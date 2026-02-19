"""
Test des nouvelles macros normalize_numero() et normalize_city()
"""
import duckdb

# Test des macros avec des données réelles
con = duckdb.connect(':memory:')

# Définir les macros simplifiées (sans strip_accents pour test rapide)
con.execute("""
CREATE OR REPLACE MACRO norm_txt(x) AS (
    trim(
        regexp_replace(
            upper(CAST(COALESCE(x, '') AS VARCHAR)),
            '[^A-Z0-9 ]+',
            ' '
        )
    )
);

-- Parse numero + complement/repetition to extract full numero with BIS/TER/etc.
CREATE OR REPLACE MACRO normalize_numero(num, rep, comp) AS (
    trim(
        norm_txt(
            CASE
                -- Si repetition existe (RNA: "bis", "ter", "B", etc.) -> concaténer avec numero
                WHEN rep IS NOT NULL AND trim(rep) != '' THEN concat_ws(' ', num, rep)
                -- Si complement contient "BIS", "TER" etc. sans numero -> ajouter au numero de base
                WHEN comp IS NOT NULL AND (
                    upper(comp) LIKE '%BIS%' OR 
                    upper(comp) LIKE '%TER%' OR
                    upper(comp) LIKE '%QUATER%' OR
                    upper(comp) LIKE '% B %' OR
                    upper(comp) LIKE '% T %'
                )
                    THEN concat_ws(' ', num, 
                        CASE 
                            WHEN upper(comp) LIKE '%QUATER%' THEN 'QUATER'
                            WHEN upper(comp) LIKE '%TER%' THEN 'TER'
                            WHEN upper(comp) LIKE '%BIS%' THEN 'BIS'
                            WHEN upper(comp) LIKE '% B %' THEN 'B'
                            WHEN upper(comp) LIKE '% T %' THEN 'T'
                            ELSE ''
                        END
                    )
                -- Sinon, juste le numero
                ELSE num
            END
        )
    )
);

-- Normalize city name to handle arrondissements
CREATE OR REPLACE MACRO normalize_city(city) AS (
    norm_txt(
        regexp_replace(
            regexp_replace(
                COALESCE(city, ''),
                ' [0-9]+E?R? ARRONDISSEMENT$',
                '',
                'i'
            ),
            ' [0-9]+E?R?$',
            '',
            'i'
        )
    )
);
""")

print("=== Test normalize_numero() ===")
test_cases_numero = [
    ('50', None, None, '50'),
    ('50', 'bis', None, '50 BIS'),
    ('50', 'B', None, '50 B'),
    ('16', 'bis', None, '16 BIS'),
    ('94', None, 'BATIMENT A BIS', '94 BIS'),
    ('4', None, 'B', '4 B'),
    ('10', 'ter', None, '10 TER'),
]

for num, rep, comp, expected in test_cases_numero:
    result = con.execute(
        "SELECT normalize_numero(?, ?, ?)", 
        [num, rep, comp]
    ).fetchone()[0]
    status = "✓" if result == expected else "✗"
    print(f"{status} normalize_numero('{num}', '{rep}', '{comp}') = '{result}' (expected '{expected}')")

print("\n=== Test normalize_city() ===")
test_cases_city = [
    ('PARIS', 'PARIS'),
    ('PARIS 19', 'PARIS'),
    ('PARIS 19E', 'PARIS'),
    ('PARIS 19ER', 'PARIS'),
    ('PARIS 19 ARRONDISSEMENT', 'PARIS'),
    ('PARIS 19E ARRONDISSEMENT', 'PARIS'),
    ('LYON 5EME', 'LYON'),
    ('MARSEILLE 8', 'MARSEILLE'),
    ('TOULOUSE', 'TOULOUSE'),
]

for city, expected in test_cases_city:
    result = con.execute(
        "SELECT normalize_city(?)", 
        [city]
    ).fetchone()[0]
    status = "✓" if result == expected else "✗"
    print(f"{status} normalize_city('{city}') = '{result}' (expected '{expected}')")

print("\n=== Test norm_txt() ===")
test_cases_txt = [
    ('Rue du Lieutenant André Argenton', 'RUE DU LIEUTENANT ANDRE ARGENTON'),
    ('Café de l\'Europe', 'CAFE DE L EUROPE'),
    ('PARIS', 'PARIS'),
]

for text, expected in test_cases_txt:
    result = con.execute(
        "SELECT norm_txt(?)", 
        [text]
    ).fetchone()[0]
    status = "✓" if result == expected else "✗"
    print(f"{status} norm_txt('{text}') = '{result}' (expected '{expected}')")

con.close()
print("\n✅ Tests terminés")
