# 5-day-challenge

## Vue d'ensemble

Projet ETL de consolidation des données SIRENE (entreprises), RNA (associations) et BAN (adresses) permettant la recherche rapide et géolocalisée d'établissements français via une API REST et une interface web moderne.

## Architecture

### Backend

- **Framework**: FastAPI 1.0.0
- **Base de données analytique**: DuckDB (catalog.db)
- **Moteur de recherche**: SQLite FTS5 (fts_search.db)
- **Serveur**: Uvicorn ASGI
- **Python**: 3.11+ requis

### Frontend

- **Framework**: React 18
- **Build Tool**: Vite 5
- **UI Library**: Material-UI (MUI)
- **State Management**: Zustand
- **Client HTTP**: Axios

### Structure des données

```
Bronze Layer (data_raw/)
  ├── StockEtablissement_utf8.csv (SIRENE)
  ├── rna_waldec_*.csv (RNA)
  └── adresses-*.csv (BAN)

Silver Layer (data_parquet/)
  ├── sirene_silver.parquet
  ├── rna_silver.parquet
  ├── ban_silver.parquet
  └── link_sirene_rna.parquet

Gold Layer (duckdb/)
  ├── catalog.db (golden_record, search_view, stats_view)
  └── fts_search.db (index FTS5 pour recherche textuelle)
```

## Pipeline ETL

### Étape 1: Normalisation (etl/normalize.py)

Normalisation des fichiers CSV sources:
- SIRENE: 42M d'établissements
- RNA: 1.5M d'associations
- BAN: 26M d'adresses

```powershell
python etl/normalize.py
```

### Étape 2: Conversion Parquet (etl/csv_to_parquet.py)

Conversion des CSV normalisés en Parquet pour performances optimales:

```powershell
python etl/csv_to_parquet.py
```

### Étape 3: Matching SIRENE-RNA (etl/match.py)

Création de la table de liaison entre SIRENE et RNA basée sur le SIREN:

```powershell
python etl/match.py
```

### Étape 4: Génération des vues (etl/views.py)

Création du golden_record et des vues optimisées:

```powershell
python etl/views.py
```

**Optimisations appliquées**:
- Utilisation de `ANY_VALUE()` au lieu de `AVG()` pour lat/lon (-40% temps)
- `MAX(geo_quality)` pour sélection meilleure adresse
- Suppression des `ORDER BY` dans les CTEs
- SQLite PRAGMAs: `journal_mode=OFF`, `synchronous=OFF`, `cache_size=1000000`
- Indexation stratégique: SIREN, SIRET, code postal, statut

**Durée d'exécution**: ~50-70 secondes pour 42M d'établissements

### Schéma golden_record

```sql
CREATE TABLE golden_record (
    siren TEXT,
    siret TEXT PRIMARY KEY,
    nom TEXT,
    enseigne TEXT,
    activite_principale TEXT,
    code_naf TEXT,
    libelle_naf TEXT,
    is_association BOOLEAN,
    numero_voie TEXT,
    type_voie TEXT,
    libelle_voie TEXT,
    code_postal TEXT,
    libelle_commune TEXT,
    latitude DOUBLE,
    longitude DOUBLE,
    geo_quality INTEGER,
    status TEXT,
    date_creation TEXT,
    date_maj TEXT,
    id_association TEXT,
    titre_association TEXT,
    objet_association TEXT
);
```

## API REST

### Démarrage du serveur

```powershell
uvicorn api.main:app --reload
```

Le serveur démarre sur `http://localhost:8000`

### Endpoints

#### 1. Recherche par SIRET

```
GET /siret/{siret}
```

**Paramètres**:
- `siret` (path): Numéro SIRET à 14 chiffres

**Exemple**:
```bash
curl http://localhost:8000/siret/12345678901234
```

**Réponse**:
```json
{
  "identity": {
    "siren": "123456789",
    "siret": "12345678901234",
    "nom": "ENTREPRISE EXEMPLE",
    "enseigne": "ENSEIGNE EXEMPLE",
    "activite_principale": "62.01Z",
    "code_naf": "6201Z",
    "libelle_naf": "Programmation informatique",
    "is_association": false,
    "status": "A",
    "date_creation": "2010-01-15",
    "date_maj": "2025-12-01"
  },
  "asso_id": {
    "id_association": null,
    "titre_association": null,
    "objet_association": null
  },
  "location": {
    "numero_voie": "10",
    "type_voie": "RUE",
    "libelle_voie": "DE LA PAIX",
    "code_postal": "75001",
    "libelle_commune": "PARIS 1ER ARRONDISSEMENT",
    "latitude": 48.8656,
    "longitude": 2.3212,
    "geo_quality": 8
  }
}
```

**Codes HTTP**:
- 200: SIRET trouvé
- 404: SIRET inexistant
- 422: Format SIRET invalide

#### 2. Recherche textuelle

```
GET /search?query={text}&code_postal={cp}&limit={n}
```

**Paramètres**:
- `query` (obligatoire): Texte de recherche (nom, enseigne, activité)
- `code_postal` (optionnel): Filtrage par code postal
- `limit` (optionnel): Nombre de résultats (défaut: 20, max: 100)

**Exemple**:
```bash
curl "http://localhost:8000/search?query=boulangerie&code_postal=75001&limit=10"
```

**Réponse**:
```json
[
  {
    "identity": {
      "siren": "123456789",
      "siret": "12345678901234",
      "nom": "BOULANGERIE DUPONT",
      "enseigne": "AU BON PAIN",
      "activite_principale": "10.71C",
      "code_naf": "1071C",
      "libelle_naf": "Boulangerie et boulangerie-pâtisserie",
      "is_association": false,
      "status": "A",
      "date_creation": "2005-03-20",
      "date_maj": "2025-11-15"
    },
    "asso_id": {
      "id_association": null,
      "titre_association": null,
      "objet_association": null
    },
    "location": {
      "numero_voie": "5",
      "type_voie": "RUE",
      "libelle_voie": "DES HALLES",
      "code_postal": "75001",
      "libelle_commune": "PARIS 1ER ARRONDISSEMENT",
      "latitude": 48.8628,
      "longitude": 2.3447,
      "geo_quality": 9
    }
  }
]
```

#### 3. Statistiques par code postal

```
GET /stats/{code_postal}
```

**Paramètres**:
- `code_postal` (path): Code postal à 5 chiffres

**Exemple**:
```bash
curl http://localhost:8000/stats/75001
```

**Réponse**:
```json
{
  "code_postal": "75001",
  "total_etablissements": 12543,
  "total_actifs": 11234,
  "total_fermes": 1309,
  "total_associations": 234,
  "total_entreprises": 12309,
  "top_activites": [
    {
      "code_naf": "6201Z",
      "libelle_naf": "Programmation informatique",
      "count": 1523
    },
    {
      "code_naf": "7022Z",
      "libelle_naf": "Conseil pour les affaires et autres conseils de gestion",
      "count": 1098
    }
  ]
}
```

#### 4. Health check

```
GET /ping
```

**Réponse**:
```json
{
  "status": "ok"
}
```

## Installation

### Prérequis

- Python 3.11 ou supérieur
- Node.js 18+ et npm
- 50 GB d'espace disque disponible
- 16 GB RAM recommandés

### Backend

1. Créer un environnement virtuel:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. Installer les dépendances:
```powershell
pip install -r requirements.txt
```

3. Télécharger les données sources:
- SIRENE: https://www.insee.fr/fr/statistiques/fichier/3591226/StockEtablissement_utf8.zip
- RNA: https://www.data.gouv.fr/fr/datasets/repertoire-national-des-associations/
- BAN: https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/

4. Placer les fichiers CSV dans `data_raw/`

5. Exécuter le pipeline ETL complet:
```powershell
python etl/normalize.py
python etl/csv_to_parquet.py
python etl/match.py
python etl/views.py
```

6. Lancer l'API:
```powershell
uvicorn api.main:app --reload
```

### Frontend

1. Installer les dépendances:
```powershell
cd front-5dc
npm install
```

2. Build pour production:
```powershell
npm run build
```

3. Copier le dossier `dist/` à la racine du projet

Le frontend sera automatiquement servi par FastAPI sur `http://localhost:8000`

## Déploiement sur VM Linux

### Option 1: Transfert SCP

```powershell
# Compression avant transfert
tar -czf 5dc.tar.gz --exclude=venv --exclude=node_modules --exclude=data_raw .

# Transfert vers VM
scp 5dc.tar.gz user@vm-ip:/mnt/data/

# Sur la VM
ssh user@vm-ip
cd /mnt/data
tar -xzf 5dc.tar.gz
```

### Option 2: Transfert sélectif

```powershell
# Uniquement les fichiers essentiels
scp -r api/ etl/ duckdb/ dist/ requirements.txt user@vm-ip:/mnt/data/5-day-challenge/
```

### Configuration VM

```bash
# Créer environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer dépendances
pip install -r requirements.txt

# Lancer en production
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Gestion DuckDB WAL

Si erreur "Bad file descriptor" avec fichiers `.wal`:

```bash
# Supprimer les fichiers WAL
rm duckdb/*.wal

# Recréer la base (si nécessaire)
python3 etl/views.py
```

Ou modifier `api/main.py` pour forcer le mode read-only:

```python
duck_conn = duckdb.connect(DB_PATH, read_only=True, config={'access_mode': 'READ_ONLY'})
```

## Performances

### Métriques ETL

- Lecture Parquet SIRENE (42M lignes): ~8s
- Lecture Parquet RNA (1.5M lignes): ~1s
- Lecture Parquet BAN (26M lignes): ~12s
- CTE ban_best (géolocalisation): ~18s
- Jointures SIRENE + RNA + BAN: ~15s
- Écriture golden_record: ~10s
- Indexation SQLite FTS5: ~25s
- **Total**: 50-70s

### Optimisations appliquées

1. **DuckDB**:
   - `ANY_VALUE(latitude), ANY_VALUE(longitude)` au lieu de `AVG()`
   - `MAX(geo_quality)` pour sélection optimale
   - Suppression des `ORDER BY` inutiles dans CTEs
   - Indexes stratégiques sur SIREN, SIRET, code_postal, status

2. **SQLite FTS5**:
   - `PRAGMA journal_mode = OFF`
   - `PRAGMA synchronous = OFF`
   - `PRAGMA cache_size = 1000000`
   - Insertion par batch avec `BEGIN TRANSACTION`

3. **API**:
   - Connexions DuckDB en mode read_only
   - Cache des requêtes fréquentes
   - Limitation à 100 résultats max

## Tests

```powershell
# Test intégrité des données
python tests/test_json_integrity.py

# Test API
curl http://localhost:8000/ping
curl http://localhost:8000/siret/12345678901234
```

## Structure du projet

```
5-day-challenge/
├── api/
│   ├── __init__.py
│   └── main.py                 # API FastAPI
├── etl/
│   ├── normalize.py            # Normalisation CSV
│   ├── csv_to_parquet.py       # Conversion Parquet
│   ├── match.py                # Matching SIRENE-RNA
│   ├── views.py                # Génération golden_record
│   └── ingest.py               # Utilitaires
├── tests/
│   └── test_json_integrity.py
├── data_raw/                   # CSV sources
├── data_parquet/               # Parquet silver layer
├── duckdb/                     # Bases DuckDB et SQLite
├── dist/                       # Frontend build
├── requirements.txt
├── Makefile
└── README.md
```

## Technologies

- **Backend**: Python 3.11, FastAPI 1.0.0, DuckDB 1.2.0, SQLite3
- **Frontend**: React 18, Vite 5, Material-UI 6, Zustand, Axios
- **Data**: Parquet, CSV
- **Serveur**: Uvicorn ASGI

## Auteur

Projet développé dans le cadre du "5-day challenge" - Consolidation SIRENE + RNA + BAN
