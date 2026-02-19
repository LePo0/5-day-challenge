param([Parameter(Position = 0)][string]$Command = "help")

function Show-Help {
    Write-Host "Challenge ETL - Commandes disponibles:" -ForegroundColor Cyan
    Write-Host "  .\make.ps1 ingest    - CSV -> Parquet (SIRENE, RNA, BAN)"
    Write-Host "  .\make.ps1 normalize - Nettoyage adresses -> Tables Silver"
    Write-Host "  .\make.ps1 match     - Matching SIRENE/RNA -> Table de liens"
    Write-Host "  .\make.ps1 views     - Generation des vues finales"
    Write-Host "  .\make.ps1 api       - Lancement du serveur FastAPI"
    Write-Host "  .\make.ps1 eval      - Tests d'integrite JSON"
}

function Start-Ingest {
    Write-Host "Downloading files..." -ForegroundColor Cyan
    python etl/download.py

    Write-Host "Converting CSV -> Parquet..." -ForegroundColor Cyan
    python etl/ingest.py
}

function Start-Normalize { python etl/normalize.py }
function Start-Match     { python etl/match.py }
function Start-Views     { python etl/views.py }

function Start-API {
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
}

function Start-Eval { python tests/test_json_integrity.py }

switch ($Command.ToLower()) {
    "help"      { Show-Help }
    "ingest"    { Start-Ingest }
    "normalize" { Start-Normalize }
    "match"     { Start-Match }
    "views"     { Start-Views }
    "api"       { Start-API }
    "eval"      { Start-Eval }
    default {
        Write-Host "Commande inconnue: $Command" -ForegroundColor Red
        Show-Help
    }
}