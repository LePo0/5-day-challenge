import { AppBar, Toolbar, Typography, Button } from '@mui/material';
import { CheckCircleOutline } from '@mui/icons-material';
import apiClient from '../api/apiClient';
import useStore from '../store/useStore';
import { useState } from 'react';

function Header() {
    const showToast = useStore((state) => state.showToast);
    const [loading, setLoading] = useState(false);

    const handleCheckServer = () => {
        setLoading(true);
        apiClient.ping()
            .then((data) => {
                showToast('success', `Serveur opérationnel ! Latence: ${data.latency_ms}ms`);
            })
            .catch(() => {
                showToast('error', 'Le serveur ne répond pas. Veuillez vérifier qu\'il est bien démarré.');
            })
            .finally(() => {
                setLoading(false);
            });
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
                <Button
                    variant="contained"
                    color="success"
                    disabled={loading}
                    startIcon={<CheckCircleOutline />}
                    onClick={handleCheckServer}
                >
                    Vérifier l'état du serveur
                </Button>
            </Toolbar>
        </AppBar>
    );
}

export default Header;
