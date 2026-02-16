import { useState } from 'react';
import { Box, TextField, Button, Typography } from '@mui/material';
import { Search } from '@mui/icons-material';
import useStore from '../store/useStore';
import apiClient from '../api/apiClient';

function SiretSearch() {
    const [siret, setSiret] = useState('');
    const setResults = useStore((state) => state.setResults);
    const setLoading = useStore((state) => state.setLoading);
    const setSearchType = useStore((state) => state.setSearchType);
    const setError = useStore((state) => state.setError);
    const showToast = useStore((state) => state.showToast);
    const loading = useStore((state) => state.loading);

    const handleSiretChange = (e) => {
        const value = e.target.value.replace(/\D/g, '').slice(0, 14);
        setSiret(value);
    };

    const handleSearch = async () => {
        setSearchType('siret');
        setLoading(true);
        setError(null);

        try {
            const data = await apiClient.getSiret(siret);
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

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Typography variant="h6" gutterBottom>
                Recherche par SIRET
            </Typography>

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
