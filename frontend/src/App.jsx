import React, { useState, useEffect } from 'react'
import {
  Container,
  AppBar,
  Toolbar,
  Typography,
  Box,
  TextField,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Alert,
  Grid,
  IconButton,
  ThemeProvider,
  createTheme,
  CssBaseline,
  Tooltip,
  Menu,
  MenuItem,
  Divider,
  Snackbar
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import MenuBookIcon from '@mui/icons-material/MenuBook'
import LanguageIcon from '@mui/icons-material/Language'
import DarkModeIcon from '@mui/icons-material/DarkMode'
import LightModeIcon from '@mui/icons-material/LightMode'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import FileDownloadIcon from '@mui/icons-material/FileDownload'
import HistoryIcon from '@mui/icons-material/History'
import CasinoIcon from '@mui/icons-material/Casino'
import MoreVertIcon from '@mui/icons-material/MoreVert'
import axios from 'axios'
import TextToSpeechButton from './components/TextToSpeechButton'
import { useLocalStorage } from './hooks/useLocalStorage'
import { exportToCSV, copyToClipboard } from './utils/exportUtils'

const API_BASE = '/api'

// Create light and dark themes
const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#667eea',
    },
    secondary: {
      main: '#764ba2',
    },
    background: {
      default: '#f5f5f5',
    },
  },
  typography: {
    h4: {
      fontWeight: 600,
    },
  },
})

const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#667eea',
    },
    secondary: {
      main: '#764ba2',
    },
    background: {
      default: '#121212',
      paper: '#1e1e1e',
    },
  },
  typography: {
    h4: {
      fontWeight: 600,
    },
  },
})

function App() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [preferBilingual, setPreferBilingual] = useState(true)
  const [darkMode, setDarkMode] = useLocalStorage('darkMode', false)
  const [searchHistory, setSearchHistory] = useLocalStorage('searchHistory', [])
  const [snackbar, setSnackbar] = useState({ open: false, message: '' })
  const [historyMenuAnchor, setHistoryMenuAnchor] = useState(null)

  const theme = darkMode ? darkTheme : lightTheme

  // Load search history on mount
  useEffect(() => {
    // Initialize with empty array if not exists
    if (!Array.isArray(searchHistory)) {
      setSearchHistory([])
    }
  }, [])

  const showSnackbar = (message) => {
    setSnackbar({ open: true, message })
  }

  const handleSearch = async () => {
    if (!query.trim()) return

    const searchQuery = query.trim()

    // Log search input in frontend for visibility/debugging
    console.info('[Search]', {
      query: searchQuery,
      preferBilingual,
      timestamp: new Date().toISOString()
    })

    setLoading(true)
    setError(null)

    try {
      const response = await axios.get(`${API_BASE}/quotes/search`, {
        params: {
          q: searchQuery,
          limit: 50,
          prefer_bilingual: preferBilingual,
        },
      })
      setResults(response.data)

      // Add to search history (max 20 items)
      const newHistory = [
        searchQuery,
        ...searchHistory.filter(item => item !== searchQuery)
      ].slice(0, 20)
      setSearchHistory(newHistory)
    } catch (err) {
      setError(err.message || 'Failed to search quotes')
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const handleRandomQuote = async () => {
    setLoading(true)
    setError(null)
    setQuery('')

    try {
      const response = await axios.get(`${API_BASE}/quotes/random`)
      setResults([response.data])
      showSnackbar('Random quote loaded!')
    } catch (err) {
      setError(err.message || 'Failed to load random quote')
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const handleCopyQuote = async (text) => {
    const success = await copyToClipboard(text)
    if (success) {
      showSnackbar('Quote copied to clipboard!')
    } else {
      showSnackbar('Failed to copy quote')
    }
  }

  const handleExportCSV = () => {
    if (results.length === 0) {
      showSnackbar('No quotes to export')
      return
    }
    const timestamp = new Date().toISOString().split('T')[0]
    exportToCSV(results, `quotes_export_${timestamp}.csv`)
    showSnackbar(`Exported ${results.length} quotes to CSV`)
  }

  const handleHistoryClick = (event) => {
    setHistoryMenuAnchor(event.currentTarget)
  }

  const handleHistoryClose = () => {
    setHistoryMenuAnchor(null)
  }

  const handleHistorySelect = (historyItem) => {
    setQuery(historyItem)
    setHistoryMenuAnchor(null)
    // Trigger search after a short delay to allow state update
    setTimeout(() => {
      handleSearch()
    }, 100)
  }

  const handleClearHistory = () => {
    setSearchHistory([])
    setHistoryMenuAnchor(null)
    showSnackbar('Search history cleared')
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ flexGrow: 1, minHeight: '100vh', bgcolor: 'background.default' }}>
        <AppBar position="static" elevation={0} sx={{ bgcolor: 'primary.main' }}>
          <Toolbar>
            <MenuBookIcon sx={{ mr: 2 }} />
            <Typography variant="h5" component="div" sx={{ flexGrow: 1, fontWeight: 600 }}>
              Aphorium
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <Tooltip title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}>
                <IconButton
                  color="inherit"
                  onClick={() => setDarkMode(!darkMode)}
                  aria-label="Toggle dark mode"
                >
                  {darkMode ? <LightModeIcon /> : <DarkModeIcon />}
                </IconButton>
              </Tooltip>
              {searchHistory.length > 0 && (
                <>
                  <Tooltip title="Search history">
                    <IconButton
                      color="inherit"
                      onClick={handleHistoryClick}
                      aria-label="Search history"
                    >
                      <HistoryIcon />
                    </IconButton>
                  </Tooltip>
                  <Menu
                    anchorEl={historyMenuAnchor}
                    open={Boolean(historyMenuAnchor)}
                    onClose={handleHistoryClose}
                    PaperProps={{
                      sx: { maxHeight: 300, width: 250 }
                    }}
                  >
                    <MenuItem disabled>
                      <Typography variant="caption" color="text.secondary">
                        Recent Searches
                      </Typography>
                    </MenuItem>
                    <Divider />
                    {searchHistory.map((item, index) => (
                      <MenuItem
                        key={index}
                        onClick={() => handleHistorySelect(item)}
                      >
                        <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>
                          {item}
                        </Typography>
                      </MenuItem>
                    ))}
                    <Divider />
                    <MenuItem onClick={handleClearHistory}>
                      <Typography variant="body2" color="error">
                        Clear History
                      </Typography>
                    </MenuItem>
                  </Menu>
                </>
              )}
            </Box>
          </Toolbar>
        </AppBar>

        <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
          <Box
            sx={{
              textAlign: 'center',
              mb: 4,
              p: 4,
              bgcolor: 'background.paper',
              borderRadius: 2,
              boxShadow: 2,
            }}
          >
            <Typography variant="h4" gutterBottom sx={{ mb: 2 }}>
              Discover Wisdom in Two Languages
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
              Search for quotes and aphorisms from English and Russian literature.
              Learn languages naturally by exploring the best quotes from both cultures.
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2, fontStyle: 'italic' }}>
              💡 Tip: Use quotes for exact phrases (e.g., "a love is"), or search without quotes for broader matches
            </Typography>

            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap', alignItems: 'center' }}>
              <TextField
                fullWidth
                variant="outlined"
                placeholder="Search in English or Russian... (e.g., 'love', 'любовь', 'wisdom', 'мудрость')"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                sx={{ maxWidth: 600 }}
                InputProps={{
                  endAdornment: (
                    <IconButton onClick={handleSearch} disabled={loading}>
                      <SearchIcon />
                    </IconButton>
                  ),
                }}
              />
              <Button
                variant="contained"
                size="large"
                onClick={handleSearch}
                disabled={loading || !query.trim()}
                sx={{ minWidth: 120 }}
              >
                {loading ? <CircularProgress size={24} /> : 'Search'}
              </Button>
              <Tooltip title="Get random quote">
                <IconButton
                  color="primary"
                  onClick={handleRandomQuote}
                  disabled={loading}
                  size="large"
                  sx={{ border: 1, borderColor: 'primary.main' }}
                >
                  <CasinoIcon />
                </IconButton>
              </Tooltip>
            </Box>

            <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center', gap: 2, flexWrap: 'wrap' }}>
              <Chip
                label="Prefer bilingual quotes"
                color={preferBilingual ? 'primary' : 'default'}
                onClick={() => setPreferBilingual(!preferBilingual)}
                clickable
              />
              {results.length > 0 && (
                <Tooltip title="Export results to CSV">
                  <Chip
                    icon={<FileDownloadIcon />}
                    label="Export CSV"
                    color="secondary"
                    onClick={handleExportCSV}
                    clickable
                  />
                </Tooltip>
              )}
            </Box>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {results.length > 0 && (
            <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography variant="h6" color="text.secondary">
                Found {results.length} quote{results.length !== 1 ? 's' : ''}
              </Typography>
            </Box>
          )}

          <Grid container spacing={3}>
            {results.map((pair, index) => {
              // Check if this is a bilingual pair (both EN and RU exist)
              const isBilingual = pair.english && pair.russian
              
              return (
                <Grid 
                  item 
                  xs={12} 
                  sm={isBilingual ? 12 : 6} 
                  md={isBilingual ? 12 : 4} 
                  key={pair.english?.id || pair.russian?.id || index}
                >
                  <Card
                    sx={{
                      borderLeft: isBilingual ? '4px solid #27ae60' : '4px solid #667eea',
                      bgcolor: isBilingual ? 'rgba(39, 174, 96, 0.05)' : 'background.paper',
                      transition: 'transform 0.2s, box-shadow 0.2s',
                      '&:hover': {
                        transform: 'translateY(-4px)',
                        boxShadow: 4,
                      },
                    }}
                  >
                    <CardContent>
                      {isBilingual ? (
                        // Bilingual pair: show side by side in same card
                        <Box sx={{ display: 'flex', gap: 3, flexDirection: { xs: 'column', md: 'row' } }}>
                          {/* English Quote */}
                          <Box sx={{ flex: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexWrap: 'wrap' }}>
                              <Chip
                                icon={<LanguageIcon />}
                                label="EN"
                                size="small"
                                color="primary"
                                variant="outlined"
                              />
                              {pair.is_translated && (
                                <Chip
                                  label="Translated"
                                  size="small"
                                  color="warning"
                                  variant="outlined"
                                />
                              )}
                              <TextToSpeechButton text={pair.english.text} language="en" size="small" />
                              <Tooltip title="Copy quote">
                                <IconButton
                                  size="small"
                                  onClick={() => handleCopyQuote(pair.english.text)}
                                  sx={{ opacity: 0.7, '&:hover': { opacity: 1 } }}
                                >
                                  <ContentCopyIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </Box>
                            <Typography
                              variant="body1"
                              sx={{
                                fontStyle: 'italic',
                                fontSize: '1.1rem',
                                mb: 1,
                                color: 'text.primary',
                                lineHeight: 1.8,
                              }}
                            >
                              "{pair.english.text}"
                            </Typography>
                            {pair.english.author && (
                              <Typography variant="caption" color="text.secondary">
                                — {pair.english.author.name}
                              </Typography>
                            )}
                          </Box>
                          
                          {/* Divider */}
                          <Box 
                            sx={{ 
                              display: { xs: 'none', md: 'block' },
                              width: '1px',
                              bgcolor: 'divider',
                              mx: 2
                            }} 
                          />
                          
                          {/* Russian Quote */}
                          <Box sx={{ flex: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexWrap: 'wrap' }}>
                              <Chip
                                icon={<LanguageIcon />}
                                label="RU"
                                size="small"
                                color="primary"
                                variant="outlined"
                              />
                              {pair.is_translated && (
                                <Chip
                                  label="Translated"
                                  size="small"
                                  color="warning"
                                  variant="outlined"
                                />
                              )}
                              <TextToSpeechButton text={pair.russian.text} language="ru" size="small" />
                              <Tooltip title="Copy quote">
                                <IconButton
                                  size="small"
                                  onClick={() => handleCopyQuote(pair.russian.text)}
                                  sx={{ opacity: 0.7, '&:hover': { opacity: 1 } }}
                                >
                                  <ContentCopyIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </Box>
                            <Typography
                              variant="body1"
                              sx={{
                                fontStyle: 'italic',
                                fontSize: '1.1rem',
                                mb: 1,
                                color: 'text.primary',
                                lineHeight: 1.8,
                              }}
                            >
                              "{pair.russian.text}"
                            </Typography>
                            {pair.russian.author && (
                              <Typography variant="caption" color="text.secondary">
                                — {pair.russian.author.name}
                              </Typography>
                            )}
                          </Box>
                        </Box>
                      ) : (
                        // Single language quote: show in smaller card
                        <Box>
                          {pair.english && (
                            <>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexWrap: 'wrap' }}>
                                <Chip
                                  icon={<LanguageIcon />}
                                  label="EN"
                                  size="small"
                                  color="primary"
                                  variant="outlined"
                                />
                                <TextToSpeechButton text={pair.english.text} language="en" size="small" />
                                <Tooltip title="Copy quote">
                                  <IconButton
                                    size="small"
                                    onClick={() => handleCopyQuote(pair.english.text)}
                                    sx={{ opacity: 0.7, '&:hover': { opacity: 1 } }}
                                  >
                                    <ContentCopyIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              </Box>
                              <Typography
                                variant="body1"
                                sx={{
                                  fontStyle: 'italic',
                                  fontSize: '1.1rem',
                                  mb: 1,
                                  color: 'text.primary',
                                  lineHeight: 1.8,
                                }}
                              >
                                "{pair.english.text}"
                              </Typography>
                              {pair.english.author && (
                                <Typography variant="caption" color="text.secondary">
                                  — {pair.english.author.name}
                                </Typography>
                              )}
                            </>
                          )}
                          {pair.russian && (
                            <>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexWrap: 'wrap' }}>
                                <Chip
                                  icon={<LanguageIcon />}
                                  label="RU"
                                  size="small"
                                  color="primary"
                                  variant="outlined"
                                />
                                <TextToSpeechButton text={pair.russian.text} language="ru" size="small" />
                                <Tooltip title="Copy quote">
                                  <IconButton
                                    size="small"
                                    onClick={() => handleCopyQuote(pair.russian.text)}
                                    sx={{ opacity: 0.7, '&:hover': { opacity: 1 } }}
                                  >
                                    <ContentCopyIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              </Box>
                              <Typography
                                variant="body1"
                                sx={{
                                  fontStyle: 'italic',
                                  fontSize: '1.1rem',
                                  mb: 1,
                                  color: 'text.primary',
                                  lineHeight: 1.8,
                                }}
                              >
                                "{pair.russian.text}"
                              </Typography>
                              {pair.russian.author && (
                                <Typography variant="caption" color="text.secondary">
                                  — {pair.russian.author.name}
                                </Typography>
                              )}
                            </>
                          )}
                        </Box>
                      )}
                    </CardContent>
                  </Card>
                </Grid>
              )
            })}
          </Grid>

          {!loading && results.length === 0 && query && (
            <Box sx={{ textAlign: 'center', mt: 4, p: 4 }}>
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No quotes found
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Try a different search term or check if data has been loaded
              </Typography>
            </Box>
          )}

          {!query && results.length === 0 && (
            <Box sx={{ textAlign: 'center', mt: 4, p: 4 }}>
              <Typography variant="h6" color="text.secondary" gutterBottom>
                Start searching for quotes
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Try searching for: "love", "wisdom", "любовь", "мудрость"
              </Typography>
              <Button
                variant="outlined"
                startIcon={<CasinoIcon />}
                onClick={handleRandomQuote}
                disabled={loading}
                sx={{ mt: 2 }}
              >
                Or get a random quote
              </Button>
            </Box>
          )}
        </Container>

        <Snackbar
          open={snackbar.open}
          autoHideDuration={3000}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          message={snackbar.message}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        />
      </Box>
    </ThemeProvider>
  )
}

export default App
