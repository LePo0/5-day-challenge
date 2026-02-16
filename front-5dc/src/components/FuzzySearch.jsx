import { useState } from 'react';
import { Box, TextField, Button, Typography, Alert, Chip } from '@mui/material';
import { Search } from '@mui/icons-material';
import useStore from '../store/useStore';
import apiClient from '../api/apiClient';
import mockApiClient from '../api/mockApiClient';

function FuzzySearch() {
    const [query, setQuery] = useState('');
    const [postalCode, setPostalCode] = useState('');
    const setResults = useStore((state) => state.setResults);
    const setLoading = useStore((state) => state.setLoading);
    const setSearchType = useStore((state) => state.setSearchType);
    const setError = useStore((state) => state.setError);
    const showToast = useStore((state) => state.showToast);
    const loading = useStore((state) => state.loading);
    const mockMode = useStore((state) => state.mockMode);

    const handlePostalCodeChange = (e) => {
        const value = e.target.value.replace(/\D/g, '').slice(0, 5);
        setPostalCode(value);
    };

    const handleSearch = async () => {
        setSearchType('fuzzy');
        setLoading(true);
        setError(null);

        try {
            const client = mockMode ? mockApiClient : apiClient;
            const data = await client.search(query, postalCode);
            setResults(data);
            showToast('success', `${data.count || 0} résultat(s) trouvé(s)`);
        } catch (error) {
            setError(error.message);
            showToast('error', `Erreur: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    const isValid = query.trim() !== '';

    // Exemples disponibles en mode mock
    const mockExamples = [
        { query: 'boulangerie', postalCode: '69001', label: 'Boulangeries Lyon' },
        { query: 'club tennis', postalCode: '69001', label: 'Clubs Tennis Lyon' },
        { query: 'croix rouge', postalCode: '75014', label: 'Croix Rouge Paris' }
    ];

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Typography variant="h6">
                Recherche Textuelle
            </Typography>

            <Alert severity="info" sx={{ borderRadius: 2 }}>
                <Typography variant="subtitle1">
                    Le texte de recherche est obligatoire.
                </Typography>
                <Typography variant="subtitle1">
                    Le code postal est optionnel (filtre géographique).
                </Typography>
            </Alert>

            {mockMode && (
                <Alert severity="info" sx={{ borderRadius: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                        Mode Mock - Exemples disponibles :
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                        {mockExamples.map(({ query: q, postalCode: pc, label }) => (
                            <Chip
                                key={`${q}-${pc}`}
                                label={label}
                                size="small"
                                clickable
                                onClick={() => {
                                    setQuery(q);
                                    setPostalCode(pc);
                                }}
                                color={query === q && postalCode === pc ? 'primary' : 'default'}
                            />
                        ))}
                    </Box>
                </Alert>
            )}

            <TextField
                fullWidth
                label="Texte de recherche (ex: nom d'entreprise)"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Croix Rouge, Carrefour..."
                required
                error={query.trim() === '' && query.length > 0}
                helperText="Obligatoire - Recherche dans les noms d'entreprises"
            />

            <TextField
                fullWidth
                label="Code Postal (optionnel)"
                value={postalCode}
                onChange={handlePostalCodeChange}
                placeholder="75015"
                helperText={postalCode ? `${postalCode.length}/5 chiffres` : 'Optionnel - Filtre géographique'}
            />

            <Button
                variant="contained"
                size="large"
                fullWidth
                disabled={!isValid || loading}
                onClick={handleSearch}
                startIcon={<Search />}
            >
                {loading ? 'Recherche...' : 'Rechercher'}
            </Button>
        </Box>
    );
}

export default FuzzySearch;
