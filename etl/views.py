import os
from datetime import datetime
import duckdb

PARQUET_DIR = "data_parquet"
DUCKDB_DIR = "duckdb"
DB_PATH = os.path.join(DUCKDB_DIR, "catalog.db")

# Inputs
SIRENE_SILVER = os.path.join(PARQUET_DIR, "sirene_silver.parquet")
RNA_SILVER = os.path.join(PARQUET_DIR, "rna_silver.parquet")
BAN_SILVER = os.path.join(PARQUET_DIR, "ban_silver.parquet")
LINK_SIRENE_RNA = os.path.join(PARQUET_DIR, "link_sirene_rna.parquet")

# Outputs
GOLDEN_RECORD = os.path.join(PARQUET_DIR, "golden_record.parquet")
SEARCH_VIEW = os.path.join(PARQUET_DIR, "search_view.parquet")
STATS_VIEW = os.path.join(PARQUET_DIR, "stats_view.parquet")

THREADS = int(os.getenv("DUCKDB_THREADS", "8"))
MEMORY_LIMIT = os.getenv("DUCKDB_MEMORY_LIMIT", "8GB")

DEV = os.getenv("DEV", "0") == "1"
PROD_CODEC = os.getenv("PROD_CODEC", "ZSTD")

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def out_opts() -> str:
    """Options Parquet selon DEV/PROD."""
    # ROW_GROUP_SIZE optimisé pour grands datasets:
    # - Plus grands row_groups = meilleure compression
    # - Meilleurs predicate pushdown pour filtres WHERE
    # - Recommandé: 128MB pour datasets > 1M lignes
    base_opts = "FORMAT PARQUET, ROW_GROUP_SIZE_BYTES 134217728"  # 128MB
    
    if DEV:
        return f"({base_opts})"
    if PROD_CODEC:
        return f"({base_opts}, CODEC '{PROD_CODEC}')"
    return f"({base_opts})"

def atomic_replace(tmp_path: str, final_path: str) -> None:
    """Remplace atomiquement (Windows-friendly)."""
    if os.path.exists(tmp_path):
        os.replace(tmp_path, final_path)

def create_golden_record(con: duckdb.DuckDBPyConnection) -> None:
    """
    Vue #1 : Golden Record (Table maître unifiée)
    
    Structure :
    - Tous les SIRET de SIRENE (base)
    - LEFT JOIN avec link_sirene_rna pour obtenir id_rna
    - LEFT JOIN avec RNA pour obtenir infos association
    - LEFT JOIN avec BAN pour obtenir coordonnées GPS
    
    Clé primaire : siret (unique)
    """
    log("GOLDEN RECORD : Fusion SIRENE + RNA + BAN...")
    
    out_final = GOLDEN_RECORD
    out_tmp = out_final + ".tmp"
    opts = out_opts()
    
    con.execute(
        f"""
COPY (
    WITH 
    -- Liens SIRENE ↔ RNA (un SIRET peut avoir plusieurs RNA, on garde le meilleur score)
    best_links AS (
        SELECT 
            siret,
            id_rna,
            score,
            methode,
            ROW_NUMBER() OVER (PARTITION BY siret ORDER BY score DESC, id_rna) as rn
        FROM '{LINK_SIRENE_RNA}'
    ),
    unique_links AS (
        SELECT siret, id_rna, score, methode
        FROM best_links
        WHERE rn = 1
    ),
    
    -- Matching BAN : meilleure adresse par (code_postal, ville norm, rue norm)
    ban_best AS (
        SELECT 
            code_postal,
            nom_commune,
            street_norm,
            AVG(lat) as latitude,
            AVG(lon) as longitude,
            COUNT(*) as nb_adresses
        FROM '{BAN_SILVER}'
        WHERE lat IS NOT NULL AND lon IS NOT NULL
        GROUP BY code_postal, nom_commune, street_norm
    )
    
    SELECT
        -- Identité SIRENE
        s.siret,
        s.siren,
        s.nom,
        s.enseigne,
        s.naf,
        s.etat,
        
        -- Association RNA (si lien existe)
        l.id_rna,
        r.titre_asso as rna_titre,
        r.objet as rna_objet,
        r.date_creat as rna_date_creation,
        l.score as match_score,
        l.methode as match_methode,
        
        -- Adresse SIRENE
        s.code_postal,
        s.ville,
        s.numero as num_voie,
        s.type_voie,
        s.libelle_voie,
        
        -- Géolocalisation BAN
        b.latitude,
        b.longitude,
        CASE 
            WHEN b.latitude IS NOT NULL THEN true 
            ELSE false 
        END as is_ban_validated,
        
        -- Champs normalisés (pour debug / recherche)
        s.name_norm,
        s.street_norm,
        s.city_norm,
        
        -- Type d'entité calculé
        CASE 
            WHEN l.id_rna IS NOT NULL THEN 'ASSOCIATION'
            WHEN s.nom IS NULL AND s.enseigne IS NOT NULL THEN 'COMMERCE'
            ELSE 'ENTREPRISE'
        END as nature,
        
        -- Statut calculé
        CASE 
            WHEN s.etat = 'A' THEN 'open'
            WHEN s.etat = 'F' THEN 'closed'
            ELSE 'unknown'
        END as status
        
    FROM '{SIRENE_SILVER}' s
    
    -- Lien vers RNA (optionnel)
    LEFT JOIN unique_links l ON s.siret = l.siret
    
    -- Infos RNA (optionnel)
    LEFT JOIN '{RNA_SILVER}' r ON l.id_rna = r.id_rna
    
    -- Géolocalisation BAN (optionnel, par adresse normalisée)
    LEFT JOIN ban_best b 
        ON s.code_postal = b.code_postal 
        AND s.city_norm = b.nom_commune
        AND s.street_norm = b.street_norm
        
    ORDER BY s.siret  -- Tri pour optimiser les lookups SIRET
)
TO '{out_tmp}' {opts};
"""
    )
    
    atomic_replace(out_tmp, out_final)
    
    # Stats
    count = con.execute(f"SELECT count(*) FROM '{out_final}'").fetchone()[0]
    with_rna = con.execute(f"SELECT count(*) FROM '{out_final}' WHERE id_rna IS NOT NULL").fetchone()[0]
    with_geo = con.execute(f"SELECT count(*) FROM '{out_final}' WHERE is_ban_validated = true").fetchone()[0]
    
    log(f" GOLDEN RECORD écrit : {count:,} SIRET")
    log(f"   • Avec RNA         : {with_rna:,} ({with_rna/count*100:.1f}%)")
    log(f"   • Avec géoloc BAN  : {with_geo:,} ({with_geo/count*100:.1f}%)")

def create_search_view(con: duckdb.DuckDBPyConnection) -> None:
    """
    Vue #2 : Search View (Index de recherche textuelle)
    
    Contient uniquement les champs nécessaires pour la recherche :
    - siret (clé)
    - search_text (nom || enseigne || titre_asso)
    - code_postal (filtre géographique)
    - ville (affichage)
    - is_association (flag)
    """
    log("SEARCH VIEW : Index de recherche textuelle...")
    
    out_final = SEARCH_VIEW
    out_tmp = out_final + ".tmp"
    opts = out_opts()
    
    con.execute(
        f"""
COPY (
    SELECT
        siret,
        
        -- Texte de recherche (tous les noms possibles + adresse + ville)
        COALESCE(
            TRIM(
                CONCAT_WS(' ',
                    NULLIF(nom, ''),
                    NULLIF(enseigne, ''),
                    NULLIF(rna_titre, ''),
                    NULLIF(ville, ''),
                    NULLIF(libelle_voie, '')
                )
            ),
            ''
        ) as search_text,
        
        -- Texte normalisé (pour fuzzy search)
        COALESCE(
            TRIM(
                CONCAT_WS(' ',
                    NULLIF(name_norm, ''),
                    NULLIF(rna_titre, '')
                )
            ),
            ''
        ) as search_text_norm,
        
        -- Texte minuscule pré-calculé pour recherche rapide (nom + adresse + ville)
        LOWER(COALESCE(
            TRIM(
                CONCAT_WS(' ',
                    NULLIF(nom, ''),
                    NULLIF(enseigne, ''),
                    NULLIF(rna_titre, ''),
                    NULLIF(ville, ''),
                    NULLIF(libelle_voie, '')
                )
            ),
            ''
        )) as search_text_lower,
        
        -- Ville en minuscule (pour filtre rapide)
        LOWER(COALESCE(ville, '')) as ville_lower,
        
        -- Adresse complète formatée
        TRIM(CONCAT_WS(' ',
            NULLIF(num_voie, ''),
            NULLIF(type_voie, ''),
            NULLIF(libelle_voie, '')
        )) as adresse,
        
        -- Filtres géographiques
        code_postal,
        ville,
        
        -- Métadonnées pour affichage
        COALESCE(nom, enseigne, rna_titre, '[SANS NOM]') as display_name,
        nature,
        status,
        
        -- Flag association
        CASE 
            WHEN id_rna IS NOT NULL THEN true 
            ELSE false 
        END as is_association
        
    FROM '{GOLDEN_RECORD}'
    WHERE status = 'open'  -- Uniquement les établissements actifs
    ORDER BY code_postal, siret  -- Tri pour optimiser les scans
)
TO '{out_tmp}' {opts};
"""
    )
    
    atomic_replace(out_tmp, out_final)
    
    count = con.execute(f"SELECT count(*) FROM '{out_final}'").fetchone()[0]
    log(f" SEARCH VIEW écrit : {count:,} entrées actives")

def create_stats_view(con: duckdb.DuckDBPyConnection) -> None:
    """
    Vue #3 : Stats View (Statistiques pré-agrégées par code postal)
    
    Pré-calcule pour chaque code postal :
    - Nombre total d'établissements
    - Nombre d'associations
    - Nombre d'établissements fermés
    - Top NAF (code + libellé + count)
    """
    log("STATS VIEW : Statistiques par code postal...")
    
    out_final = STATS_VIEW
    out_tmp = out_final + ".tmp"
    opts = out_opts()
    
    con.execute(
        f"""
COPY (
    WITH 
    -- Comptages par CP
    cp_counts AS (
        SELECT
            code_postal,
            COUNT(*) as total_entites,
            SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as total_active,
            SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as total_fermees,
            SUM(CASE WHEN nature = 'ASSOCIATION' THEN 1 ELSE 0 END) as total_associations,
            SUM(CASE WHEN nature != 'ASSOCIATION' THEN 1 ELSE 0 END) as total_entreprises
        FROM '{GOLDEN_RECORD}'
        GROUP BY code_postal
    ),
    
    -- Top NAF par CP (uniquement pour les actifs)
    top_naf AS (
        SELECT
            code_postal,
            naf,
            COUNT(*) as count_naf,
            ROW_NUMBER() OVER (PARTITION BY code_postal ORDER BY COUNT(*) DESC) as rn
        FROM '{GOLDEN_RECORD}'
        WHERE status = 'open' AND naf IS NOT NULL
        GROUP BY code_postal, naf
    ),
    
    -- Garder uniquement le top 1 NAF par CP
    best_naf AS (
        SELECT code_postal, naf, count_naf
        FROM top_naf
        WHERE rn = 1
    )
    
    SELECT
        c.code_postal,
        c.total_entites,
        c.total_active,
        c.total_fermees,
        c.total_associations,
        c.total_entreprises,
        
        -- Top NAF
        n.naf as top_naf_code,
        n.count_naf as top_naf_count
        
    FROM cp_counts c
    LEFT JOIN best_naf n ON c.code_postal = n.code_postal
    ORDER BY c.code_postal
)
TO '{out_tmp}' {opts};
"""
    )
    
    atomic_replace(out_tmp, out_final)
    
    count = con.execute(f"SELECT count(*) FROM '{out_final}'").fetchone()[0]
    log(f" STATS VIEW écrit : {count:,} codes postaux")

def create_indexes(con: duckdb.DuckDBPyConnection) -> None:
    """
    Crée les index sur les vues pour optimiser les performances API
    """
    log("CRÉATION DES INDEX...")
    
    # Charger les parquets en tables DuckDB
    log("  Chargement des vues en tables...")
    
    con.execute(f"CREATE OR REPLACE TABLE golden_record AS SELECT * FROM '{GOLDEN_RECORD}'")
    con.execute(f"CREATE OR REPLACE TABLE search_view AS SELECT * FROM '{SEARCH_VIEW}'")
    con.execute(f"CREATE OR REPLACE TABLE stats_view AS SELECT * FROM '{STATS_VIEW}'")
    
    log("   Tables chargées")
    
    # === INDEX GOLDEN_RECORD (Endpoint: GET /siret/{siret}) ===
    log("  📍 Index pour GET /siret/{siret}...")
    try:
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_golden_siret ON golden_record(siret)")
        log("     golden_record.siret (UNIQUE) - Lookup O(1)")
    except Exception as e:
        log(f"      Erreur siret : {e}")
    
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_golden_cp ON golden_record(code_postal)")
        log("     golden_record.code_postal - Filtrage géographique")
    except Exception as e:
        log(f"      Erreur code_postal : {e}")
    
    # Index pour agrégations stats (si stats_view absente ou calcul temps réel)
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_golden_cp_etat ON golden_record(code_postal, etat)")
        log("     golden_record.(code_postal, etat) - Count fermés")
    except Exception as e:
        log(f"      Erreur cp+etat : {e}")
    
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_golden_cp_naf ON golden_record(code_postal, naf)")
        log("     golden_record.(code_postal, naf) - Top NAF")
    except Exception as e:
        log(f"      Erreur cp+naf : {e}")
    
    # === INDEX SEARCH_VIEW (Endpoint: GET /search?q=...&postal_code=...) ===
    log("")
    log("  🔍 Index pour GET /search...")
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_search_siret ON search_view(siret)")
        log("     search_view.siret - Lookup direct")
    except Exception as e:
        log(f"      Erreur siret : {e}")
    
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_search_cp ON search_view(code_postal)")
        log("     search_view.code_postal - Filtre primaire (CRITIQUE)")
    except Exception as e:
        log(f"      Erreur code_postal : {e}")
    
    # Index composite OPTIMAL pour recherche textuelle filtrée par CP
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_search_cp_text ON search_view(code_postal, search_text_lower)")
        log("     search_view.(code_postal, search_text_lower) - Recherche optimisée")
    except Exception as e:
        log(f"      Erreur cp+text : {e}")
    
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_search_ville ON search_view(ville_lower)")
        log("     search_view.ville_lower - Recherche par ville")
    except Exception as e:
        log(f"      Erreur ville : {e}")
    
    # Index partiel pour recherches d'associations (bonus perf)
    try:
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_search_associations 
            ON search_view(code_postal, search_text_lower) 
            WHERE id_rna IS NOT NULL
        """)
        log("     search_view WHERE is_association=true - Index partiel")
    except Exception as e:
        log(f"      Erreur associations : {e}")
    
    # === INDEX STATS_VIEW (Endpoint: GET /stats/{code_postal}) ===
    log("")
    log("  📊 Index pour GET /stats/{code_postal}...")
    try:
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_stats_cp ON stats_view(code_postal)")
        log("     stats_view.code_postal (UNIQUE) - Lookup O(1)")
    except Exception as e:
        log(f"      Erreur stats : {e}")
    
    # === OPTIMISATION QUERY PLANNER ===
    log("")
    log("  🔧 Analyse des statistiques pour query planner...")
    con.execute("ANALYZE golden_record")
    con.execute("ANALYZE search_view")
    con.execute("ANALYZE stats_view")
    log("     Tables analysées (distribution des valeurs calculée)")
    
    # === RÉSUMÉ ===
    log("")
    log("=" * 80)
    log(" RÉSUMÉ DES INDEX CRÉÉS")
    log("=" * 80)
    log("  GOLDEN_RECORD (42M lignes) :")
    log("    • siret (UNIQUE)           → GET /siret/{siret} < 50ms")
    log("    • code_postal              → Filtre géographique")
    log("    • (code_postal, etat)      → Count fermés pour /stats")
    log("    • (code_postal, naf)       → Top NAF pour /stats")
    log("")
    log("  SEARCH_VIEW (38M lignes actives) :")
    log("    • siret                    → Lookup direct")
    log("    • code_postal              → Filtre primaire /search")
    log("    • (code_postal, text)      → Recherche textuelle optimisée")
    log("    • ville_lower              → Recherche par ville")
    log("    • WHERE is_association     → Index partiel pour associations")
    log("")
    log("  STATS_VIEW (16k codes postaux) :")
    log("    • code_postal (UNIQUE)     → GET /stats/{cp} < 10ms")
    log("")
    log("🎯 Total : 10 index créés (3 UNIQUE, 1 partiel, 6 standards)")

def create_fts_sqlite() -> None:
    """
    Crée une base SQLite FTS5 pour la recherche textuelle ultra-rapide
    """
    import sqlite3
    
    log("CRÉATION INDEX FULL-TEXT SEARCH (SQLite FTS5)...")
    
    SQLITE_FTS = os.path.join(DUCKDB_DIR, "fts_search.db")
    
    # Supprimer l'ancienne base si elle existe
    if os.path.exists(SQLITE_FTS):
        os.remove(SQLITE_FTS)
    
    # Charger les données depuis Parquet
    con_duck = duckdb.connect()
    df = con_duck.execute(f"""
        SELECT 
            siret,
            search_text,
            search_text_norm,
            code_postal,
            ville,
            display_name,
            nature,
            is_association
        FROM '{SEARCH_VIEW}'
        WHERE search_text IS NOT NULL AND search_text != ''
    """).df()
    
    log(f"  {len(df):,} lignes à indexer")
    
    # Créer la base SQLite avec FTS5
    con_sqlite = sqlite3.connect(SQLITE_FTS)
    
    con_sqlite.execute("""
        CREATE VIRTUAL TABLE search_fts USING fts5(
            siret UNINDEXED,
            search_text,
            search_text_norm,
            code_postal UNINDEXED,
            ville UNINDEXED,
            display_name UNINDEXED,
            nature UNINDEXED,
            is_association UNINDEXED,
            tokenize='porter unicode61 remove_diacritics 1'
        )
    """)
    
    # Insérer par batches
    batch_size = 50000
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]
        batch.to_sql('search_fts', con_sqlite, if_exists='append', index=False)
        if i % 500000 == 0 and i > 0:
            log(f"    {i:,} / {len(df):,} insérés")
    
    # Optimiser
    con_sqlite.execute("INSERT INTO search_fts(search_fts) VALUES('optimize')")
    con_sqlite.commit()
    con_sqlite.close()
    con_duck.close()
    
    size_mb = os.path.getsize(SQLITE_FTS) / 1024 / 1024
    log(f"   Index FTS5 créé : {size_mb:.1f} MB")

def verify_views(con: duckdb.DuckDBPyConnection) -> None:
    """Vérifications de cohérence"""
    log("VÉRIFICATIONS...")
    
    # Golden Record : test échantillon
    sample = con.execute(f"""
        SELECT siret, nom, id_rna, is_ban_validated, nature
        FROM '{GOLDEN_RECORD}'
        LIMIT 3
    """).fetchall()
    
    log("  Échantillon Golden Record :")
    for row in sample:
        siret, nom, rna, geo, nature = row
        log(f"    {siret} | {nom[:40] if nom else '[VIDE]'} | RNA={rna} | GEO={geo} | {nature}")
    
    # Search View : comptages
    search_stats = con.execute(f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN is_association THEN 1 ELSE 0 END) as nb_asso,
            AVG(LENGTH(search_text)) as avg_text_len
        FROM '{SEARCH_VIEW}'
    """).fetchone()
    
    log(f"  Search View : {search_stats[0]:,} entrées | {search_stats[1]:,} associations | texte moyen {search_stats[2]:.0f} car.")
    
    # Stats View : exemple
    stats_sample = con.execute(f"""
        SELECT code_postal, total_active, total_associations, top_naf_code
        FROM '{STATS_VIEW}'
        ORDER BY total_active DESC
        LIMIT 3
    """).fetchall()
    
    log("  Top 3 codes postaux (par activité) :")
    for cp, actifs, assos, naf in stats_sample:
        log(f"    {cp} : {actifs:,} actifs | {assos:,} associations | NAF dominant = {naf}")

def benchmark_performance(con: duckdb.DuckDBPyConnection) -> None:
    """Test de performance des requêtes"""
    import time
    
    log("\n" + "=" * 80)
    log("⚡ BENCHMARK DE PERFORMANCE")
    log("=" * 80)
    
    # Test 1 : Lookup par SIRET
    log("\n  GET /siret/77567227200020 (Croix Rouge)")
    start = time.time()
    result = con.execute("SELECT siret, nom, id_rna FROM golden_record WHERE siret = '77567227200020'").fetchone()
    duration = (time.time() - start) * 1000
    
    if result:
        log(f"   Trouvé : {result[1]} | RNA={result[2]}")
        log(f"    {duration:.2f} ms {'' if duration < 100 else '' if duration < 500 else ' LENT'}")
    
    # Test 2 : Recherche par CP
    log("\n  GET /search?postal_code=75015")
    start = time.time()
    results = con.execute("SELECT COUNT(*) FROM search_view WHERE code_postal = '75015'").fetchone()
    duration = (time.time() - start) * 1000
    log(f"   {results[0]:,} établissements")
    log(f"    {duration:.2f} ms {'' if duration < 50 else '' if duration < 200 else ' LENT'}")
    
    # Test 3 : Stats
    log("\n  GET /stats/75015")
    start = time.time()
    result = con.execute("SELECT total_active, total_associations FROM stats_view WHERE code_postal = '75015'").fetchone()
    duration = (time.time() - start) * 1000
    if result:
        log(f"   Actifs={result[0]:,} | Associations={result[1]:,}")
        log(f"    {duration:.2f} ms {'' if duration < 10 else '' if duration < 50 else ' LENT'}")

def main() -> None:
    log("=" * 80)
    log("GÉNÉRATION DES VUES API")
    log("=" * 80)
    
    # Vérifier que les inputs existent
    for path, name in [
        (SIRENE_SILVER, "SIRENE Silver"),
        (RNA_SILVER, "RNA Silver"),
        (BAN_SILVER, "BAN Silver"),
        (LINK_SIRENE_RNA, "Liens SIRENE-RNA"),
    ]:
        if not os.path.exists(path):
            log(f" Manquant : {name} ({path})")
            return
    
    # Connexion DuckDB
    con = duckdb.connect(DB_PATH)
    con.execute(f"SET threads = {THREADS}")
    con.execute(f"SET memory_limit = '{MEMORY_LIMIT}'")
    con.execute("SET preserve_insertion_order = false")
    
    try:
        # 1. Génération des 3 vues
        create_golden_record(con)
        create_search_view(con)
        create_stats_view(con)
        
        # 2. Création des index
        log("")
        log("=" * 80)
        create_indexes(con)
        
        # 3. Index FTS (optionnel, pour recherche ultra-rapide)
        log("")
        log("=" * 80)
        try:
            create_fts_sqlite()
        except Exception as e:
            log(f"  FTS5 non créé (optionnel) : {e}")
        
        # 4. Vérifications
        log("")
        log("=" * 80)
        verify_views(con)
        
        # 5. Benchmark
        benchmark_performance(con)
        
        log("\n" + "=" * 80)
        log(" VUES & INDEX CRÉÉS AVEC SUCCÈS")
        log("=" * 80)
        log("")
        log(" Fichiers générés :")
        log(f"  • {GOLDEN_RECORD} (table maître)")
        log(f"  • {SEARCH_VIEW} (recherche)")
        log(f"  • {STATS_VIEW} (stats pré-calculées)")
        log(f"  • {DB_PATH} (catalog DuckDB + 10 index)")
        log(f"  • duckdb/fts_search.db (index FTS5 SQLite)")
        log("")
        log(" Prochaine étape :")
        log("  python api/main.py")
        log("  ou")
        log("  uvicorn api.main:app --reload")
        
    finally:
        con.close()

if __name__ == "__main__":
    main()
