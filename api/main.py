from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import time
import duckdb
import os
from pathlib import Path

# ==================== Configuration ====================

# Chemins vers les données
DATA_DIR = Path(__file__).parent.parent / "data_parquet"
DUCKDB_DIR = Path(__file__).parent.parent / "duckdb"
CATALOG_DB = DUCKDB_DIR / "catalog.db"
FTS_DB = DUCKDB_DIR / "fts_search.db"

# Chemin vers le frontend (dist/ copié à la racine)
STATIC_DIR = Path(__file__).parent.parent / "dist"

GOLDEN_RECORD = DATA_DIR / "golden_record.parquet"
SEARCH_VIEW = DATA_DIR / "search_view.parquet"
STATS_VIEW = DATA_DIR / "stats_view.parquet"

# Connexions (partagées)
con = None  # DuckDB
fts_con = None  # SQLite FTS5
stats_cache = {}  # Cache des stats en RAM
search_cache = {}  # Cache des recherches en RAM (clé: q+dept)
siret_cache = {}  # Cache des fiches siret en RAM

# ---------------------------
# MODE DEV / PROD
# ---------------------------
DEV = os.getenv("DEV", "0") == "1"
DEV_SAMPLE_PCT = int(os.getenv("DEV_SAMPLE_PCT", "1"))
DEV_LIMIT = int(os.getenv("DEV_LIMIT", "0"))

PROD_CODEC = os.getenv("PROD_CODEC", "ZSTD")  # ZSTD / SNAPPY / GZIP / "" (none)
THREADS = int(os.getenv("DUCKDB_THREADS", "8"))
MEMORY_LIMIT = os.getenv("DUCKDB_MEMORY_LIMIT", "8GB")
SEARCH_CACHE_TTL_SEC = int(os.getenv("SEARCH_CACHE_TTL_SEC", "120"))
SEARCH_CACHE_MAX_ENTRIES = int(os.getenv("SEARCH_CACHE_MAX_ENTRIES", "5000"))
SIRET_CACHE_TTL_SEC = int(os.getenv("SIRET_CACHE_TTL_SEC", "300"))
SIRET_CACHE_MAX_ENTRIES = int(os.getenv("SIRET_CACHE_MAX_ENTRIES", "100000"))


# Models

class PingResponse(BaseModel):
    status: str = "ok"
    timestamp: str
    latency_ms: float

class ErrorResponse(BaseModel):
    """Format d'erreur standardisé selon l'énoncé"""
    error: str
    message: str

# GET /siret/{siret} - Structure imbriquée selon énoncé
class Identity(BaseModel):
    siret: str
    nom_raison_sociale: str
    enseigne: Optional[str] = None
    categorie_entreprise: Optional[str] = None

class AssoId(BaseModel):
    id_rna: Optional[str] = None
    date_publication_jo: Optional[str] = None

class Location(BaseModel):
    numero_voie: Optional[str] = None
    type_voie: Optional[str] = None
    libelle_voie: Optional[str] = None
    code_postal: str
    commune: str
    geo_score: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class GoldenRecord(BaseModel):
    """Structure du Golden Record selon énoncé"""
    identity: Identity
    asso_id: AssoId
    location: Location

# GET /search - Structure selon énoncé
class SearchResult(BaseModel):
    siret: str
    name: str
    is_association: bool
    city: str

class SearchResponse(BaseModel):
    query: str
    filter_dept: Optional[str] = None
    count: int
    results: List[SearchResult]

# GET /stats/{code_postal} - Structure selon énoncé
class Repartition(BaseModel):
    entreprises_pures: int
    associations: int
    etablissements_fermes: int

class TopNaf(BaseModel):
    code: Optional[str] = None
    libelle: Optional[str] = None
    count: int

class StatsResponse(BaseModel):
    zone: str
    total_entites: int
    repartition: Repartition
    top_naf: TopNaf

# ==================== Application ====================

app = FastAPI(
    title="Challenge ETL API",
    description="API unifiée SIRENE + RNA + BAN",
    version="1.0.0",
)

# CORS pour le frontend React sur port 5173 (Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permettre toutes les origines (prod + dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Frontend Statique ====================

# Monter le dossier dist/ pour servir les assets (JS, CSS, images)
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

# ==================== Startup / Shutdown ====================

@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage de l'API"""
    global con, fts_con, stats_cache, search_cache, siret_cache
    
    # Vérifier que catalog.db existe (avec les tables et index créés par views.py)
    if not CATALOG_DB.exists():
        raise FileNotFoundError(
            f"Base DuckDB manquante : {CATALOG_DB}\n"
            "Exécutez d'abord : python etl/views.py"
        )
    
    # Connexion au catalog.db (tables et index déjà créés par views.py)
    con = duckdb.connect(str(CATALOG_DB), read_only=True)
    con.execute(f"SET threads = {THREADS}")
    con.execute(f"SET memory_limit = '{MEMORY_LIMIT}'")
    
    print("✅ Connexion au catalog.db (avec index pré-construits)")
    
    # Vérifier que les tables existent
    tables = con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()
    table_names = [t[0] for t in tables]
    
    if 'search_view' not in table_names:
        raise RuntimeError(
            "Table search_view manquante dans catalog.db.\n"
            "Ré-exécutez : python etl/views.py"
        )
    
    # Connexion SQLite FTS5 pour recherche textuelle optimisée
    if FTS_DB.exists():
        import sqlite3
        fts_con = sqlite3.connect(str(FTS_DB))
        print("✅ Connexion à fts_search.db (index FTS5)")
    else:
        print("⚠️  fts_search.db absent - recherche textuelle sera plus lente")
        fts_con = None
    
    # Charger stats_view en RAM (cache complet)
    stats_df = con.execute("SELECT * FROM stats_view").df()
    stats_cache = stats_df.set_index('code_postal').to_dict('index')
    search_cache = {}
    siret_cache = {}
    
    print(f"✅ API démarrée")
    print(f"  • Database      : {CATALOG_DB}")
    print(f"  • FTS Index     : {'Activé' if fts_con else 'Désactivé'}")
    print(f"  • Tables        : {', '.join(table_names)}")
    print(f"  • Stats Cache   : {len(stats_cache)} codes postaux")
    print(f"  • Search Cache  : TTL={SEARCH_CACHE_TTL_SEC}s, max={SEARCH_CACHE_MAX_ENTRIES}")
    print(f"  • SIRET Cache   : TTL={SIRET_CACHE_TTL_SEC}s, max={SIRET_CACHE_MAX_ENTRIES}")

@app.on_event("shutdown")
async def shutdown_event():
    """Nettoyage à l'arrêt de l'API"""
    global con, fts_con
    if con:
        con.close()
    if fts_con:
        fts_con.close()

# ==================== Endpoints ====================

@app.get("/api/v1/ping", response_model=PingResponse, tags=["Health"])
async def ping():
    """
    Healthcheck - Vérifie que l'API est opérationnelle
    
    **Utilisé pour :**
    - Tests de disponibilité
    - Monitoring
    - Stress tests
    
    **Retourne :**
    - status : État de l'API
    - timestamp : Horodatage
    - latency_ms : Temps de réponse en millisecondes
    """
    start_time = time.time()
    
    # Calcul de la latence
    latency = round((time.time() - start_time) * 1000, 2)
    
    return PingResponse(
        status="ok",
        timestamp=datetime.now().isoformat(),
        latency_ms=latency
    )


@app.get("/api/v1/siret/{siret}", response_model=GoldenRecord, tags=["Entities"], responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
async def get_siret(siret: str):
    """
    Récupération du Golden Record d'un établissement
    
    **Paramètres :**
    - `siret` : 14 chiffres (SIREN 9 + NIC 5)
    
    **Retourne :**
    - identity : Données SIRENE (identité légale)
    - asso_id : Données RNA (si association)
    - location : Données BAN (géolocalisation)
    
    **Codes HTTP :**
    - 200 : Succès
    - 400 : SIRET invalide
    - 404 : SIRET introuvable
    """
    # Validation format SIRET
    if len(siret) != 14 or not siret.isdigit():
        return JSONResponse(
            status_code=400,
            content={
                "error": "INVALID_FORMAT",
                "message": "Le siret doit contenir 14 chiffres."
            }
        )

    cache_key = siret_cache_key(siret)
    cached_payload = siret_cache_get(cache_key)
    if cached_payload is not None:
        return GoldenRecord(**cached_payload)
    
    # Requête dans golden_record (table avec index dans catalog.db)
    result = con.execute("""
        SELECT 
            siret,
            siren,
            nom,
            enseigne,
            code_postal,
            num_voie,
            type_voie,
            libelle_voie,
            ville,
            id_rna,
            latitude,
            longitude,
            geo_quality,
            CAST(rna_date_creation AS VARCHAR) as date_creation,
            status
        FROM golden_record
        WHERE siret = ?
    """, [siret]).fetchone()
    
    if not result:
        return JSONResponse(
            status_code=404,
            content={
                "error": "SIRET_NOT_FOUND",
                "message": f"Le siret {siret} est inconnu."
            }
        )
    
    # Extraction des valeurs
    (siret_val, siren_val, nom, enseigne, code_postal, num_voie, type_voie,
     libelle_voie, ville, id_rna, latitude, longitude, geo_quality, 
     date_creation, status) = result
    
    # Calcul de categorie_entreprise (simplifié)
    categorie = "PME"  # Par défaut, pourrait être enrichi avec effectifs
    
    # Construction de la réponse structurée
    response = GoldenRecord(
        identity=Identity(
            siret=siret_val,
            nom_raison_sociale=nom or "[SANS NOM]",
            enseigne=enseigne,
            categorie_entreprise=categorie
        ),
        asso_id=AssoId(
            id_rna=id_rna,
            date_publication_jo=date_creation
        ),
        location=Location(
            numero_voie=num_voie,
            type_voie=type_voie,
            libelle_voie=libelle_voie,
            code_postal=code_postal,
            commune=ville or "[COMMUNE INCONNUE]",
            geo_score=round(geo_quality, 2) if geo_quality else None,
            latitude=round(latitude, 4) if latitude else None,
            longitude=round(longitude, 4) if longitude else None
        )
    )
    siret_cache_set(cache_key, response.model_dump())
    return response


# ==================== Helpers ====================

def escape_fts5(text: str) -> str:
    """
    Échappe les caractères spéciaux pour FTS5
    
    Caractères problématiques : " ' ( ) [ ] { } * : ^
    
    Args:
        text: Texte à échapper
    
    Returns:
        Texte nettoyé et sécurisé pour FTS5
    
    Examples:
        >>> escape_fts5("VILLE D'AVRAY")
        'VILLE D AVRAY'
        >>> escape_fts5('ASSOCIATION "SECOURS" POPULAIRE')
        'ASSOCIATION SECOURS POPULAIRE'
    """
    # Supprimer les caractères spéciaux FTS5
    special_chars = ['"', "'", '(', ')', '[', ']', '{', '}', '*', ':', '^']
    for char in special_chars:
        text = text.replace(char, ' ')
    
    # Nettoyer les espaces multiples
    text = ' '.join(text.split())
    
    return text


def search_cache_key(q: Optional[str], dept: Optional[str]) -> str:
    q_norm = (q or "").strip().lower()
    dept_norm = (dept or "").strip()
    return f"q={q_norm}|dept={dept_norm}"


def search_cache_get(key: str):
    now = time.time()
    item = search_cache.get(key)
    if not item:
        return None
    ts, payload = item
    if now - ts > SEARCH_CACHE_TTL_SEC:
        search_cache.pop(key, None)
        return None
    return payload


def search_cache_set(key: str, payload: dict) -> None:
    if SEARCH_CACHE_MAX_ENTRIES <= 0:
        return
    now = time.time()
    search_cache[key] = (now, payload)

    if len(search_cache) > SEARCH_CACHE_MAX_ENTRIES:
        oldest_key = min(search_cache.items(), key=lambda kv: kv[1][0])[0]
        search_cache.pop(oldest_key, None)


def siret_cache_key(siret: str) -> str:
    return (siret or "").strip()


def siret_cache_get(key: str):
    now = time.time()
    item = siret_cache.get(key)
    if not item:
        return None
    ts, payload = item
    if now - ts > SIRET_CACHE_TTL_SEC:
        siret_cache.pop(key, None)
        return None
    return payload


def siret_cache_set(key: str, payload: dict) -> None:
    if SIRET_CACHE_MAX_ENTRIES <= 0:
        return
    now = time.time()
    siret_cache[key] = (now, payload)

    if len(siret_cache) > SIRET_CACHE_MAX_ENTRIES:
        oldest_key = min(siret_cache.items(), key=lambda kv: kv[1][0])[0]
        siret_cache.pop(oldest_key, None)


# ==================== Endpoints ====================

@app.get("/api/v1/search", response_model=SearchResponse, tags=["Search"], responses={400: {"model": ErrorResponse}})
async def search(
    q: Optional[str] = Query(None, description="Texte à chercher (nom ou enseigne)"),
    dept: Optional[str] = Query(None, description="Code département (2 chiffres)")
):
    """
    Recherche géographique et textuelle
    
    **Paramètres :**
    - `q` : Texte libre (nom, enseigne, RNA)
    - `dept` : Code département (2 chiffres)
    
    **Retour :**
    - Maximum 10 résultats
    - Tri par pertinence
    
    **Codes HTTP :**
    - 200 : Succès (même si 0 résultat)
    - 400 : Paramètre invalide
    """
    # Validation département
    if dept and (len(dept) not in [2, 3] or not dept.isdigit()):
        return JSONResponse(
            status_code=400,
            content={
                "error": "INVALID_FORMAT",
                "message": f"Le code département doit contenir 2 ou 3 chiffres (reçu: {dept})"
            }
        )

    cache_key = search_cache_key(q, dept)
    cached_payload = search_cache_get(cache_key)
    if cached_payload is not None:
        return SearchResponse(**cached_payload)
    
    # STRATÉGIE OPTIMISÉE : FTS5 si recherche textuelle, sinon DuckDB
    if q and fts_con:
        # === RECHERCHE FTS5 (< 100ms) ===
        cursor = fts_con.cursor()
        
        # Échapper les caractères spéciaux FTS5
        q_escaped = escape_fts5(q)
        
        # Vérifier que la requête n'est pas vide après nettoyage
        if not q_escaped.strip():
            return JSONResponse(
                status_code=400,
                content={
                    "error": "INVALID_FORMAT",
                    "message": "Query invalide après nettoyage (caractères spéciaux uniquement)"
                }
            )
        
        # Ajouter wildcards pour recherche partielle
        fts_query = ' '.join([f'{word}*' for word in q_escaped.split()])
        
        # Construire la requête FTS avec filtre département
        if dept:
            cursor.execute("""
                SELECT siret FROM search_fts 
                WHERE search_fts MATCH ? AND code_postal LIKE ?
                LIMIT 50
            """, (fts_query, f"{dept}%"))
        else:
            cursor.execute("""
                SELECT siret FROM search_fts 
                WHERE search_fts MATCH ?
                LIMIT 50
            """, (fts_query,))
        
        # Récupérer les SIRETs matchés
        sirets = [row[0] for row in cursor.fetchall()]
        
        if not sirets:
            response = SearchResponse(query=q or "", filter_dept=dept, count=0, results=[])
            search_cache_set(cache_key, response.model_dump())
            return response
        
        # Enrichir avec les données DuckDB
        placeholders = ','.join(['?' for _ in sirets])
        results = con.execute(f"""
            SELECT 
                siret,
                display_name as name,
                COALESCE(ville, '') as city,
                id_rna
            FROM search_view
            WHERE siret IN ({placeholders})
            LIMIT 10
        """, sirets).fetchall()
    
    else:
        # === RECHERCHE DUCKDB CLASSIQUE (avec index) ===
        where_clauses = []
        params = []
        
        if dept:
            where_clauses.append("code_postal LIKE ?")
            params.append(f"{dept}%")
        
        if q:
            where_clauses.append("search_text_lower LIKE ?")
            search_pattern = f"%{q.lower()}%"
            params.append(search_pattern)
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        results = con.execute(f"""
            SELECT 
                siret,
                display_name as name,
                COALESCE(ville, '') as city,
                id_rna
            FROM search_view
            WHERE {where_sql}
            LIMIT 10
        """, params).fetchall()
    
    # Conversion en objets SearchResult
    search_results = []
    for row in results:
        search_results.append(SearchResult(
            siret=row[0],
            name=row[1],
            is_association=(row[3] is not None),
            city=row[2]
        ))
    
    response = SearchResponse(
        query=q or "",
        filter_dept=dept,
        count=len(search_results),
        results=search_results
    )
    search_cache_set(cache_key, response.model_dump())
    return response


@app.get("/api/v1/stats/{code_postal}", response_model=StatsResponse, tags=["Statistics"], responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
async def get_stats(code_postal: str):
    """
    Statistiques par code postal
    
    **Paramètres :**
    - `code_postal` : Code postal (5 chiffres)
    
    **Retourne :**
    - zone : Code postal
    - total_entites : Nombre total d'établissements
    - repartition : Détail entreprises/associations/fermés
    - top_naf : Code NAF le plus fréquent avec libellé
    """
    if len(code_postal) != 5 or not code_postal.isdigit():
        return JSONResponse(
            status_code=400,
            content={
                "error": "INVALID_FORMAT",
                "message": f"Le code postal doit contenir 5 chiffres (reçu: {code_postal})"
            }
        )
    
    # Lookup O(1) dans le cache stats
    if code_postal not in stats_cache:
        return JSONResponse(
            status_code=404,
            content={
                "error": "ZONE_NOT_FOUND",
                "message": f"Le code postal {code_postal} est inconnu."
            }
        )
    
    stats = stats_cache[code_postal]
    
    # Calcul de la répartition
    total_entites = int(stats["total_entites"])
    total_associations = int(stats["total_associations"])
    total_fermes = int(stats.get("total_fermees", 0))  # Colonne = total_fermees dans stats_view
    entreprises_pures = total_entites - total_associations
    
    # Mapping NAF code -> libellé (simplifié, devrait être enrichi avec table NAF)
    naf_code = stats.get("top_naf_code")
    naf_libelle = None  # Pourrait être enrichi avec une vraie table de référence NAF
    
    # Construction de la réponse structurée selon énoncé
    return StatsResponse(
        zone=code_postal,
        total_entites=total_entites,
        repartition=Repartition(
            entreprises_pures=entreprises_pures,
            associations=total_associations,
            etablissements_fermes=total_fermes
        ),
        top_naf=TopNaf(
            code=naf_code,
            libelle=naf_libelle,
            count=int(stats.get("top_naf_count", 0)) if stats.get("top_naf_count") else 0
        )
    )


# ==================== Routes Frontend ====================

@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend index.html at root"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Frontend not built. Run 'npm run build' in front-5dc/"}

@app.get("/{full_path:path}", include_in_schema=False)
async def catch_all(full_path: str):
    """
    Catch-all route for SPA routing.
    Try to serve the file if it exists, otherwise return index.html.
    """
    # Ignorer les routes API
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    # Chercher le fichier demandé
    file_path = STATIC_DIR / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    
    # Fallback to index.html for SPA routing (React Router)
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    
    return {"message": "Frontend not found"}

# ==================== Point d'entrée ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
