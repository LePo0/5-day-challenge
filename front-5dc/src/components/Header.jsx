import { AppBar, Toolbar, Typography, Button } from '@mui/material';
import { CheckCircleOutline } from '@mui/icons-material';

function Header() {
    const handleCheckServer = () => {
        console.log('Vérification du serveur...');
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
                    startIcon={<CheckCircleOutline />}
                    onClick={handleCheckServer}
                // sx={{
                //     bgcolor: 'rgba(255, 255, 255, 0.2)',
                //     '&:hover': {
                //         bgcolor: 'rgba(255, 255, 255, 0.3)',
                //     },
                // }}
                >
                    Vérifier l'état du serveur
                </Button>
            </Toolbar>
        </AppBar>
    );
}

export default Header;
