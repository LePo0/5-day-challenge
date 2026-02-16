/**
 * Mock API Client pour les tests d'affichage
 * Simule les réponses de l'API avec un délai réaliste
 */

import { getMockSiret, getMockSearch, getMockStats, mockData } from './mockData';

/**
 * Simule un délai réseau
 * @param {number} ms - Délai en millisecondes (défaut: 300-800ms)
 */
const simulateDelay = (ms = Math.random() * 500 + 300) => {
    return new Promise(resolve => setTimeout(resolve, ms));
};

/**
 * Mock API Client - Fonctions simulées
 */
const mockApiClient = {
    /**
     * Ping - Vérifier l'état du serveur (mock)
     */
    ping: async () => {
        await simulateDelay(50);
        return mockData.ping;
    },

    /**
     * Recherche par SIRET (mock)
     * @param {string} siret - Numéro SIRET (14 chiffres)
     */
    getSiret: async (siret) => {
        await simulateDelay();
        const result = getMockSiret(siret);

        if (!result) {
            throw new Error(`SIRET ${siret} non trouvé dans les données mock`);
        }

        return result;
    },

    /**
     * Recherche fuzzy (mock)
     * @param {string} query - Texte de recherche
     * @param {string} postalCode - Code postal complet
     */
    search: async (query = '', postalCode = '') => {
        await simulateDelay();
        return getMockSearch(query, postalCode);
    },

    /**
     * Statistiques par code postal (mock)
     * @param {string} codePostal - Code postal (5 chiffres)
     */
    getStats: async (codePostal) => {
        await simulateDelay();
        return getMockStats(codePostal);
    },
};

export default mockApiClient;
