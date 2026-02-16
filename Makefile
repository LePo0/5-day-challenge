# Challenge ETL - Makefile
# Orchestration du pipeline de données

.PHONY: ingest normalize match views api eval

# CSV -> Parquet (SIRENE, RNA, BAN)
ingest:
	python etl/ingest.py

# Nettoyage adresses -> Tables Silver
normalize:
	python etl/normalize.py

# Matching SIRENE/RNA -> Table de liens
match:
	python etl/match.py

# Génération des vues finales (Golden, Search, Stats)
views:
	python etl/views.py

# Lancement du serveur FastAPI
api:
	uvicorn api.main:app --reload

# Tests d'intégrité JSON
eval:
	python tests/test_json_integrity.py
