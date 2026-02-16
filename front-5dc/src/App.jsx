import { useState } from 'react';
import { ThemeProvider, CssBaseline, Box } from '@mui/material';
import { darkTheme } from './theme';
import Header from './components/Header';
import SearchTabs from './components/SearchTabs';
import ResultsArea from './components/ResultsArea';

function App() {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searchType, setSearchType] = useState('siret');

  const handleSearch = (type, data) => {
    setSearchType(type);
    setLoading(true);

    // Simuler un appel API
    setTimeout(() => {
      setResults(data);
      setLoading(false);
    }, 800);
  };

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Box id="app-container" sx={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', p: 3, }}>
        <Header />

        <Box sx={{ flexGrow: 1, width: '100%', overflow: 'hidden' }}>
          <Box sx={{ display: 'flex', gap: 3, height: '100%', width: '100%' }}>
            {/* Zone de recherche - 40% */}
            <Box sx={{ width: '40%', height: '100%', display: 'flex' }}>
              <SearchTabs onSearch={handleSearch} />
            </Box>

            {/* Zone de résultats - 60% */}
            <Box sx={{ width: '60%', height: '100%', display: 'flex' }}>
              <ResultsArea
                results={results}
                loading={loading}
                searchType={searchType}
              />
            </Box>
          </Box>
        </Box>
      </Box>
    </ThemeProvider>
  );
}

export default App;
