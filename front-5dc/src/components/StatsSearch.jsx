import { useState } from 'react';
import { Box, TextField, Button, Typography, Alert, Chip } from '@mui/material';
import { Analytics } from '@mui/icons-material';
import useStore from '../store/useStore';
import apiClient from '../api/apiClient';
import mockApiClient from '../api/mockApiClient';

function StatsSearch() {
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
        setSearchType('stats');
        setLoading(true);
        setError(null);

        try {
            const client = mockMode ? mockApiClient : apiClient;
            const data = await client.getStats(postalCode);
            setResults(data);
            showToast('success', `Statistiques récupérées pour le code postal ${postalCode}`);
        } catch (error) {
            setError(error.message);
            showToast('error', `Erreur: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    const isValid = postalCode.length === 5;

    // Codes postaux disponibles en mode mock
    const mockPostalCodes = [
        { code: '33000', label: 'Bordeaux Centre' },
        { code: '75013', label: 'Paris 13ème' },
        { code: '69001', label: 'Lyon 1er' },
        { code: '75015', label: 'Paris 15ème' }
    ];

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Typography variant="h6" gutterBottom>
                Statistiques par Code Postal
            </Typography>

            {mockMode && (
                <Alert severity="info" sx={{ borderRadius: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                        Mode Mock - Codes postaux disponibles :
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                        {mockPostalCodes.map(({ code, label }) => (
                            <Chip
                                key={code}
                                label={`${label} (${code})`}
                                size="small"
                                clickable
                                onClick={() => setPostalCode(code)}
                                color={postalCode === code ? 'primary' : 'default'}
                            />
                        ))}
                    </Box>
                </Alert>
            )}

            <TextField
                fullWidth
                label="Code Postal (5 chiffres)"
                value={postalCode}
                onChange={handlePostalCodeChange}
                placeholder="75015"
                helperText={`${postalCode.length}/5 chiffres`}
                error={postalCode.length > 0 && postalCode.length !== 5}
            />

            <Button
                variant="contained"
                size="large"
                fullWidth
                disabled={!isValid || loading}
                onClick={handleSearch}
                startIcon={<Analytics />}
            >
                {loading ? 'Chargement...' : 'Voir les Statistiques'}
            </Button>
        </Box>
    );
}

export default StatsSearch;
