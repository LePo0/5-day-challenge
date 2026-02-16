import { useState } from 'react';
import { Box, TextField, Button, Typography } from '@mui/material';
import { Search } from '@mui/icons-material';

function SiretSearch() {
    const [siret, setSiret] = useState('');

    const handleSiretChange = (e) => {
        const value = e.target.value.replace(/\D/g, '').slice(0, 14);
        setSiret(value);
    };

    const handleSearch = () => {
        console.log('Recherche SIRET:', siret);
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
                disabled={!isValid}
                onClick={handleSearch}
                startIcon={<Search />}
            >
                Rechercher
            </Button>
        </Box>
    );
}

export default SiretSearch;
