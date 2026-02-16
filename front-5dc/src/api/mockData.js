/**
 * Mock Data pour les tests d'affichage
 * Conforme aux spécifications API v1.0
 */

export const mockData = {
    // Mock pour recherche SIRET - Croix Rouge Française
    siret: {
        "77567227200020": {
            identity: {
                siret: "77567227200020",
                nom_raison_sociale: "CROIX ROUGE FRANCAISE",
                enseigne: null,
                categorie_entreprise: "PME"
            },
            asso_id: {
                id_rna: "W751000060",
                date_publication_jo: "1901-07-01"
            },
            location: {
                numero_voie: "98",
                type_voie: "RUE",
                libelle_voie: "DIDOT",
                code_postal: "75014",
                commune: "PARIS",
                geo_score: 0.98,
                latitude: 48.8296,
                longitude: 2.3235
            }
        },
        // Direction Interministérielle du Numérique
        "13002526500013": {
            identity: {
                siret: "13002526500013",
                nom_raison_sociale: "DIRECTION INTERMINISTERIELLE DU NUMERIQUE",
                enseigne: "DINUM",
                categorie_entreprise: "ETI"
            },
            asso_id: null,
            location: {
                numero_voie: "20",
                type_voie: "AVENUE",
                libelle_voie: "DE SEGUR",
                code_postal: "75007",
                commune: "PARIS",
                geo_score: 0.95,
                latitude: 48.850699,
                longitude: 2.308628
            }
        },
        // Entreprise quelconque
        "85296374100056": {
            identity: {
                siret: "85296374100056",
                nom_raison_sociale: "SAS TENNIS PRO SHOP",
                enseigne: "Tennis Pro",
                categorie_entreprise: "PME"
            },
            asso_id: null,
            location: {
                numero_voie: "42",
                type_voie: "RUE",
                libelle_voie: "REPUBLIQUE",
                code_postal: "69100",
                commune: "VILLEURBANNE",
                geo_score: 0.92,
                latitude: 45.7640,
                longitude: 4.8795
            }
        }
    },

    // Mock pour recherche fuzzy/textuelle
    search: {
        "boulangerie_69": {
            query: "boulangerie",
            filter_dept: "69",
            count: 2,
            results: [
                {
                    siret: "88245100012345",
                    name: "BOULANGERIE DE L HOTEL DE VILLE",
                    is_association: false,
                    city: "LYON"
                },
                {
                    siret: "44312000056789",
                    name: "LA PETITE BOULANGERIE",
                    is_association: false,
                    city: "LYON"
                }
            ]
        },
        "club_tennis_69": {
            query: "club tennis",
            filter_dept: "69",
            count: 3,
            results: [
                {
                    siret: "32165498700012",
                    name: "TENNIS CLUB DE LYON",
                    is_association: true,
                    city: "LYON 5EME"
                },
                {
                    siret: "85296374100056",
                    name: "SAS TENNIS PRO SHOP",
                    is_association: false,
                    city: "VILLEURBANNE"
                },
                {
                    siret: "79845612300098",
                    name: "ASSOCIATION TENNIS CLUB CALUIRE",
                    is_association: true,
                    city: "CALUIRE ET CUIRE"
                }
            ]
        },
        "croix_rouge_75": {
            query: "croix rouge",
            filter_dept: "75",
            count: 5,
            results: [
                {
                    siret: "77567227200020",
                    name: "CROIX ROUGE FRANCAISE",
                    is_association: true,
                    city: "PARIS"
                },
                {
                    siret: "77567227201234",
                    name: "CROIX ROUGE FRANCAISE - DELEGATION LOCALE",
                    is_association: true,
                    city: "PARIS 15EME"
                },
                {
                    siret: "77567227205678",
                    name: "CROIX ROUGE FRANCAISE - SIEGE",
                    is_association: true,
                    city: "PARIS 8EME"
                },
                {
                    siret: "88945612300045",
                    name: "PHARMACIE DE LA CROIX ROUGE",
                    is_association: false,
                    city: "PARIS 11EME"
                },
                {
                    siret: "44556677800099",
                    name: "CROIX ROUGE FORMATION",
                    is_association: false,
                    city: "PARIS 12EME"
                }
            ]
        }
    },

    // Mock pour statistiques
    stats: {
        "33000": {
            zone: "33000",
            total_entites: 15420,
            repartition: {
                entreprises_pures: 14200,
                associations: 1220,
                etablissements_fermes: 3400
            },
            top_naf: {
                code: "56.10A",
                libelle: "Restauration traditionnelle",
                count: 850
            }
        },
        "75013": {
            zone: "75013",
            total_entites: 18730,
            repartition: {
                entreprises_pures: 14502,
                associations: 3200,
                etablissements_fermes: 1028
            },
            top_naf: {
                code: "6201Z",
                libelle: "Programmation informatique",
                count: 1240
            }
        },
        "69001": {
            zone: "69001",
            total_entites: 4250,
            repartition: {
                entreprises_pures: 3800,
                associations: 450,
                etablissements_fermes: 890
            },
            top_naf: {
                code: "47.11F",
                libelle: "Hypermarchés",
                count: 120
            }
        },
        "75015": {
            zone: "75015",
            total_entites: 22340,
            repartition: {
                entreprises_pures: 18500,
                associations: 3840,
                etablissements_fermes: 2150
            },
            top_naf: {
                code: "86.21Z",
                libelle: "Activités hospitalières",
                count: 340
            }
        }
    },

    // Mock pour ping
    ping: {
        status: "ok",
        latency_ms: 12
    }
};

/**
 * Fonction helper pour obtenir des mock data de SIRET
 */
export function getMockSiret(siret) {
    return mockData.siret[siret] || null;
}

/**
 * Fonction helper pour obtenir des mock data de recherche
 * @param {string} query - Terme de recherche
 * @param {string} dept - Code département
 */
export function getMockSearch(query, dept) {
    const key = `${query.toLowerCase().replace(/\s+/g, '_')}_${dept}`;

    // Si on a une correspondance exacte
    if (mockData.search[key]) {
        return mockData.search[key];
    }

    // Sinon, retourner un résultat par défaut basé sur la requête
    return {
        query: query,
        filter_dept: dept,
        count: 0,
        results: []
    };
}

/**
 * Fonction helper pour obtenir des mock data de stats
 */
export function getMockStats(codePostal) {
    return mockData.stats[codePostal] || {
        zone: codePostal,
        total_entites: 0,
        repartition: {
            entreprises_pures: 0,
            associations: 0,
            etablissements_fermes: 0
        },
        top_naf: null
    };
}

export default mockData;
