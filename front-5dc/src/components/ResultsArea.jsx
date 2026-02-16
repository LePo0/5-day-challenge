import { Box, Paper, Typography, CircularProgress, Card, CardContent, Grid, Divider, Chip, Alert } from '@mui/material';
import { LocationOn, Business, Group, Phone, Email } from '@mui/icons-material';
import useStore from '../store/useStore';

function ResultsArea() {
    const results = useStore((state) => state.results);
    const loading = useStore((state) => state.loading);
    const searchType = useStore((state) => state.searchType);
    const error = useStore((state) => state.error);
    // Affichage pour la recherche SIRET (résultat unique)
    const renderSiretResult = () => {
        if (!results) return null;

        return (
            <Card variant="outlined" sx={{ mt: 2 }}>
                <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 2 }}>
                        <Typography variant="h5" fontWeight="bold">
                            {results.denomination || 'N/A'}
                        </Typography>
                        <Chip
                            label={results.code_postal || 'N/A'}
                            color="primary"
                            size="small"
                        />
                    </Box>

                    <Typography variant="body2" color="text.secondary" gutterBottom>
                        SIRET: {results.siret}
                    </Typography>

                    <Divider sx={{ my: 2 }} />

                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                        {results.adresse && (
                            <Box sx={{ display: 'flex', alignItems: 'start', gap: 1 }}>
                                <LocationOn fontSize="small" color="primary" />
                                <Typography variant="body2">
                                    {results.adresse}
                                    {results.code_postal && results.commune &&
                                        `, ${results.code_postal} ${results.commune}`
                                    }
                                </Typography>
                            </Box>
                        )}

                        {results.activite_principale && (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Business fontSize="small" color="primary" />
                                <Typography variant="body2">
                                    Activité: {results.activite_principale}
                                </Typography>
                            </Box>
                        )}

                        {results.categorie && (
                            <Chip
                                label={results.categorie}
                                variant="outlined"
                                size="small"
                                sx={{ alignSelf: 'flex-start', mt: 1 }}
                            />
                        )}
                    </Box>
                </CardContent>
            </Card>
        );
    };

    // Affichage pour la recherche fuzzy (liste de résultats)
    const renderFuzzyResults = () => {
        if (!results || results.length === 0) return null;

        return (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                {results.map((result, index) => (
                    <Card key={index} variant="outlined" sx={{
                        transition: 'all 0.2s',
                        '&:hover': {
                            boxShadow: 3,
                            transform: 'translateY(-2px)'
                        }
                    }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 1 }}>
                                <Typography variant="subtitle1" fontWeight="bold">
                                    {result.denomination}
                                </Typography>
                                <Chip label={result.code_postal || 'N/A'} size="small" />
                            </Box>

                            <Typography variant="body2" color="text.secondary" gutterBottom>
                                SIRET: {result.siret}
                            </Typography>

                            {result.adresse && (
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                                    <LocationOn fontSize="small" color="action" />
                                    <Typography variant="body2">
                                        {result.adresse}
                                    </Typography>
                                </Box>
                            )}

                            {result.score && (
                                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                                    Score de pertinence: {result.score}%
                                </Typography>
                            )}
                        </CardContent>
                    </Card>
                ))}
            </Box>
        );
    };

    // Affichage pour les statistiques
    const renderStats = () => {
        if (!results) return null;

        return (
            <Grid container spacing={3} sx={{ mt: 2 }}>
                <Grid item xs={12} sm={6}>
                    <Card sx={{
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        color: 'white',
                        height: '100%'
                    }}>
                        <CardContent sx={{ textAlign: 'center', py: 4 }}>
                            <Business sx={{ fontSize: 64, mb: 2, opacity: 0.9 }} />
                            <Typography variant="h2" fontWeight="bold" gutterBottom>
                                {results.nb_entreprises || 0}
                            </Typography>
                            <Typography variant="h6">
                                Entreprises
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} sm={6}>
                    <Card sx={{
                        background: 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
                        color: 'white',
                        height: '100%'
                    }}>
                        <CardContent sx={{ textAlign: 'center', py: 4 }}>
                            <Group sx={{ fontSize: 64, mb: 2, opacity: 0.9 }} />
                            <Typography variant="h2" fontWeight="bold" gutterBottom>
                                {results.nb_associations || 0}
                            </Typography>
                            <Typography variant="h6">
                                Associations
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                {results.code_postal && (
                    <Grid item xs={12}>
                        <Card variant="outlined">
                            <CardContent>
                                <Typography variant="body1" align="center" color="text.secondary">
                                    Statistiques pour le code postal: <strong>{results.code_postal}</strong>
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                )}
            </Grid>
        );
    };

    return (
        <Paper elevation={2} sx={{
            p: 3,
            height: '100%',
            width: '100%',
            overflow: 'auto',
            display: 'flex',
            flexDirection: 'column'
        }}>
            <Typography variant="h6" gutterBottom>
                Résultats
                {searchType === 'fuzzy' && results && results.length > 0 && ` (${results.length})`}
            </Typography>

            {error && (
                <Alert severity="error" sx={{ mt: 2 }}>
                    {error}
                </Alert>
            )}

            {loading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
                    <CircularProgress size={60} />
                </Box>
            )}

            {!loading && !results && !error && (
                <Box sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'center',
                    alignItems: 'center',
                    gap: 2
                }}>
                    <Typography variant="body1" color="text.secondary">
                        Aucune recherche effectuée
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        Utilisez le formulaire de recherche pour voir les résultats
                    </Typography>
                </Box>
            )}

            {!loading && results && searchType === 'siret' && renderSiretResult()}

            {!loading && results && searchType === 'fuzzy' && (
                results.length === 0 ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
                        <Typography variant="body1" color="text.secondary">
                            Aucun résultat trouvé
                        </Typography>
                    </Box>
                ) : (
                    renderFuzzyResults()
                )
            )}

            {!loading && results && searchType === 'stats' && renderStats()}
        </Paper>
    );
}

export default ResultsArea;
