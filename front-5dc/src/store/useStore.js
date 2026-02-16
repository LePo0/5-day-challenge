import { create } from 'zustand';

/**
 * Store global de l'application
 * Utilise Zustand pour la gestion d'état
 */
const useStore = create((set) => ({
    // État des résultats de recherche
    results: null,
    loading: false,
    searchType: null, // 'siret' | 'fuzzy' | 'stats'
    error: null,

    // État du toaster
    toast: {
        open: false,
        type: 'info', // 'info' | 'success' | 'warning' | 'error'
        children: '',
    },

    // Actions
    setResults: (results) => set({ results, error: null }),
    setLoading: (loading) => set({ loading }),
    setSearchType: (searchType) => set({ searchType }),
    setError: (error) => set({ error, results: null }),

    // Actions toaster
    showToast: (type, children) => set({
        toast: { open: true, type, children }
    }),
    hideToast: () => set((state) => ({
        toast: { ...state.toast, open: false }
    })),

    // Reset complet
    reset: () => set({ results: null, loading: false, searchType: null, error: null }),
}));

export default useStore;
