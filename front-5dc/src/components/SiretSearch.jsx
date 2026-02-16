import { useState } from 'react';
import { Box, TextField, Button, Typography, Alert, Chip } from '@mui/material';
import { Search } from '@mui/icons-material';
import useStore from '../store/useStore';
import apiClient from '../api/apiClient';
import mockApiClient from '../api/mockApiClient';

function SiretSearch() {
    const [siret, setSiret] = useState('');
    const setResults = useStore((state) => state.setResults);
    const setLoading = useStore((state) => state.setLoading);
    const setSearchType = useStore((state) => state.setSearchType);
    const setError = useStore((state) => state.setError);
    const showToast = useStore((state) => state.showToast);
    const loading = useStore((state) => state.loading);
    const mockMode = useStore((state) => state.mockMode);

    const handleSiretChange = (e) => {
        const value = e.target.value.replace(/\D/g, '').slice(0, 14);
        setSiret(value);
    };

    const handleSearch = async () => {
        setSearchType('siret');
        setLoading(true);
        setError(null);

        try {
            const client = mockMode ? mockApiClient : apiClient;
            const data = await client.getSiret(siret);
            setResults(data);
            showToast('success', `Résultat trouvé pour le SIRET ${siret}`);
        } catch (error) {
            setError(error.message);
            showToast('error', `Erreur: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    const isValid = siret.length === 14;

    // SIRET disponibles en mode mock
    const mockSirets = [
        { siret: '77567227200020', label: 'Croix Rouge Française (Association)' },
        { siret: '13002526500013', label: 'DINUM' },
        { siret: '85296374100056', label: 'SAS Tennis Pro Shop' }
    ];

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Typography variant="h6" gutterBottom>
                Recherche par SIRET
            </Typography>

            {mockMode && (
                <Alert severity="info" sx={{ borderRadius: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                        Mode Mock - SIRET disponibles :
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                        {mockSirets.map(({ siret: mockSiret, label }) => (
                            <Chip
                                key={mockSiret}
                                label={`${label} (${mockSiret})`}
                                size="small"
                                clickable
                                onClick={() => setSiret(mockSiret)}
                                color={siret === mockSiret ? 'primary' : 'default'}
                            />
                        ))}
                    </Box>
                </Alert>
            )}

            <TextField
                fullWidth
                label="SIRET (14 chiffres)"
                value={siret}
                onChange={handleSiretChange}
                placeholder="77567227200020"
                helperText={`${siret.length}/14 chiffres`}
                error={siret.length > 0 && siret.length !== 14}
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

export default SiretSearch;
