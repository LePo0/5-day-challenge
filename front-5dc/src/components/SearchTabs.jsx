import { useState } from 'react';
import { Box, Tabs, Tab, Paper } from '@mui/material';
import { Search, TravelExplore, Analytics } from '@mui/icons-material';
import SiretSearch from './SiretSearch';
import FuzzySearch from './FuzzySearch';
import StatsSearch from './StatsSearch';

function SearchTabs({ onSearch }) {
    const [activeTab, setActiveTab] = useState(0);

    const handleTabChange = (event, newValue) => {
        setActiveTab(newValue);
    };

    return (
        <Paper elevation={3} sx={{
            overflow: 'hidden',
            height: '100%',
            width: '100%',
            display: 'flex',
            flexDirection: 'column'
        }}>
            <Tabs
                value={activeTab}
                onChange={handleTabChange}
                variant="fullWidth"
                sx={{
                    borderBottom: 1,
                    borderColor: 'divider',
                    '& .MuiTab-root': { py: 2 },
                }}
            >
                <Tab icon={<Search />} label="Recherche SIRET" iconPosition="start" />
                <Tab icon={<TravelExplore />} label="Recherche Textuelle" iconPosition="start" />
                <Tab icon={<Analytics />} label="Statistiques" iconPosition="start" />
            </Tabs>

            <Box sx={{ p: 4, flexGrow: 1, overflow: 'auto' }}>
                {activeTab === 0 && <SiretSearch onSearch={onSearch} />}
                {activeTab === 1 && <FuzzySearch onSearch={onSearch} />}
                {activeTab === 2 && <StatsSearch onSearch={onSearch} />}
            </Box>
        </Paper>
    );
}

export default SearchTabs;
