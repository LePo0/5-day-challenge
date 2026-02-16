import { AppBar, Toolbar, Typography, Button, Box, Switch, FormControlLabel, Chip } from '@mui/material';
import { CheckCircleOutline, Science } from '@mui/icons-material';
import apiClient from '../api/apiClient';
import useStore from '../store/useStore';
import { useState } from 'react';

function Header() {
    const showToast = useStore((state) => state.showToast);
    const mockMode = useStore((state) => state.mockMode);
    const toggleMockMode = useStore((state) => state.toggleMockMode);
    const [loading, setLoading] = useState(false);

    const handleCheckServer = async () => {
        setLoading(true);
        try {
            const data = await apiClient.ping();
            showToast('success', `Serveur opérationnel ! Status: ${data.status || 'OK'}`);
        } catch (error) {
            showToast('error', 'Le serveur ne répond pas. Veuillez vérifier qu\'il est bien démarré sur http://localhost:8000');
        } finally {
            setLoading(false);
        }
    };

    const handleToggleMock = () => {
        toggleMockMode();
        showToast('info', mockMode ? 'Mode API réelle activé' : 'Mode Mock activé - Données de test');
    };

    return (
        <AppBar position="static" elevation={0} sx={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            mb: 4,

        }}>
            <Toolbar sx={{ justifyContent: 'space-between', py: 2 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 700 }}>
                    ETL 5 Day Challenge
                </Typography>
                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                    <FormControlLabel
                        control={
                            <Switch
                                checked={mockMode}
                                onChange={handleToggleMock}
                                sx={{
                                    '& .MuiSwitch-switchBase.Mui-checked': {
                                        color: '#ffa726',
                                    },
                                    '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                                        backgroundColor: '#ffa726',
                                    },
                                }}
                            />
                        }
                        label={
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Science fontSize="small" />
                                <Typography variant="body2" sx={{ color: 'white' }}>
                                    Mode Mock
                                </Typography>
                                {mockMode && <Chip label="TEST" size="small" color="warning" />}
                            </Box>
                        }
                        sx={{ mr: 2, color: 'white' }}
                    />
                    <Button
                        variant="contained"
                        color="success"
                        disabled={loading || mockMode}
                        startIcon={<CheckCircleOutline />}
                        onClick={handleCheckServer}
                    >
                        Vérifier le serveur
                    </Button>
                </Box>
            </Toolbar>
        </AppBar>
    );
}

export default Header;
