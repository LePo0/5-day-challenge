/**
 * Client API pour communiquer avec le backend FastAPI
 * Base URL: http://localhost:8000/api/v1
 */

const API_BASE_URL = 'http://localhost:8000/api/v1';

/**
 * Fonction utilitaire pour gérer les appels API
 * @param {string} endpoint - L'endpoint à appeler (sans le préfixe /api/v1)
 * @param {object} options - Options fetch (method, headers, body, etc.)
 * @returns {Promise} - Promesse avec les données JSON
 */
async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;

    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const config = { ...defaultOptions, ...options };

    try {
        const response = await fetch(url, config);

        if (!response.ok) {
            const error = await response.json().catch(() => ({ message: 'Erreur réseau' }));
            throw new Error(error.message || `Erreur HTTP: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error(`Erreur API [${endpoint}]:`, error);
        throw error;
    }
}

/**
 * API Client - Fonctions pour appeler les endpoints
 */
const apiClient = {
    /**
     * Ping - Vérifier l'état du serveur
     * GET /ping
     */
    ping: async () => {
        return apiRequest('/ping');
    },

    /**
     * Recherche par SIRET
     * GET /siret/{siret}
     * @param {string} siret - Numéro SIRET (14 chiffres)
     */
    getSiret: async (siret) => {
        return apiRequest(`/siret/${siret}`);
    },

    /**
     * Recherche fuzzy (textuelle)
     * GET /search?query=...&postal_code=...
     * @param {string} query - Texte de recherche (optionnel)
     * @param {string} postalCode - Code postal (optionnel)
     */
    search: async (query = '', postalCode = '') => {
        const params = new URLSearchParams();
        if (query) params.append('query', query);
        if (postalCode) params.append('postal_code', postalCode);

        return apiRequest(`/search?${params.toString()}`);
    },

    /**
     * Statistiques par code postal
     * GET /stats/{code_postal}
     * @param {string} codePostal - Code postal (5 chiffres)
     */
    getStats: async (codePostal) => {
        return apiRequest(`/stats/${codePostal}`);
    },
};

export default apiClient;
