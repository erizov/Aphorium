import React, { useState } from 'react'
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
  CssBaseline
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import MenuBookIcon from '@mui/icons-material/MenuBook'
import LanguageIcon from '@mui/icons-material/Language'
import axios from 'axios'

const theme = createTheme({
  palette: {
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

const API_BASE = '/api'

function App() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [preferBilingual, setPreferBilingual] = useState(true)

  const handleSearch = async () => {
    if (!query.trim()) return

    setLoading(true)
    setError(null)

    try {
      const response = await axios.get(`${API_BASE}/quotes/search`, {
        params: {
          q: query,
          limit: 50,
          prefer_bilingual: preferBilingual,
        },
      })
      setResults(response.data)
    } catch (err) {
      setError(err.message || 'Failed to search quotes')
      setResults([])
    } finally {
      setLoading(false)
    }
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
            <Typography variant="body2" sx={{ opacity: 0.9 }}>
              Learn languages through quotes
            </Typography>
          </Toolbar>
        </AppBar>

        <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
          <Box
            sx={{
              textAlign: 'center',
              mb: 4,
              p: 4,
              bgcolor: 'white',
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

            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
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
            </Box>

            <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center', gap: 2 }}>
              <Chip
                label="Prefer bilingual quotes"
                color={preferBilingual ? 'primary' : 'default'}
                onClick={() => setPreferBilingual(!preferBilingual)}
                clickable
              />
            </Box>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {results.length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="h6" color="text.secondary">
                Found {results.length} quote{results.length !== 1 ? 's' : ''}
              </Typography>
            </Box>
          )}

          <Grid container spacing={3}>
            {results.map((pair, index) => (
              <Grid item xs={12} key={pair.english?.id || pair.russian?.id || index}>
                <Card
                  sx={{
                    borderLeft: (pair.english && pair.russian) ? '4px solid #27ae60' : '4px solid #667eea',
                    bgcolor: (pair.english && pair.russian) ? 'rgba(39, 174, 96, 0.05)' : 'white',
                    transition: 'transform 0.2s, box-shadow 0.2s',
                    '&:hover': {
                      transform: 'translateY(-4px)',
                      boxShadow: 4,
                    },
                  }}
                >
                  <CardContent>
                    <Box sx={{ display: 'flex', gap: 3, flexDirection: { xs: 'column', md: 'row' } }}>
                      {/* English Quote */}
                      {pair.english && (
                        <Box sx={{ flex: 1 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
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
                      )}
                      
                      {/* Russian Quote */}
                      {pair.russian && (
                        <Box sx={{ flex: 1, borderLeft: { md: '1px solid #e0e0e0' }, pl: { md: 3 } }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
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
                      )}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
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
            </Box>
          )}
        </Container>
      </Box>
    </ThemeProvider>
  )
}

export default App

