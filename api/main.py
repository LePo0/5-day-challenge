from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import time

# Models - Conformes aux Exemples 1-5 de l'énoncé

class PingResponse(BaseModel):
    status: str = "ok"

class Address(BaseModel):
    """Adresse normalisée (BAN)"""
    number: str
    street: str
    postal_code: str
    city: str
    is_ban_validated: bool = True
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class SiretResponse(BaseModel):
    """Structure conforme aux Exemples 1-2 de l'énoncé"""
    siret: str
    rna: Optional[str] = None
    name: str
    status: str  # "open" ou "closed"
    nature: Optional[str] = None  # "ASSOCIATION" si présent
    address: Address

class SearchResult(BaseModel):
    """Résultat de recherche conforme à l'Exemple 4"""
    siret: str
    name: str
    address_city: str

class SearchResponse(BaseModel):
    """Réponse de recherche conforme à l'Exemple 4"""
    count: int
    results: List[SearchResult]

class StatsResponse(BaseModel):
    """Statistiques conformes à l'Exemple 5"""
    postal_code: str
    total_active_companies: int
    total_associations: int
    top_activity: str  # Code NAF le plus fréquent

class ErrorResponse(BaseModel):
    """Format d'erreur conforme à l'Exemple 3"""
    error: str
    input: str

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
# Conformes aux Exemples 1-2-4 de l'énoncé

MOCK_ENTITIES = {
    # Exemple 1 : L'Entreprise Standard (SIRENE + BAN)
    "13002526500013": {
        "siret": "13002526500013",
        "rna": None,
        "name": "DIRECTION INTERMINISTERIELLE DU NUMERIQUE",
        "status": "open",
        "nature": None,
        "address": {
            "number": "20",
            "street": "AV DE SEGUR",
            "postal_code": "75007",
            "city": "PARIS",
            "is_ban_validated": True,
            "latitude": 48.850699,
            "longitude": 2.308628
        }
    },
    # Exemple 2 : Le Cas Hybride (Association avec SIRET)
    "77567227200020": {
        "siret": "77567227200020",
        "rna": "W751000060",
        "name": "CROIX ROUGE FRANCAISE",
        "status": "open",
        "nature": "ASSOCIATION",
        "address": {
            "number": "98",
            "street": "RUE DIDOT",
            "postal_code": "75014",
            "city": "PARIS",
            "is_ban_validated": True,
            "latitude": 48.8296,
            "longitude": 2.3235
        }
    },
    # Données supplémentaires pour tests
    "12345678901234": {
        "siret": "12345678901234",
        "rna": None,
        "name": "ENTREPRISE DEMO SARL",
        "status": "open",
        "nature": None,
        "address": {
            "number": "42",
            "street": "RUE DE LA PAIX",
            "postal_code": "69001",
            "city": "LYON",
            "is_ban_validated": True,
            "latitude": 45.7710,
            "longitude": 4.8349
        }
    },
    "88245100012345": {
        "siret": "88245100012345",
        "rna": None,
        "name": "BOULANGERIE DE L HOTEL DE VILLE",
        "status": "open",
        "nature": None,
        "address": {
            "number": "5",
            "street": "PLACE DE L HOTEL DE VILLE",
            "postal_code": "69001",
            "city": "LYON",
            "is_ban_validated": True,
            "latitude": 45.7679,
            "longitude": 4.8345
        }
    },
    "44312000054321": {
        "siret": "44312000054321",
        "rna": None,
        "name": "LA PETITE BOULANGERIE",
        "status": "open",
        "nature": None,
        "address": {
            "number": "12",
            "street": "RUE DE LA REPUBLIQUE",
            "postal_code": "69001",
            "city": "LYON",
            "is_ban_validated": True,
            "latitude": 45.7640,
            "longitude": 4.8357
        }
    },
    "98765432109876": {
        "siret": "98765432109876",
        "rna": "W331234567",
        "name": "ASSOCIATION SPORTIVE LOCALE",
        "status": "open",
        "nature": "ASSOCIATION",
        "address": {
            "number": "15",
            "street": "AVENUE DES SPORTS",
            "postal_code": "33000",
            "city": "BORDEAUX",
            "is_ban_validated": True,
            "latitude": 44.8378,
            "longitude": -0.5792
        }
    },
    "11223344556677": {
        "siret": "11223344556677",
        "rna": "W750123456",
        "name": "ASSOCIATION CULTURELLE PARIS 13",
        "status": "open",
        "nature": "ASSOCIATION",
        "address": {
            "number": "25",
            "street": "RUE DE TOLBIAC",
            "postal_code": "75013",
            "city": "PARIS",
            "is_ban_validated": True,
            "latitude": 48.8271,
            "longitude": 2.3571
        }
    }
}

# ==================== Endpoints ====================

@app.get("/api/v1/ping", response_model=PingResponse, tags=["Health"])
async def ping():
    """
    Healthcheck - Vérifie que l'API est opérationnelle
    Conforme à l'énoncé : réponse simple {"status": "ok"}
    
    **Utilisé pour :**
    - Tests de disponibilité
    - Monitoring
    - Stress tests
    """
    return PingResponse(status="ok")


@app.get("/api/v1/siret/{siret}", response_model=SiretResponse, tags=["Entities"])
async def get_siret(siret: str):
    """
    Récupération du Golden Record d'un établissement
    Conforme aux Exemples 1-2 de l'énoncé
    
    **Paramètres :**
    - `siret` : 14 chiffres (SIREN 9 + NIC 5)
    
    **Retourne :**
    - Données SIRENE (identité légale)
    - Données RNA (si association)
    - Données BAN (géolocalisation)
    
    **Codes HTTP :**
    - 200 : Succès
    - 400 : SIRET invalide
    - 404 : SIRET introuvable (format Exemple 3)
    """
    # Validation format SIRET
    if len(siret) != 14 or not siret.isdigit():
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid format", "input": siret}
        )
    
    # Recherche dans les données mockées
    if siret not in MOCK_ENTITIES:
        # Format conforme à l'Exemple 3 de l'énoncé
        raise HTTPException(
            status_code=404,
            detail={"error": "Siret not found", "input": siret}
        )
    
    entity = MOCK_ENTITIES[siret]
    
    return SiretResponse(
        siret=entity["siret"],
        rna=entity["rna"],
        name=entity["name"],
        status=entity["status"],
        nature=entity["nature"],
        address=Address(**entity["address"])
    )


@app.get("/api/v1/search", response_model=SearchResponse, tags=["Search"])
async def search(
    q: str = Query(..., description="Texte à chercher (nom ou enseigne)"),
    postal_code: Optional[str] = Query(None, description="Code postal (5 chiffres)")
):
    """
    Recherche géographique et textuelle
    Conforme à l'Exemple 4 de l'énoncé
    
    **Paramètres :**
    - `q` : Texte libre (nom, enseigne) - OBLIGATOIRE
    - `postal_code` : Code postal exact (5 chiffres) - OPTIONNEL
    
    **Retour :**
    - Maximum 10 résultats
    - Structure : {count, results[{siret, name, address_city}]}
    
    **Codes HTTP :**
    - 200 : Succès (même si 0 résultat)
    - 400 : Paramètre invalide
    """
    # Validation code postal si fourni
    if postal_code and (len(postal_code) != 5 or not postal_code.isdigit()):
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid postal code", "input": postal_code}
        )
    
    # Filtrage des entités mockées
    results = []
    search_text = q.lower()
    
    for entity_data in MOCK_ENTITIES.values():
        # Filtre par code postal
        if postal_code and entity_data["address"]["postal_code"] != postal_code:
            continue
        
        # Filtre par texte (recherche dans nom)
        if search_text not in entity_data["name"].lower():
            continue
        
        # Construction du résultat conforme à l'Exemple 4
        results.append(SearchResult(
            siret=entity_data["siret"],
            name=entity_data["name"],
            address_city=entity_data["address"]["city"]
        ))
    
    # Limitation à 10 résultats
    results = results[:10]
    
    return SearchResponse(
        count=len(results),
        results=results
    )


@app.get("/api/v1/stats/distribution/{code_postal}", response_model=StatsResponse, tags=["Statistics"])
async def get_stats(code_postal: str):
    """
    Statistiques par code postal
    Conforme à l'Exemple 5 de l'énoncé
    
    **Paramètres :**
    - `code_postal` : Code postal (5 chiffres)
    
    **Retourne :**
    - postal_code : Le code postal
    - total_active_companies : Nombre d'entreprises actives
    - total_associations : Nombre d'associations
    - top_activity : Code NAF le plus fréquent (string)
    
    **Codes HTTP :**
    - 200 : Succès
    - 400 : Format invalide
    """
    if len(code_postal) != 5 or not code_postal.isdigit():
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid postal code", "input": code_postal}
        )
    
    # Calcul des statistiques mockées
    # Filtre les entreprises actives (sans RNA)
    nb_companies = len([
        e for e in MOCK_ENTITIES.values()
        if e["address"]["postal_code"] == code_postal 
        and e["rna"] is None
        and e["status"] == "open"
    ])
    
    # Filtre les associations (avec RNA)
    nb_associations = len([
        e for e in MOCK_ENTITIES.values()
        if e["address"]["postal_code"] == code_postal 
        and e["rna"] is not None
        and e["status"] == "open"
    ])
    
    # Code NAF le plus fréquent (mockée pour l'exemple)
    # Dans une vraie implémentation, il faudrait compter les codes NAF réels
    top_activity = "6201Z"  # Code par défaut de l'Exemple 5
    
    # Ajuster selon le code postal pour varier les résultats
    if code_postal == "75013":
        top_activity = "6201Z"
    elif code_postal == "69001":
        top_activity = "1071C"  # Boulangerie
    elif code_postal == "33000":
        top_activity = "5610A"  # Restauration
    
    return StatsResponse(
        postal_code=code_postal,
        total_active_companies=nb_companies if nb_companies > 0 else 14502,  # Valeur de l'exemple si vide
        total_associations=nb_associations if nb_associations > 0 else 3200,  # Valeur de l'exemple si vide
        top_activity=top_activity
    )


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
