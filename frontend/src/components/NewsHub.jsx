import React from 'react'
import {
  Box,
  Grid,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  Pagination,
  MenuItem,
} from '@mui/material'
import axios from 'axios'
import NewsStoryCard from './NewsStoryCard'
import NewsArticleDetail from './NewsArticleDetail'

const API_BASE = '/api'
/** UI caps pagination regardless of total rows in the archive. */
const MAX_NEWS_PAGES = 7
const NEWS_CATEGORIES = [
  ['breaking', 'Breaking'],
  ['general', 'General'],
  ['world', 'World'],
  ['politics', 'Politics'],
  ['us', 'US'],
  ['europe', 'Europe'],
  ['russia', 'Russia'],
  ['business', 'Business'],
  ['technology', 'Technology'],
  ['ai', 'AI'],
  ['science', 'Science'],
  ['nature', 'Nature'],
  ['health', 'Health'],
  ['culture', 'Culture'],
  ['sports', 'Sports'],
  ['society', 'Society'],
]

function formatResponseDetail(detail) {
  if (detail == null) return ''
  if (typeof detail === 'string') return detail
  try {
    return JSON.stringify(detail)
  } catch {
    return String(detail)
  }
}

function formatAxiosError(e) {
  const status = e?.response?.status
  const detail = formatResponseDetail(e?.response?.data?.detail)
  const msg = e?.message || 'Request failed'
  if (status && detail) return `${msg} (HTTP ${status}): ${detail}`
  if (status) return `${msg} (HTTP ${status})`
  return msg
}

export default function NewsHub({ uiLang, showSnackbar }) {
  const [items, setItems] = React.useState([])
  const [total, setTotal] = React.useState(0)
  const [page, setPage] = React.useState(1)
  const [pageSize] = React.useState(6)
  const [category, setCategory] = React.useState('')
  const [q, setQ] = React.useState('')
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState(null)
  const [detailId, setDetailId] = React.useState(null)

  const load = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { page, page_size: pageSize }
      if (category) params.category = category
      if (q.trim()) params.q = q.trim()
      const res = await axios.get(`${API_BASE}/news/articles`, { params })
      setItems(res.data.items || [])
      setTotal(res.data.total || 0)
    } catch (e) {
      setError(formatAxiosError(e))
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, category, q])

  const hasFilters = Boolean(category || q.trim())

  React.useEffect(() => {
    load()
  }, [load])

  const rawPageCount = Math.max(1, Math.ceil(total / pageSize))
  const pages = Math.min(MAX_NEWS_PAGES, rawPageCount)

  React.useEffect(() => {
    if (page > pages) setPage(pages)
  }, [page, pages])

  const handleProcess = async (id) => {
    try {
      await axios.post(`${API_BASE}/news/articles/${id}/process`)
      if (showSnackbar) showSnackbar('Processed')
      await load()
    } catch (e) {
      if (showSnackbar) showSnackbar(formatAxiosError(e))
    }
  }

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="h5" gutterBottom sx={{ fontWeight: 600 }}>
        News & aphorisms
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Current stories with generated lines and archive echoes. Process uses your configured LLM.
      </Typography>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 3, alignItems: 'center' }}>
        <TextField
          size="small"
          label="Search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          sx={{ minWidth: 200 }}
        />
        <TextField
          select
          size="small"
          label="Category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          sx={{ minWidth: 160 }}
        >
          <MenuItem value="">All</MenuItem>
          {NEWS_CATEGORIES.map(([value, label]) => (
            <MenuItem value={value} key={value}>{label}</MenuItem>
          ))}
        </TextField>
        <Button variant="contained" onClick={() => { setPage(1); load() }} disabled={loading}>
          {loading ? <CircularProgress size={22} /> : 'Refresh'}
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {loading && items.length === 0 ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Grid container spacing={2}>
          {items.map((article) => (
            <Grid item xs={12} md={6} key={article.id}>
              <NewsStoryCard
                article={article}
                uiLang={uiLang}
                onOpenDetail={setDetailId}
                onProcess={handleProcess}
              />
            </Grid>
          ))}
        </Grid>
      )}

      {!loading && items.length === 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" color="text.secondary">
            {hasFilters
              ? 'No articles match the current search/category filters.'
              : 'No articles yet. Ingest RSS via API or run '}
            {!hasFilters && (
              <Box component="span" sx={{ fontFamily: 'monospace' }}>
                python scripts/seed_news_demo.py
              </Box>
            )}
            {!hasFilters ? '.' : ''}
          </Typography>
          {hasFilters && (
            <Button
              size="small"
              variant="text"
              sx={{ mt: 1 }}
              onClick={() => {
                setQ('')
                setCategory('')
                setPage(1)
              }}
            >
              Clear filters
            </Button>
          )}
        </Box>
      )}

      {total > pageSize && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
          <Pagination count={pages} page={page} onChange={(_, p) => setPage(p)} color="primary" />
        </Box>
      )}

      <NewsArticleDetail
        articleId={detailId}
        open={Boolean(detailId)}
        onClose={() => setDetailId(null)}
        uiLang={uiLang}
        onProcessed={load}
      />
    </Box>
  )
}
