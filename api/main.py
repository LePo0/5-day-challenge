from fastapi import FastAPI, HTTPException, Query
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

GOLDEN_RECORD = DATA_DIR / "golden_record.parquet"
SEARCH_VIEW = DATA_DIR / "search_view.parquet"
STATS_VIEW = DATA_DIR / "stats_view.parquet"

# Connexions (partagées)
con = None  # DuckDB
fts_con = None  # SQLite FTS5
stats_cache = {}  # Cache des stats en RAM

# Models

class PingResponse(BaseModel):
    status: str = "ok"
    timestamp: str
    latency_ms: float

class GoldenRecord(BaseModel):
    """Structure du Golden Record (SIRENE + RNA + BAN)"""
    siret: str
    siren: str
    nom: Optional[str] = None
    enseigne: Optional[str] = None
    code_postal: str
    numero_voie: Optional[str] = None
    libelle_voie: Optional[str] = None
    commune: str
    
    # RNA (si association)
    id_rna: Optional[str] = None
    titre_association: Optional[str] = None
    
    # BAN (géolocalisation)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geo_score: Optional[float] = None
    
    # Métadonnées
    etat_administratif: str = "A"  # A=Actif, F=Fermé
    date_creation: Optional[str] = None
    date_maj: Optional[str] = None

class SearchResult(BaseModel):
    """Résultat de recherche simplifié"""
    siret: str
    nom: str
    enseigne: Optional[str] = None
    adresse: Optional[str] = None
    code_postal: Optional[str] = None
    commune: Optional[str] = None
    id_rna: Optional[str] = None

class SearchResponse(BaseModel):
    query: str
    postal_code: Optional[str] = None
    count: int
    results: List[SearchResult]

# ==================== Application ====================

app = FastAPI(
    title="Challenge ETL API",
    description="API unifiée SIRENE + RNA + BAN",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc"
)

# CORS pour le frontend React sur port 5173 (Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Startup / Shutdown ====================

@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage de l'API"""
    global con, fts_con, stats_cache
    
    # Vérifier que catalog.db existe (avec les tables et index créés par views.py)
    if not CATALOG_DB.exists():
        raise FileNotFoundError(
            f"Base DuckDB manquante : {CATALOG_DB}\n"
            "Exécutez d'abord : python etl/views.py"
        )
    
    # Connexion au catalog.db (tables et index déjà créés par views.py)
    con = duckdb.connect(str(CATALOG_DB), read_only=True)
    con.execute("SET threads = 4")
    con.execute("SET memory_limit = '4GB'")
    
    print("Connexion au catalog.db (avec index pré-construits)")
    
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
        print("Connexion à fts_search.db (index FTS5)")
    else:
        print("fts_search.db absent - recherche textuelle sera plus lente")
        fts_con = None
    
    # Charger stats_view en RAM (cache complet)
    stats_df = con.execute("SELECT * FROM stats_view").df()
    stats_cache = stats_df.set_index('code_postal').to_dict('index')
    
    print(f"API démarrée")
    print(f"  • Database      : {CATALOG_DB}")
    print(f"  • FTS Index     : {'Activé' if fts_con else 'Désactivé'}")
    print(f"  • Tables        : {', '.join(table_names)}")
    print(f"  • Stats Cache   : {len(stats_cache)} codes postaux")

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


@app.get("/api/v1/siret/{siret}", response_model=GoldenRecord, tags=["Entities"])
async def get_siret(siret: str):
    """
    Récupération du Golden Record d'un établissement
    
    **Paramètres :**
    - `siret` : 14 chiffres (SIREN 9 + NIC 5)
    
    **Retourne :**
    - Données SIRENE (identité légale)
    - Données RNA (si association)
    - Données BAN (géolocalisation)
    
    **Codes HTTP :**
    - 200 : Succès
    - 400 : SIRET invalide
    - 404 : SIRET introuvable
    """
    # Validation format SIRET
    if len(siret) != 14 or not siret.isdigit():
        raise HTTPException(
            status_code=400,
            detail="SIRET invalide : doit contenir exactement 14 chiffres"
        )
    
    # Requête dans golden_record (table avec index dans catalog.db)
    result = con.execute("""
        SELECT 
            siret,
            siren,
            COALESCE(nom, '') as nom,
            enseigne,
            code_postal,
            num_voie as numero_voie,
            libelle_voie,
            ville as commune,
            id_rna,
            rna_titre as titre_association,
            latitude,
            longitude,
            CASE 
                WHEN latitude IS NOT NULL THEN 1.0 
                ELSE NULL 
            END as geo_score,
            etat as etat_administratif,
            CAST(rna_date_creation AS VARCHAR) as date_creation,
            NULL as date_maj
        FROM golden_record
        WHERE siret = ?
    """, [siret]).fetchone()
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"SIRET {siret} introuvable dans la base de données"
        )
    
    # Conversion en dictionnaire
    columns = [
        'siret', 'siren', 'nom', 'enseigne', 'code_postal', 
        'numero_voie', 'libelle_voie', 'commune', 'id_rna', 
        'titre_association', 'latitude', 'longitude', 'geo_score', 
        'etat_administratif', 'date_creation', 'date_maj'
    ]
    data = dict(zip(columns, result))
    
    return GoldenRecord(**data)


@app.get("/api/v1/search", response_model=SearchResponse, tags=["Search"])
async def search(
    q: Optional[str] = Query(None, description="Texte à chercher (nom ou enseigne)"),
    postal_code: Optional[str] = Query(None, description="Code postal (5 chiffres)")
):
    """
    Recherche géographique et textuelle
    
    **Paramètres :**
    - `q` : Texte libre (nom, enseigne, RNA)
    - `postal_code` : Code postal exact (5 chiffres)
    
    **Retour :**
    - Maximum 10 résultats
    - Tri par pertinence
    
    **Codes HTTP :**
    - 200 : Succès (même si 0 résultat)
    - 400 : Paramètre invalide
    """
    # Validation code postal
    if postal_code and (len(postal_code) != 5 or not postal_code.isdigit()):
        raise HTTPException(
            status_code=400,
            detail="Code postal invalide : doit contenir exactement 5 chiffres"
        )
    
    # STRATÉGIE OPTIMISÉE : FTS5 si recherche textuelle, sinon DuckDB
    if q and fts_con:
        # === RECHERCHE FTS5 (< 100ms) ===
        cursor = fts_con.cursor()
        
        # Construire la requête FTS
        if postal_code:
            cursor.execute("""
                SELECT siret FROM search_fts 
                WHERE search_fts MATCH ? AND code_postal = ?
                LIMIT 50
            """, (q, postal_code))
        else:
            cursor.execute("""
                SELECT siret FROM search_fts 
                WHERE search_fts MATCH ?
                LIMIT 50
            """, (q,))
        
        # Récupérer les SIRETs matchés
        sirets = [row[0] for row in cursor.fetchall()]
        
        if not sirets:
            return SearchResponse(query=q, postal_code=postal_code, count=0, results=[])
        
        # Enrichir avec les données DuckDB
        placeholders = ','.join(['?' for _ in sirets])
        results = con.execute(f"""
            SELECT 
                siret,
                display_name as nom,
                NULL as enseigne,
                COALESCE(adresse, '') as adresse,
                COALESCE(code_postal, '') as code_postal,
                COALESCE(ville, '') as commune,
                CASE WHEN is_association THEN 'W__' ELSE NULL END as id_rna
            FROM search_view
            WHERE siret IN ({placeholders})
            LIMIT 10
        """, sirets).fetchall()
    
    else:
        # === RECHERCHE DUCKDB CLASSIQUE (avec index) ===
        where_clauses = []
        params = []
        
        if postal_code:
            where_clauses.append("code_postal = ?")
            params.append(postal_code)
        
        if q:
            where_clauses.append("search_text_lower LIKE ?")
            search_pattern = f"%{q.lower()}%"
            params.append(search_pattern)
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        results = con.execute(f"""
            SELECT 
                siret,
                display_name as nom,
                NULL as enseigne,
                COALESCE(adresse, '') as adresse,
                COALESCE(code_postal, '') as code_postal,
                COALESCE(ville, '') as commune,
                CASE WHEN is_association THEN 'W__' ELSE NULL END as id_rna
            FROM search_view
            WHERE {where_sql}
            LIMIT 10
        """, params).fetchall()
    
    # Conversion en objets SearchResult
    search_results = []
    for row in results:
        search_results.append(SearchResult(
            siret=row[0],
            nom=row[1],
            enseigne=row[2],
            adresse=row[3],
            code_postal=row[4],
            commune=row[5],
            id_rna=row[6]
        ))
    
    return SearchResponse(
        query=q or "",
        postal_code=postal_code,
        count=len(search_results),
        results=search_results
    )


@app.get("/api/v1/stats/{code_postal}", tags=["Statistics"])
async def get_stats(code_postal: str):
    """
    Statistiques par code postal (BONUS)
    
    **Paramètres :**
    - `code_postal` : Code postal (5 chiffres)
    
    **Retourne :**
    - Nombre d'entreprises
    - Nombre d'associations
    - Top 5 des codes NAF
    
    **Note :** Endpoint optionnel pour bonus
    """
    if len(code_postal) != 5 or not code_postal.isdigit():
        raise HTTPException(
            status_code=400,
            detail="Code postal invalide : doit contenir exactement 5 chiffres"
        )
    
    # Lookup O(1) dans le cache stats
    if code_postal not in stats_cache:
        raise HTTPException(
            status_code=404,
            detail=f"Code postal {code_postal} introuvable dans la base"
        )
    
    stats = stats_cache[code_postal]
    
    # Construction de la réponse (mapping des noms de colonnes)
    return {
        "code_postal": code_postal,
        "total_etablissements": int(stats["total_entites"]),
        "total_actifs": int(stats["total_active"]),
        "total_associations": int(stats["total_associations"]),
        "top_naf": {
            "code": stats.get("top_naf_code"),
            "count": int(stats.get("top_naf_count", 0)) if stats.get("top_naf_count") else 0
        }
    }


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
