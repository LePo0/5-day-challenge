import { useState } from 'react';
import { Box, TextField, Button, Typography } from '@mui/material';
import { Analytics } from '@mui/icons-material';

function StatsSearch() {
    const [postalCode, setPostalCode] = useState('');

    const handlePostalCodeChange = (e) => {
        const value = e.target.value.replace(/\D/g, '').slice(0, 5);
        setPostalCode(value);
    };

    const handleSearch = () => {
        console.log('Statistiques pour:', postalCode);
    };

    const isValid = postalCode.length === 5;

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Typography variant="h6" gutterBottom>
                Statistiques par Code Postal
            </Typography>

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
                disabled={!isValid}
                onClick={handleSearch}
                startIcon={<Analytics />}
            >
                Voir les Statistiques
            </Button>
        </Box>
    );
}

export default StatsSearch;
