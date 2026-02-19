import { createTheme } from '@mui/material/styles';

export const darkTheme = createTheme({
    palette: {
        mode: 'dark',
        primary: {
            main: '#667eea',
            light: '#8094f0',
            dark: '#5568d3',
        },
        secondary: {
            main: '#764ba2',
            light: '#9166b8',
            dark: '#5e3c82',
        },
        background: {
            default: '#0a0e27',
            paper: '#1a1f3a',
        },
        text: {
            primary: '#ffffff',
            secondary: '#b0b8d4',
        },
    },
    typography: {
        fontFamily: '"Inter", "Segoe UI", "Roboto", sans-serif',
        h4: {
            fontWeight: 700,
        },
        button: {
            textTransform: 'none',
            fontWeight: 600,
        },
    },
    components: {
        MuiButton: {
            styleOverrides: {
                root: {
                    borderRadius: 8,
                    padding: '10px 24px',
                },
            },
        },
        MuiTextField: {
            styleOverrides: {
                root: {
                    '& .MuiOutlinedInput-root': {
                        borderRadius: 8,
                    },
                },
            },
        },
        MuiPaper: {
            styleOverrides: {
                root: {
                    borderRadius: 12,
                    backgroundImage: 'none',
                },
            },
        },
        MuiTab: {
            styleOverrides: {
                root: {
                    textTransform: 'none',
                    fontWeight: 600,
                    fontSize: '1rem',
                },
            },
        },
    },
});
