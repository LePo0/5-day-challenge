import { ThemeProvider, CssBaseline, Box } from '@mui/material';
import { darkTheme } from './theme';
import Header from './components/Header';
import SearchTabs from './components/SearchTabs';
import ResultsArea from './components/ResultsArea';
import Toaster from './components/Toaster';

function App() {
  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Box id="app-container" sx={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', p: 3, }}>
        <Header />

        <Box sx={{ flexGrow: 1, width: '100%', overflow: 'hidden' }}>
          <Box sx={{ display: 'flex', gap: 3, height: '100%', width: '100%' }}>
            {/* Zone de recherche - 40% */}
            <Box sx={{ width: '40%', height: '100%', display: 'flex' }}>
              <SearchTabs />
            </Box>

            {/* Zone de résultats - 60% */}
            <Box sx={{ width: '60%', height: '100%', display: 'flex' }}>
              <ResultsArea />
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Toaster global */}
      <Toaster />
    </ThemeProvider>
  );
}

export default App;
