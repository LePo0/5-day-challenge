import { Box, Paper, Typography, CircularProgress, Card, CardContent, Grid, Divider, Chip, Alert, Tabs, Tab } from '@mui/material';
import { LocationOn, Business, Group, Phone, Email, Code } from '@mui/icons-material';
import { useState } from 'react';
import JsonView from '@uiw/react-json-view';
import { vscodeTheme } from '@uiw/react-json-view/vscode';
import useStore from '../store/useStore';

function ResultsArea() {
    const results = useStore((state) => state.results);
    const loading = useStore((state) => state.loading);
    const searchType = useStore((state) => state.searchType);
    const error = useStore((state) => state.error);
    const [viewMode, setViewMode] = useState(0); // 0 = formatted, 1 = JSON

    // Affichage pour la recherche SIRET (résultat unique) - Structure Exemples 1-2
    const renderSiretResult = () => {
        if (!results) return null;

        return (
            <Card variant="outlined" sx={{ mt: 2 }}>
                <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 2 }}>
                        <Typography variant="h5" fontWeight="bold">
                            {results.name || 'N/A'}
                        </Typography>
                        <Chip
                            label={results.address?.postal_code || 'N/A'}
                            color="primary"
                            size="small"
                        />
                    </Box>

                    <Typography variant="body2" color="text.secondary" gutterBottom>
                        SIRET: {results.siret || 'N/A'}
                    </Typography>

                    <Typography variant="body2" color="text.secondary" gutterBottom>
                        Statut: {results.status || 'N/A'}
                    </Typography>

                    {results.rna && (
                        <Chip
                            label={`RNA: ${results.rna}`}
                            color="success"
                            size="small"
                            sx={{ mt: 1, mb: 2 }}
                        />
                    )}

                    {results.nature && (
                        <Chip
                            label={results.nature}
                            color="info"
                            size="small"
                            sx={{ mt: 1, mb: 2, ml: 1 }}
                        />
                    )}

                    <Divider sx={{ my: 2 }} />

                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                        {results.address && (
                            <>
                                <Box sx={{ display: 'flex', alignItems: 'start', gap: 1 }}>
                                    <LocationOn fontSize="small" color="primary" />
                                    <Typography variant="body2">
                                        {results.address.number} {results.address.street}
                                        {results.address.postal_code && results.address.city &&
                                            `, ${results.address.postal_code} ${results.address.city}`
                                        }
                                    </Typography>
                                </Box>

                                {results.address.latitude && results.address.longitude && (
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <LocationOn fontSize="small" color="secondary" />
                                        <Typography variant="body2">
                                            GPS: {results.address.latitude}, {results.address.longitude}
                                        </Typography>
                                    </Box>
                                )}

                                {results.address.is_ban_validated && (
                                    <Chip
                                        label="Adresse validée BAN"
                                        color="success"
                                        variant="outlined"
                                        size="small"
                                        sx={{ alignSelf: 'flex-start' }}
                                    />
                                )}
                            </>
                        )}
                    </Box>
                </CardContent>
            </Card>
        );
    };

    // Affichage pour la recherche fuzzy (liste de résultats) - Structure Exemple 4
    const renderFuzzyResults = () => {
        if (!results || !results.results || results.results.length === 0) return null;

        return (
            <>
                <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                        Total: {results.count || 0} résultat(s)
                    </Typography>
                </Box>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                    {results.results.map((result, index) => (
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
                                        {result.name}
                                    </Typography>
                                    <Chip label={result.siret} color="primary" size="small" />
                                </Box>

                                {result.address_city && (
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                                        <LocationOn fontSize="small" color="action" />
                                        <Typography variant="body2">
                                            {result.address_city}
                                        </Typography>
                                    </Box>
                                )}
                            </CardContent>
                        </Card>
                    ))}
                </Box>
            </>
        );
    };

    // Affichage pour les statistiques - Structure Exemple 5
    const renderStats = () => {
        if (!results) return null;

        return (
            <Box sx={{ mt: 2 }}>
                {/* En-tête avec code postal */}
                <Card variant="outlined" sx={{ mb: 3, p: 3, textAlign: 'center' }}>
                    <Typography variant="overline" color="text.secondary">
                        Code Postal
                    </Typography>
                    <Typography variant="h4" fontWeight="bold" color="primary" gutterBottom>
                        {results.postal_code}
                    </Typography>
                </Card>

                {/* Statistiques principales */}
                <Grid container spacing={2} sx={{ mb: 3 }}>
                    <Grid item xs={12} sm={6}>
                        <Card variant="outlined">
                            <CardContent sx={{ textAlign: 'center', py: 3 }}>
                                <Business color="primary" sx={{ fontSize: 42, mb: 1 }} />
                                <Typography variant="h4" fontWeight="bold">
                                    {results.total_active_companies?.toLocaleString() || 0}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    Entreprises actives
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <Card variant="outlined">
                            <CardContent sx={{ textAlign: 'center', py: 3 }}>
                                <Group color="success" sx={{ fontSize: 42, mb: 1 }} />
                                <Typography variant="h4" fontWeight="bold">
                                    {results.total_associations?.toLocaleString() || 0}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    Associations
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>

                {/* Activité principale */}
                {results.top_activity && (
                    <Card variant="outlined">
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                Activité principale
                            </Typography>
                            <Divider sx={{ my: 2 }} />
                            <Typography variant="body1" fontWeight="medium">
                                {results.top_activity}
                            </Typography>
                        </CardContent>
                    </Card>
                )}
            </Box>
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
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">
                    Résultats
                    {searchType === 'fuzzy' && results && results.count > 0 && ` (${results.count})`}
                </Typography>

                {results && !loading && (
                    <Tabs value={viewMode} onChange={(e, newValue) => setViewMode(newValue)}>
                        <Tab label="Vue formatée" />
                        <Tab label="JSON" icon={<Code />} iconPosition="start" />
                    </Tabs>
                )}
            </Box>

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
                    gap: 2,
                    minHeight: 400
                }}>
                    <Typography variant="body1" color="text.secondary">
                        Aucune recherche effectuée
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        Utilisez le formulaire de recherche pour voir les résultats
                    </Typography>
                </Box>
            )}

            {!loading && results && !error && (
                <>
                    {viewMode === 0 ? (
                        <>
                            {searchType === 'siret' && renderSiretResult()}

                            {searchType === 'fuzzy' && (
                                (!results.results || results.results.length === 0) ? (
                                    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
                                        <Typography variant="body1" color="text.secondary">
                                            Aucun résultat trouvé
                                        </Typography>
                                    </Box>
                                ) : (
                                    renderFuzzyResults()
                                )
                            )}

                            {searchType === 'stats' && renderStats()}
                        </>
                    ) : (
                        <Box sx={{ mt: 2 }}>
                            <JsonView value={results} style={vscodeTheme} />
                        </Box>
                    )}
                </>
            )}
        </Paper>
    );
}

export default ResultsArea;
