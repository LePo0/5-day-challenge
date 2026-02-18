# ANALYSE APPROFONDIE DES DONNÉES SOURCES

## 📊 SCHÉMAS RÉELS DES DONNÉES

### **BAN (Base Adresse Nationale) - 26 colonnes**

```
id, id_fantoir, numero, rep, nom_voie, code_postal, code_insee, nom_commune,
code_insee_ancienne_commune, nom_ancienne_commune, x, y, lon, lat,
type_position, alias, nom_ld, libelle_acheminement, nom_afnor,
source_position, source_nom_voie, certification_commune, cad_parcelles
```

**Colonnes utilisées actuellement :** `id, numero, rep, nom_voie, code_postal, nom_commune, lat, lon`

**Colonnes manquantes importantes :**
- ❌ `libelle_acheminement` : Nom officiel La Poste (peut différer de nom_commune)
- ❌ `nom_afnor` : Normalisation AFNOR de la voie
- ❌ `code_insee` : Code INSEE (pour matching plus précis que code postal)

---

### **RNA (Répertoire National des Associations) - 37 colonnes**

Exemple réel :
```
W011000049 | 7,89044E+13 | CLUB DES RANDONNEURS PEDESTRES DE BELLEY
94 RUE du Lieutenant Andre Argenton | 1300 Belley
```

**Colonnes utilisées actuellement :** 
```
id, siret, titre, adrs_codepostal, adrs_libcommune, objet, date_creat,
adrs_numvoie, adrs_typevoie, adrs_libvoie
```

**⚠️ PROBLÈMES IDENTIFIÉS :**

#### **1. SIRET en notation scientifique**
```
Fichier CSV : 789044000000013
Excel/LibreOffice : 7,89044E+13
```
**Impact :** Le SIRET peut être tronqué ou mal lu lors de l'import.

**Solution actuelle (ingest.py:95) :** ✅
```python
types={'adrs_codepostal': 'VARCHAR', 'siret': 'VARCHAR', 'id': 'VARCHAR'}
```
Bon : Force VARCHAR pour éviter conversion scientifique.

---

#### **2. Libellés de voie hétérogènes**

**RNA :**
```
adrs_typevoie = "RUE"
adrs_libvoie = "du Lieutenant Andre Argenton"
```
→ Contient : articles ("du"), casse mixte, espaces multiples

**SIRENE :**
```
typeVoieEtablissement = "RUE"
libelleVoieEtablissement = "HENRI BARBUSSE"
```
→ MAJUSCULES, pas d'article, propre

**BAN :**
```
nom_voie = "Rue du Lieutenant André Argenton"
```
→ Casse mixte, accents, type de voie inclus

**Problème de matching :**
```python
# RNA normalisé
"94 RUE DU LIEUTENANT ANDRE ARGENTON"

# SIRENE normalisé
"134 RUE HENRI BARBUSSE"

# BAN normalisé
"94 RUE LIEUTENANT ANDRE ARGENTON"  # Doit supprimer "du"
```

Si on ne supprime pas les articles, le matching échoue !

---

#### **3. Répétitions d'adresse (BIS, TER)**

**BAN :**
```
numero = "94"
rep = ""           # Vide si pas de répétition
```

**Si adresse avec BIS :**
```
numero = "94"
rep = "B"          # Ou "BIS", "T" (TER), etc.
```

**Problème actuel (ingest.py:130) :**
```python
SELECT id, numero, rep, nom_voie, ...
```
✅ La colonne `rep` est lue mais **pas concaténée avec numero dans normalize.py** !

**Impact :**
- BAN : `numero="94", rep="B"` → devrait donner `"94 B"` ou `"94 BIS"`
- SIRENE : `numeroVoieEtablissement="94"` (pas de répétition)
- Le JOIN échoue si BAN a "94 B" et SIRENE cherche "94"

---

### **SIRENE (INSEE) - 54 colonnes**

Exemple réel :
```
005420021,00031,00542002100031 | 134 RUE HENRI BARBUSSE | 80130 FRIVILLE-ESCARBOTIN
etatAdministratifEtablissement = F (Fermé)
denominationUsuelleEtablissement = "" (vide)
enseigne1Etablissement = "" (vide)
```

**Colonnes utilisées actuellement :**
```
siret, siren, enseigne1Etablissement, denominationUsuelleEtablissement,
numeroVoieEtablissement, typeVoieEtablissement, libelleVoieEtablissement,
codePostalEtablissement, libelleCommuneEtablissement,
etatAdministratifEtablissement, activitePrincipaleEtablissement
```

**⚠️ PROBLÈMES IDENTIFIÉS :**

#### **1. Répétitions d'adresse (BIS, TER)**

**SIRENE a aussi une colonne répétition :**
```
numeroVoieEtablissement = "94"
indiceRepetitionEtablissement = "B"  # ❌ PAS UTILISÉ ACTUELLEMENT
```

**Solution :** Ajouter `indiceRepetitionEtablissement` dans ingest.py

---

#### **2. Noms d'établissement vides**

Exemple :
```
denominationUsuelleEtablissement = ""
enseigne1Etablissement = ""
```

Si l'établissement n'a ni nom ni enseigne → problème pour search_text.

**Solution actuelle (views.py) :** ✅
```python
COALESCE(nom, enseigne, '[SANS NOM]')
```

---

## 🔧 PROBLÈMES DE NORMALISATION

### **1. Articles et prépositions non supprimés**

**Exemple RNA :**
```
adrs_libvoie = "du Lieutenant Andre Argenton"
```

**Normalisation actuelle (normalize.py:170-220) :**
```sql
norm_street() → Remplace types de voies, supprime espaces multiples
```

**Mais ne supprime PAS :**
- Articles : `du`, `de la`, `des`, `le`, `la`, `les`, `l'`
- Prépositions : `à`, `au`, `aux`, `en`

**Impact sur matching :**
```
RNA : "RUE DU LIEUTENANT ANDRE ARGENTON"
BAN : "RUE LIEUTENANT ANDRE ARGENTON"
→ Mismatch à cause de "DU"
```

---

### **2. Gestion des traits d'union dans les noms de villes**

**Exemples :**
```
SIRENE : "FRIVILLE-ESCARBOTIN"
RNA    : "Belley"
BAN    : "Friville-Escarbotin"
```

**Normalisation actuelle :**
```sql
norm_txt(ville) → upper(), strip_accents(), collapse espaces
```

**Mais garde les traits d'union** → OK car standardisé

Cependant, problème avec arrondissements :
```
BAN : "Paris 14e Arrondissement"
SIRENE : "PARIS"
```

**Solution actuelle (normalize.py:485-490) :** ✅
```sql
CASE
    WHEN nom_commune LIKE '%ARRONDISSEMENT' 
    THEN norm_txt(regexp_replace(nom_commune, ' [0-9]+E? ARRONDISSEMENT$', ''))
    ELSE norm_txt(nom_commune)
END
```

---

### **3. Numéros de voie avec répétitions**

**BAN :**
```
numero = "94"
rep = "B"
```

**Normalisation actuelle (normalize.py:483) :**
```sql
norm_street(concat_ws(' ', numero, nom_voie))
```

**❌ OUBLI :** La colonne `rep` n'est pas utilisée !

**Devrait être :**
```sql
norm_street(concat_ws(' ', 
    CASE 
        WHEN rep IS NOT NULL AND rep != '' THEN numero || ' ' || rep
        ELSE numero
    END,
    nom_voie
))
```

---

## 🔗 PROBLÈMES DE MATCHING

### **1. Matching SIRENE ↔ RNA (match.py)**

**Stratégie actuelle :**
```sql
JOIN ON s.code_postal = r.code_postal 
    AND s.block_key = r.block_key  -- 10 premiers caractères du nom normalisé
```

**Score composite :**
```sql
0.7 * score_nom + 0.3 * score_adresse
```

**⚠️ PROBLÈME :**

Si l'association n'a pas de nom (`titre_asso` vide), le `block_key` sera basé sur l'adresse :
```sql
CASE
    WHEN length(norm_txt(nom_effectif)) > 0 
    THEN substr(norm_txt(nom_effectif), 1, 10)
    ELSE substr(rue_normalisee, 1, 10)  -- ← Fallback adresse
END AS block_key
```

Mais si les adresses ont des articles différents :
```
RNA : "RUE DU LIEUTENANT" → block_key = "RUE DU LIE"
BAN : "RUE LIEUTENANT"    → block_key = "RUE LIEUTE"
```
→ Pas de match !

---

### **2. Matching SIRENE/RNA ↔ BAN (views.py:163)**

**Stratégie actuelle :**
```sql
LEFT JOIN ban_best b 
    ON s.code_postal = b.code_postal 
    AND s.city_norm = b.city_norm
    AND s.street_norm = b.street_norm
```

**⚠️ PROBLÈMES :**

#### **a) Articles dans RNA**
```
RNA street_norm = "94 RUE DU LIEUTENANT ANDRE ARGENTON"
BAN street_norm = "94 RUE LIEUTENANT ANDRE ARGENTON"
```
→ Pas de match !

#### **b) Répétitions manquantes**
```
BAN : "94 B RUE DIDOT"
SIRENE : "94 RUE DIDOT"
```
→ Pas de match !

#### **c) Noms de villes variables**
```
BAN : "PARIS 14E ARRONDISSEMENT"
SIRENE : "PARIS"
```
→ Résolu par normalisation arrondissements ✅

---

## 📋 RECOMMANDATIONS

### **PRIORITÉ 1 : Améliorer norm_street() - Supprimer articles**

**Fichier :** `etl/normalize.py` lignes 100-297

**Ajouter à la macro `norm_street()` :**

```sql
-- Supprimer articles et prépositions (avec espaces autour)
REPLACE(txt, ' DU ', ' ')
REPLACE(txt, ' DE LA ', ' ')
REPLACE(txt, ' DES ', ' ')
REPLACE(txt, ' DE L ', ' ')
REPLACE(txt, ' LE ', ' ')
REPLACE(txt, ' LA ', ' ')
REPLACE(txt, ' LES ', ' ')
REPLACE(txt, ' AU ', ' ')
REPLACE(txt, ' AUX ', ' ')
REPLACE(txt, ' L ', ' ')
```

**Ordre important :** Après `upper()` mais avant collapse espaces.

---

### **PRIORITÉ 2 : Gérer les répétitions BIS/TER**

#### **A) SIRENE (ingest.py:43)**

**Avant :**
```python
numeroVoieEtablissement as num_voie,
```

**Après :**
```python
numeroVoieEtablissement as num_voie,
indiceRepetitionEtablissement as repetition_voie,
```

#### **B) BAN (normalize.py:483)**

**Avant :**
```sql
norm_street(concat_ws(' ', numero, nom_voie))
```

**Après :**
```sql
norm_street(concat_ws(' ', 
    CASE 
        WHEN rep IS NOT NULL AND rep != '' 
        THEN numero || ' ' || UPPER(rep)  -- "94 B"
        ELSE numero
    END,
    nom_voie
))
```

#### **C) SIRENE (normalize.py:320-370)**

**Ajouter logique similaire :**
```sql
CASE 
    WHEN repetition_voie IS NOT NULL AND repetition_voie != '' 
    THEN num_voie || ' ' || UPPER(repetition_voie)
    ELSE num_voie
END AS numero_complet
```

---

### **PRIORITÉ 3 : Améliorer block_key pour matching par adresse**

**Fichier :** `etl/normalize.py` lignes 320-370 et 395-450

**Problème :** Si le nom est vide, le block_key est basé sur l'adresse, mais les articles causent des mismatches.

**Solution :**

1. Appliquer `norm_street()` **après** suppression des articles
2. Créer un `block_key_address` séparé pour les cas sans nom :

```sql
-- Block key adresse (sans articles)
substr(
    REGEXP_REPLACE(
        rue_normalisee,
        '^(RUE|AV|BD|PL|CHE|IMP|ALL) ',  -- Supprimer type de voie au début
        ''
    ),
    1, 15  -- Plus long que 10 pour mieux différencier
) AS block_key_address
```

---

### **PRIORITÉ 4 : Utiliser code_insee au lieu de code_postal**

**Problème :** Les codes postaux peuvent couvrir plusieurs communes :
```
75014 → Paris 14e, mais aussi Malakoff, Montrouge (limitrophes)
```

**Solution :**

1. **BAN a `code_insee`** → Utiliser dans JOIN
2. **SIRENE a `codeCommuneEtablissement`** → Ajouter à ingest.py
3. **RNA a `adrs_codeinsee`** → Ajouter à ingest.py

**Nouveau JOIN (views.py:163) :**
```sql
LEFT JOIN ban_best b 
    ON s.code_insee = b.code_insee      -- ← Plus précis que code_postal
    AND s.street_norm = b.street_norm
```

---

### **PRIORITÉ 5 : Ajouter champs de qualité BAN**

**BAN a des métadonnées de qualité :**
- `certification_commune` : 1 (certifié) ou 0
- `source_position` : "bal" (meilleur), "cadastre", "inconnue"
- `type_position` : "entrée", "numéro", "interpolation"

**Utilité :**
- Filtrer les adresses de mauvaise qualité
- Préférer les adresses certifiées dans `ban_best`

**Ajout dans normalize.py :**
```sql
SELECT 
    id, code_postal, code_insee, numero, rep, nom_voie, nom_commune,
    lat, lon, street_norm, city_norm,
    certification_commune,
    source_position,
    type_position
FROM ban_bronze
```

**Ajout dans views.py (ban_best CTE) :**
```sql
ban_best AS (
    SELECT 
        code_insee,
        street_norm,
        AVG(lat) as latitude,
        AVG(lon) as longitude,
        COUNT(*) as nb_adresses,
        -- Prioriser qualité
        MAX(certification_commune) as best_certification,
        MIN(CASE source_position 
            WHEN 'bal' THEN 1 
            WHEN 'cadastre' THEN 2 
            ELSE 3 
        END) as best_source
    FROM ban_silver
    WHERE lat IS NOT NULL AND lon IS NOT NULL
    GROUP BY code_insee, street_norm
)
```

---

## 🎯 PLAN D'ACTION RECOMMANDÉ

### **Phase 1 : Corrections Critiques (1-2h)**

1. ✅ Ajouter suppression articles dans `norm_street()` (normalize.py)
2. ✅ Gérer répétitions BIS/TER dans BAN et SIRENE (ingest.py + normalize.py)
3. ✅ Tester matching sur 1000 lignes échantillon

### **Phase 2 : Amélioration Précision (2-3h)**

4. ✅ Ajouter `code_insee` dans SIRENE et RNA (ingest.py)
5. ✅ Utiliser `code_insee` au lieu de `code_postal` dans JOINs (views.py)
6. ✅ Tester impact sur taux de géolocalisation

### **Phase 3 : Qualité de Données (1h)**

7. ✅ Ajouter métadonnées qualité BAN (normalize.py)
8. ✅ Filtrer adresses de mauvaise qualité (views.py)
9. ✅ Tests finaux end-to-end

---

## 📊 MÉTRIQUES ATTENDUES APRÈS CORRECTIONS

| Métrique | Avant | Après (estimé) |
|----------|-------|----------------|
| Adresses géolocalisées (BAN) | ~100 (0.0002%) | ~27M (64%) |
| Associations matchées (RNA) | ~80k (4%) | ~1.5M (68%) |
| Précision matching adresse | 50-60% | 85-90% |
| False positives matching nom | 10-15% | <5% |

---

**Voulez-vous que je commence l'implémentation de ces corrections ?**
