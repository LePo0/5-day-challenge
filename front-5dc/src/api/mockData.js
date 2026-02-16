/**
 * Mock Data pour les tests d'affichage
 * Conforme aux Exemples 1-5 de l'énoncé (structure de test officielle)
 */

export const mockData = {
    // Mock pour recherche SIRET - Structure selon Exemples 1 & 2
    siret: {
        "77567227200020": {
            siret: "77567227200020",
            rna: "W751000060",  // PREUVE DE LA JOINTURE
            name: "CROIX ROUGE FRANCAISE",
            status: "open",
            nature: "ASSOCIATION",
            address: {
                number: "98",
                street: "RUE DIDOT",
                postal_code: "75014",
                city: "PARIS",
                is_ban_validated: true,
                latitude: 48.8296,
                longitude: 2.3235
            }
        },
        // Direction Interministérielle du Numérique
        "13002526500013": {
            siret: "13002526500013",
            rna: null,
            name: "DIRECTION INTERMINISTERIELLE DU NUMERIQUE",
            status: "open",
            address: {
                number: "20",
                street: "AV DE SEGUR",
                postal_code: "75007",
                city: "PARIS",
                is_ban_validated: true,
                latitude: 48.850699,
                longitude: 2.308628
            }
        },
        // Entreprise quelconque
        "85296374100056": {
            siret: "85296374100056",
            rna: null,
            name: "SAS TENNIS PRO SHOP",
            status: "open",
            address: {
                number: "42",
                street: "RUE REPUBLIQUE",
                postal_code: "69100",
                city: "VILLEURBANNE",
                is_ban_validated: true,
                latitude: 45.7640,
                longitude: 4.8795
            }
        }
    },

    // Mock pour recherche fuzzy/textuelle - Structure selon Exemple 4
    search: {
        "boulangerie_69001": {
            count: 2,
            results: [
                {
                    siret: "88245100012345",
                    name: "BOULANGERIE DE L HOTEL DE VILLE",
                    address_city: "LYON"
                },
                {
                    siret: "44312000056789",
                    name: "LA PETITE BOULANGERIE",
                    address_city: "LYON"
                }
            ]
        },
        "club_tennis_69001": {
            count: 2,
            results: [
                {
                    siret: "32165498700012",
                    name: "TENNIS CLUB DE LYON",
                    address_city: "LYON"
                },
                {
                    siret: "85296374100056",
                    name: "SAS TENNIS PRO SHOP",
                    address_city: "VILLEURBANNE"
                }
            ]
        },
        "croix_rouge_75014": {
            count: 3,
            results: [
                {
                    siret: "77567227200020",
                    name: "CROIX ROUGE FRANCAISE",
                    address_city: "PARIS"
                },
                {
                    siret: "77567227201234",
                    name: "CROIX ROUGE FRANCAISE - DELEGATION LOCALE",
                    address_city: "PARIS"
                },
                {
                    siret: "88945612300045",
                    name: "PHARMACIE DE LA CROIX ROUGE",
                    address_city: "PARIS"
                }
            ]
        }
    },

    // Mock pour statistiques - Structure selon Exemple 5
    stats: {
        "75013": {
            postal_code: "75013",
            total_active_companies: 14502,
            total_associations: 3200,
            top_activity: "6201Z"
        },
        "33000": {
            postal_code: "33000",
            total_active_companies: 14200,
            total_associations: 1220,
            top_activity: "56.10A"
        },
        "69001": {
            postal_code: "69001",
            total_active_companies: 3800,
            total_associations: 450,
            top_activity: "47.11F"
        },
        "75015": {
            postal_code: "75015",
            total_active_companies: 18500,
            total_associations: 3840,
            top_activity: "86.21Z"
        }
    },
    // Mock pour ping
    ping: {
        status: "ok"
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
 * @param {string} postalCode - Code postal complet (5 chiffres)
 */
export function getMockSearch(query, postalCode) {
    const key = `${query.toLowerCase().replace(/\s+/g, '_')}_${postalCode}`;

    // Si on a une correspondance exacte
    if (mockData.search[key]) {
        return mockData.search[key];
    }

    // Sinon, retourner un résultat vide
    return {
        count: 0,
        results: []
    };
}

/**
 * Fonction helper pour obtenir des mock data de stats
 */
export function getMockStats(codePostal) {
    return mockData.stats[codePostal] || {
        postal_code: codePostal,
        total_active_companies: 0,
        total_associations: 0,
        top_activity: null
    };
}

export default mockData;
