# Challenge ETL - Script PowerShell (équivalent Makefile pour Windows)
# Usage: .\make.ps1 <commande>

function Show-Help {
    Write-Host "Challenge ETL - Commandes disponibles:" -ForegroundColor Cyan
    Write-Host "  .\make.ps1 ingest    - CSV -> Parquet (SIRENE, RNA, BAN)"
    Write-Host "  .\make.ps1 normalize - Nettoyage adresses -> Tables Silver"
    Write-Host "  .\make.ps1 match     - Matching SIRENE/RNA -> Table de liens"
    Write-Host "  .\make.ps1 views     - Generation des vues finales"
    Write-Host "  .\make.ps1 api       - Lancement du serveur FastAPI"
    Write-Host "  .\make.ps1 eval      - Tests d'integrite JSON"
}

# CSV -> Parquet (SIRENE, RNA, BAN)
function Start-Ingest {
    python etl/ingest.py
}

# Nettoyage adresses -> Tables Silver
function Start-Normalize {
    python etl/normalize.py
}

# Matching SIRENE/RNA -> Table de liens
function Start-Match {
    python etl/match.py
}

# Génération des vues finales
function Start-Views {
    python etl/views.py
}

# Lancement du serveur FastAPI
function Start-API {
    uvicorn api.main:app --reload
}

# Tests d'intégrité JSON
function Start-Eval {
    python tests/test_json_integrity.py
}

# Main
param([Parameter(Position = 0)][string]$Command = "help")

switch ($Command.ToLower()) {
    "help" { Show-Help }
    "ingest" { Start-Ingest }
    "normalize" { Start-Normalize }
    "match" { Start-Match }
    "views" { Start-Views }
    "api" { Start-API }
    "eval" { Start-Eval }
    default {
        Write-Host "Commande inconnue: $Command" -ForegroundColor Red
        Show-Help
    }
}
