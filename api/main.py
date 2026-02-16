from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import time

# Models

class PingResponse(BaseModel):
    status: str = "ok"
    timestamp: str
    latency_ms: float

class GoldenRecord(BaseModel):
    """Structure du Golden Record (SIRENE + RNA + BAN)"""
    siret: str
    siren: str
    nom: str
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
    adresse: str
    code_postal: str
    commune: str
    id_rna: Optional[str] = None

class SearchResponse(BaseModel):
    query: str
    postal_code: Optional[str] = None
    count: int
    results: List[SearchResult]

# ==================== Application ====================

app = FastAPI(
    title="Challenge ETL API",
    description="API unifiée SIRENE + RNA + BAN avec données mockées",
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

# ==================== Données Mockées ====================

MOCK_ENTITIES = {
    "77567227200020": {
        "siret": "77567227200020",
        "siren": "775672272",
        "nom": "CROIX ROUGE FRANCAISE",
        "enseigne": None,
        "code_postal": "75015",
        "numero_voie": "98",
        "libelle_voie": "RUE DIDOT",
        "commune": "PARIS 15",
        "id_rna": "W751000022",
        "titre_association": "CROIX ROUGE FRANCAISE",
        "latitude": 48.8317,
        "longitude": 2.3157,
        "geo_score": 0.95,
        "etat_administratif": "A",
        "date_creation": "1945-05-08",
        "date_maj": "2025-12-15"
    },
    "12345678901234": {
        "siret": "12345678901234",
        "siren": "123456789",
        "nom": "ENTREPRISE DEMO SARL",
        "enseigne": "DEMO SHOP",
        "code_postal": "69001",
        "numero_voie": "42",
        "libelle_voie": "RUE DE LA PAIX",
        "commune": "LYON 1ER",
        "id_rna": None,
        "titre_association": None,
        "latitude": 45.7710,
        "longitude": 4.8349,
        "geo_score": 0.88,
        "etat_administratif": "A",
        "date_creation": "2010-03-15",
        "date_maj": "2026-01-20"
    },
    "98765432109876": {
        "siret": "98765432109876",
        "siren": "987654321",
        "nom": "ASSOCIATION SPORTIVE LOCALE",
        "enseigne": "ASL SPORTS",
        "code_postal": "33000",
        "numero_voie": "15",
        "libelle_voie": "AVENUE DES SPORTS",
        "commune": "BORDEAUX",
        "id_rna": "W331234567",
        "titre_association": "ASSOCIATION SPORTIVE LOCALE",
        "latitude": 44.8378,
        "longitude": -0.5792,
        "geo_score": 0.92,
        "etat_administratif": "A",
        "date_creation": "2018-09-10",
        "date_maj": "2025-11-05"
    }
}

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
    
    # Recherche dans les données mockées
    if siret not in MOCK_ENTITIES:
        raise HTTPException(
            status_code=404,
            detail=f"SIRET {siret} introuvable dans la base de données"
        )
    
    return GoldenRecord(**MOCK_ENTITIES[siret])


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
    
    # Filtrage des entités mockées
    results = []
    for entity_data in MOCK_ENTITIES.values():
        # Filtre par code postal
        if postal_code and entity_data["code_postal"] != postal_code:
            continue
        
        # Filtre par texte (recherche dans nom et enseigne)
        if q:
            search_text = q.lower()
            nom_match = search_text in entity_data["nom"].lower()
            enseigne_match = (
                entity_data["enseigne"] and 
                search_text in entity_data["enseigne"].lower()
            )
            
            if not (nom_match or enseigne_match):
                continue
        
        # Construction du résultat
        adresse = f"{entity_data['numero_voie'] or ''} {entity_data['libelle_voie'] or ''}".strip()
        
        results.append(SearchResult(
            siret=entity_data["siret"],
            nom=entity_data["nom"],
            enseigne=entity_data["enseigne"],
            adresse=adresse,
            code_postal=entity_data["code_postal"],
            commune=entity_data["commune"],
            id_rna=entity_data["id_rna"]
        ))
    
    # Limitation à 10 résultats
    results = results[:10]
    
    return SearchResponse(
        query=q or "",
        postal_code=postal_code,
        count=len(results),
        results=results
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
    
    # Statistiques mockées
    nb_entreprises = len([
        e for e in MOCK_ENTITIES.values()
        if e["code_postal"] == code_postal and e["id_rna"] is None
    ])
    
    nb_associations = len([
        e for e in MOCK_ENTITIES.values()
        if e["code_postal"] == code_postal and e["id_rna"] is not None
    ])
    
    return {
        "code_postal": code_postal,
        "nb_entreprises": nb_entreprises,
        "nb_associations": nb_associations,
        "top_naf": [
            {"code": "8790B", "libelle": "Action sociale", "count": nb_associations},
            {"code": "4711D", "libelle": "Supermarchés", "count": nb_entreprises}
        ]
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
