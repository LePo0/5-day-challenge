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

    // Affichage pour la recherche SIRET (résultat unique)
    const renderSiretResult = () => {
        if (!results) return null;

        const { identity, asso_id, location } = results;
        const isAssociation = asso_id?.id_rna != null;

        return (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                {/* Carte principale - Identité */}
                <Card variant="outlined">
                    <CardContent>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 2 }}>
                            <Box>
                                <Typography variant="h5" fontWeight="bold" gutterBottom>
                                    {identity?.nom_raison_sociale || '[SANS NOM]'}
                                </Typography>
                                {identity?.enseigne && (
                                    <Typography variant="subtitle1" color="text.secondary">
                                        Enseigne: {identity.enseigne}
                                    </Typography>
                                )}
                            </Box>
                            <Chip
                                label={isAssociation ? "Association" : "Entreprise"}
                                color={isAssociation ? "success" : "primary"}
                                icon={isAssociation ? <Group /> : <Business />}
                            />
                        </Box>

                        <Divider sx={{ my: 2 }} />

                        <Grid container spacing={2}>
                            <Grid item xs={12} sm={6}>
                                <Typography variant="caption" color="text.secondary" display="block">
                                    SIRET
                                </Typography>
                                <Typography variant="body1" fontWeight="medium">
                                    {identity?.siret || 'N/A'}
                                </Typography>
                            </Grid>

                            {identity?.categorie_entreprise && (
                                <Grid item xs={12} sm={6}>
                                    <Typography variant="caption" color="text.secondary" display="block">
                                        Catégorie
                                    </Typography>
                                    <Typography variant="body1" fontWeight="medium">
                                        {identity.categorie_entreprise}
                                    </Typography>
                                </Grid>
                            )}
                        </Grid>
                    </CardContent>
                </Card>

                {/* Carte Association (si applicable) */}
                {isAssociation && (
                    <Card variant="outlined" sx={{ borderColor: 'success.main', borderWidth: 2 }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                                <Group color="success" />
                                <Typography variant="h6" color="success.main">
                                    Information Association
                                </Typography>
                            </Box>

                            <Divider sx={{ my: 2 }} />

                            <Grid container spacing={2}>
                                <Grid item xs={12} sm={6}>
                                    <Typography variant="caption" color="text.secondary" display="block">
                                        Numéro RNA
                                    </Typography>
                                    <Typography variant="body1" fontWeight="medium">
                                        {asso_id.id_rna}
                                    </Typography>
                                </Grid>

                                {asso_id?.date_publication_jo && (
                                    <Grid item xs={12} sm={6}>
                                        <Typography variant="caption" color="text.secondary" display="block">
                                            Date publication JO
                                        </Typography>
                                        <Typography variant="body1" fontWeight="medium">
                                            {asso_id.date_publication_jo}
                                        </Typography>
                                    </Grid>
                                )}
                            </Grid>
                        </CardContent>
                    </Card>
                )}

                {/* Carte Localisation */}
                {location && (
                    <Card variant="outlined">
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                                <LocationOn color="primary" />
                                <Typography variant="h6">
                                    Localisation
                                </Typography>
                            </Box>

                            <Divider sx={{ my: 2 }} />

                            <Box sx={{ mb: 3 }}>
                                <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                                    Adresse
                                </Typography>
                                <Typography variant="body1" fontWeight="medium">
                                    {location.numero_voie} {location.type_voie} {location.libelle_voie}
                                </Typography>
                                <Typography variant="body1" fontWeight="medium">
                                    {location.code_postal} {location.commune}
                                </Typography>
                            </Box>

                            {location?.latitude && location?.longitude && (
                                <Grid container spacing={2}>
                                    <Grid item xs={12} sm={4}>
                                        <Typography variant="caption" color="text.secondary" display="block">
                                            Latitude
                                        </Typography>
                                        <Typography variant="body2" fontWeight="medium">
                                            {location.latitude.toFixed(4)}
                                        </Typography>
                                    </Grid>
                                    <Grid item xs={12} sm={4}>
                                        <Typography variant="caption" color="text.secondary" display="block">
                                            Longitude
                                        </Typography>
                                        <Typography variant="body2" fontWeight="medium">
                                            {location.longitude.toFixed(4)}
                                        </Typography>
                                    </Grid>
                                    <Grid item xs={12} sm={4}>
                                        <Typography variant="caption" color="text.secondary" display="block">
                                            Score géolocalisation
                                        </Typography>
                                        <Typography variant="body2" fontWeight="medium">
                                            {location.geo_score ? (location.geo_score * 100).toFixed(0) + '%' : 'N/A'}
                                        </Typography>
                                    </Grid>
                                </Grid>
                            )}
                        </CardContent>
                    </Card>
                )}
            </Box>
        );
    };

    // Affichage pour la recherche fuzzy (liste de résultats)
    const renderFuzzyResults = () => {
        if (!results || !results.results || results.results.length === 0) return null;

        return (
            <>
                <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                        Requête: {results.query || 'N/A'}
                        {results.filter_dept && ` | Département: ${results.filter_dept}`}
                    </Typography>
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
                                    <Chip
                                        label={result.is_association ? "Association" : "Entreprise"}
                                        color={result.is_association ? "success" : "primary"}
                                        size="small"
                                        icon={result.is_association ? <Group /> : <Business />}
                                    />
                                </Box>

                                <Typography variant="body2" color="text.secondary" gutterBottom>
                                    SIRET: {result.siret}
                                </Typography>

                                {result.city && (
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                                        <LocationOn fontSize="small" color="action" />
                                        <Typography variant="body2">
                                            {result.city}
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

    // Affichage pour les statistiques
    const renderStats = () => {
        if (!results) return null;

        return (
            <Box sx={{ mt: 2 }}>
                {/* En-tête avec zone et total */}
                <Card variant="outlined" sx={{ mb: 3, p: 3, textAlign: 'center' }}>
                    <Typography variant="overline" color="text.secondary">
                        Code Postal
                    </Typography>
                    <Typography variant="h4" fontWeight="bold" color="primary" gutterBottom>
                        {results.zone}
                    </Typography>
                    <Divider sx={{ my: 2 }} />
                    <Typography variant="h5" color="text.secondary">
                        {results.total_entites?.toLocaleString() || 0} entités totales
                    </Typography>
                </Card>

                {/* Répartition simplifiée */}
                {results.repartition && (
                    <Card variant="outlined" sx={{ mb: 3 }}>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                Répartition
                            </Typography>
                            <Divider sx={{ my: 2 }} />
                            <Grid container spacing={2}>
                                <Grid item xs={12} sm={4}>
                                    <Box sx={{ textAlign: 'center', py: 2 }}>
                                        <Business color="primary" sx={{ fontSize: 36, mb: 1 }} />
                                        <Typography variant="h5" fontWeight="bold">
                                            {results.repartition.entreprises_pures?.toLocaleString() || 0}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Entreprises pures
                                        </Typography>
                                    </Box>
                                </Grid>
                                <Grid item xs={12} sm={4}>
                                    <Box sx={{ textAlign: 'center', py: 2 }}>
                                        <Group color="success" sx={{ fontSize: 36, mb: 1 }} />
                                        <Typography variant="h5" fontWeight="bold">
                                            {results.repartition.associations?.toLocaleString() || 0}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Associations
                                        </Typography>
                                    </Box>
                                </Grid>
                                <Grid item xs={12} sm={4}>
                                    <Box sx={{ textAlign: 'center', py: 2 }}>
                                        <Business color="error" sx={{ fontSize: 36, mb: 1 }} />
                                        <Typography variant="h5" fontWeight="bold">
                                            {results.repartition.etablissements_fermes?.toLocaleString() || 0}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Établissements fermés
                                        </Typography>
                                    </Box>
                                </Grid>
                            </Grid>
                        </CardContent>
                    </Card>
                )}

                {/* Activité principale */}
                {results.top_naf && (
                    <Card variant="outlined">
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                Activité principale (NAF)
                            </Typography>
                            <Divider sx={{ my: 2 }} />
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
                                <Box>
                                    <Typography variant="h6" fontWeight="bold" color="primary">
                                        {results.top_naf.code}
                                    </Typography>
                                    <Typography variant="body1" color="text.secondary">
                                        {results.top_naf.libelle}
                                    </Typography>
                                </Box>
                                <Chip
                                    label={`${results.top_naf.count?.toLocaleString() || 0} établissements`}
                                    color="primary"
                                    size="medium"
                                />
                            </Box>
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
