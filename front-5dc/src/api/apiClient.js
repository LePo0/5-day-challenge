/**
 * Client API pour communiquer avec le backend FastAPI
 * Base URL: http://localhost:8000/api/v1
 */

const API_BASE_URL = 'http://20.199.77.191:8000/api/v1';

/**
 * Fonction utilitaire pour gérer les appels API
 * @param {string} endpoint - L'endpoint à appeler (sans le préfixe /api/v1)
 * @param {object} options - Options fetch (method, headers, body, etc.)
 * @param {number} timeout - Timeout en millisecondes (défaut: 10000ms)
 * @returns {Promise} - Promesse avec les données JSON
 */
async function apiRequest(endpoint, options = {}, timeout = 10000) {
    const url = `${API_BASE_URL}${endpoint}`;

    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const config = { ...defaultOptions, ...options };

    // Création d'un AbortController pour le timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    config.signal = controller.signal;

    try {
        const response = await fetch(url, config);
        clearTimeout(timeoutId);

        if (!response.ok) {
            const error = await response.json().catch(() => ({ message: 'Erreur réseau' }));
            throw new Error(error.message || `Erreur HTTP: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        clearTimeout(timeoutId);

        if (error.name === 'AbortError') {
            console.error(`Timeout API [${endpoint}]: Le serveur ne répond pas`);
            throw new Error('Le serveur ne répond pas. Veuillez vérifier qu\'il est bien démarré.');
        }

        if (error.message.includes('fetch')) {
            console.error(`Erreur de connexion [${endpoint}]:`, error);
            throw new Error('Impossible de se connecter au serveur. Vérifiez qu\'il est démarré');
        }

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
     * GET /search?q=...&dept=...
     * @param {string} query - Texte de recherche (optionnel)
     * @param {string} dept - Code département (optionnel)
     */
    search: async (query = '', dept = '') => {
        const params = new URLSearchParams();
        if (query) params.append('q', query);
        if (dept) params.append('dept', dept);

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
