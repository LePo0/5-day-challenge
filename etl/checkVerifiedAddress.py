"""
Script de vérification des adresses géolocalisées par BAN

Usage:
    python scripts/check_verified_addresses.py [--limit N] [--export CSV]

Exemples:
    python scripts/check_verified_addresses.py --limit 100
    python scripts/check_verified_addresses.py --export verified_addresses.csv
    python scripts/check_verified_addresses.py --rna-only
"""

import os
import sys
import argparse
import duckdb
import pandas as pd
from datetime import datetime
from pathlib import Path

# Chemins
PROJECT_ROOT = Path(__file__).parent.parent
PARQUET_DIR = PROJECT_ROOT / "data_parquet"
DUCKDB_DIR = PROJECT_ROOT / "duckdb"
DB_PATH = DUCKDB_DIR / "catalog.db"
GOLDEN_RECORD = PARQUET_DIR / "golden_record.parquet"

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def check_verified_addresses(limit: int = None, rna_only: bool = False, export_csv: str = None):
    """
    Extrait les SIRET dont l'adresse a été vérifiée par BAN
    
    Args:
        limit: Nombre max de résultats (None = tous)
        rna_only: Seulement les établissements avec RNA
        export_csv: Chemin du fichier CSV à exporter (optionnel)
    """
    
    if not GOLDEN_RECORD.exists():
        log(f"❌ Erreur: {GOLDEN_RECORD} introuvable")
        log("   Lancez d'abord: python etl/views.py")
        sys.exit(1)
    
    log("🔍 Recherche des adresses vérifiées par BAN...")
    
    con = duckdb.connect()
    
    # Construire la requête
    sql = f"""
        SELECT
            siret,
            nom,
            enseigne,
            id_rna,
            rna_titre,
            code_postal,
            ville,
            num_voie,
            type_voie,
            libelle_voie,
            latitude,
            longitude,
            nature,
            status,
            match_score,
            match_methode
        FROM '{GOLDEN_RECORD}'
        WHERE is_ban_validated = true
    """
    
    if rna_only:
        sql += " AND id_rna IS NOT NULL"
    
    sql += " ORDER BY siret"
    
    if limit:
        sql += f" LIMIT {limit}"
    
    # Exécuter
    result = con.execute(sql).fetchdf()
    
    total = len(result)
    log(f"✅ {total:,} établissements avec adresse vérifiée trouvés")
    
    # Stats
    if total > 0:
        with_rna = result['id_rna'].notna().sum()
        associations = (result['nature'] == 'ASSOCIATION').sum()
        actifs = (result['status'] == 'open').sum()
        
        log("")
        log("📊 STATISTIQUES:")
        log(f"   • Avec RNA        : {with_rna:,} ({with_rna/total*100:.1f}%)")
        log(f"   • Associations    : {associations:,} ({associations/total*100:.1f}%)")
        log(f"   • Actifs          : {actifs:,} ({actifs/total*100:.1f}%)")
        
        # Top 5 codes postaux
        log("")
        log("📍 Top 5 codes postaux:")
        top_cp = result['code_postal'].value_counts().head(5)
        for cp, count in top_cp.items():
            log(f"   • {cp} : {count:,} établissements")
    
    # Échantillon
    if total > 0:
        log("")
        log("📋 ÉCHANTILLON (5 premiers):")
        log("-" * 120)
        
        for idx, row in result.head(5).iterrows():
            # Handle NaN values properly
            nom = row['nom'] if pd.notna(row['nom']) else (
                row['enseigne'] if pd.notna(row['enseigne']) else (
                row['rna_titre'] if pd.notna(row['rna_titre']) else '[SANS NOM]'
            ))
            
            num_voie = str(row['num_voie']) if pd.notna(row['num_voie']) else ''
            type_voie = str(row['type_voie']) if pd.notna(row['type_voie']) else ''
            libelle_voie = str(row['libelle_voie']) if pd.notna(row['libelle_voie']) else ''
            adresse = f"{num_voie} {type_voie} {libelle_voie}".strip()
            
            rna_info = f" | RNA={row['id_rna']}" if pd.notna(row['id_rna']) else ""
            
            log(f"SIRET: {row['siret']}")
            log(f"  Nom     : {str(nom)[:60]}")
            log(f"  Adresse : {adresse}, {row['code_postal']} {row['ville']}")
            log(f"  GPS     : {row['latitude']:.6f}, {row['longitude']:.6f}")
            log(f"  Nature  : {row['nature']} | Status: {row['status']}{rna_info}")
            
            if pd.notna(row['match_methode']):
                log(f"  Match   : {row['match_methode']} (score={row['match_score']:.3f})")
            log("")
    
    # Export CSV
    if export_csv:
        output_path = PROJECT_ROOT / export_csv
        result.to_csv(output_path, index=False, encoding='utf-8-sig')
        log(f"💾 Export CSV: {output_path}")
    
    con.close()
    
    return result

def main():
    parser = argparse.ArgumentParser(
        description='Vérification des adresses géolocalisées par BAN',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python scripts/check_verified_addresses.py --limit 100
  python scripts/check_verified_addresses.py --export verified.csv
  python scripts/check_verified_addresses.py --rna-only --limit 50
        """
    )
    
    parser.add_argument('--limit', type=int, default=None,
                        help='Nombre max de résultats (défaut: tous)')
    parser.add_argument('--export', type=str, default=None,
                        help='Exporter en CSV (ex: verified.csv)')
    parser.add_argument('--rna-only', action='store_true',
                        help='Seulement les établissements avec RNA')
   
    args = parser.parse_args()
    
    log("=" * 80)
    log("VÉRIFICATION DES ADRESSES GÉOLOCALISÉES")
    log("=" * 80)
    log("")
    
    result = check_verified_addresses(
        limit=args.limit,
        rna_only=args.rna_only,
        export_csv=args.export
    )
    
    log("")
    log("=" * 80)
    log("✅ VÉRIFICATION TERMINÉE")
    log("=" * 80)

if __name__ == "__main__":
    main()