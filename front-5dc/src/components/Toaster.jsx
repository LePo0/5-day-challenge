import { Snackbar, Alert } from '@mui/material';
import useStore from '../store/useStore';

/**
 * Composant Toaster pour afficher des notifications
 * Types: info, success, warning, error
 */
function Toaster() {
    const toast = useStore((state) => state.toast);
    const hideToast = useStore((state) => state.hideToast);

    const handleClose = (event, reason) => {
        if (reason === 'clickaway') {
            return;
        }
        hideToast();
    };

    return (
        <Snackbar
            open={toast.open}
            autoHideDuration={6000}
            onClose={handleClose}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
            <Alert
                onClose={handleClose}
                severity={toast.type || 'info'}
                variant="filled"
                sx={{ width: '100%' }}
            >
                {toast.children}
            </Alert>
        </Snackbar>
    );
}

export default Toaster;
