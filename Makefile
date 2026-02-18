# Challenge ETL - Makefile
# Orchestration du pipeline de données

.PHONY: ingest normalize match views api eval

# CSV -> Parquet (SIRENE, RNA, BAN)
ingest:
	python3 etl/download.py
	python3 etl/ingest.py

# Nettoyage adresses -> Tables Silver
normalize:
	python3 etl/normalize.py

# Matching SIRENE/RNA -> Table de liens
match:
	python3 etl/match.py

# Génération des vues finales (Golden, Search, Stats)
views:
	python3 etl/views.py

# Lancement du serveur FastAPI
api:
	uvicorn api.main:app --reload

# Tests d'intégrité JSON
eval:
	python3 tests/test_json_integrity.py
