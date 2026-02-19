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
            // Extract department code (first 2 digits) from postal code
            const dept = postalCode.length >= 2 ? postalCode.substring(0, 2) : '';
            const client = mockMode ? mockApiClient : apiClient;
            const data = await client.search(query, dept);
            setResults(data);
            showToast('success', `${data.count || 0} résultat(s) trouvé(s)`);
        } catch (error) {
            setError(error.message);
            showToast('error', `Erreur: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    const isValid = query.trim() !== '' || postalCode !== '';

    // Exemples disponibles en mode mock
    const mockExamples = [
        { query: 'boulangerie', dept: '69', label: 'Boulangeries Rhône' },
        { query: 'club tennis', dept: '69', label: 'Clubs Tennis Rhône' },
        { query: 'croix rouge', dept: '75', label: 'Croix Rouge Paris' }
    ];

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Typography variant="h6">
                Recherche Textuelle
            </Typography>

            <Alert severity="info" sx={{ borderRadius: 2 }}>
                <Typography variant="subtitle1">
                    Au moins un champ doit être rempli.
                </Typography>
                <Typography variant="subtitle1">
                    Retourne 10 résultats maximum, triés par pertinence.
                </Typography>
            </Alert>

            {mockMode && (
                <Alert severity="info" sx={{ borderRadius: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                        Mode Mock - Exemples disponibles :
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                        {mockExamples.map(({ query: q, dept, label }) => (
                            <Chip
                                key={`${q}-${dept}`}
                                label={label}
                                size="small"
                                clickable
                                onClick={() => {
                                    setQuery(q);
                                    setPostalCode(dept + '000');
                                }}
                                color={query === q ? 'primary' : 'default'}
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
            />

            <TextField
                fullWidth
                label="Code Postal"
                value={postalCode}
                onChange={handlePostalCodeChange}
                placeholder="75015"
                helperText={postalCode ? `${postalCode.length}/5 chiffres` : 'Optionnel'}
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
