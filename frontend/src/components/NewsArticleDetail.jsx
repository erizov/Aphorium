import React from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  Link,
  CircularProgress,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import axios from 'axios'
import TextToSpeechButton from './TextToSpeechButton'

const API_BASE = '/api'

function formatAxiosError(e) {
  const status = e?.response?.status
  const detail = e?.response?.data?.detail
  const msg = e?.message || 'Request failed'
  if (status && detail) return `${msg} (HTTP ${status}): ${detail}`
  if (status) return `${msg} (HTTP ${status})`
  return msg
}

function authorLabel(author, uiLang) {
  if (!author) return 'Unknown author'
  if (uiLang === 'ru') return author.name_ru || author.name_en || 'Unknown author'
  return author.name_en || author.name_ru || 'Unknown author'
}

export default function NewsArticleDetail({ articleId, open, onClose, uiLang, onProcessed }) {
  const [article, setArticle] = React.useState(null)
  const [loading, setLoading] = React.useState(false)
  const [processing, setProcessing] = React.useState(false)
  const [error, setError] = React.useState(null)

  const load = React.useCallback(async () => {
    if (!articleId) return
    setLoading(true)
    setError(null)
    try {
      const res = await axios.get(`${API_BASE}/news/articles/${articleId}`)
      setArticle(res.data)
    } catch (e) {
      setError(formatAxiosError(e))
      setArticle(null)
    } finally {
      setLoading(false)
    }
  }, [articleId])

  React.useEffect(() => {
    if (open && articleId) {
      load()
    }
  }, [open, articleId, load])

  const handleProcess = async () => {
    if (!articleId) return
    setProcessing(true)
    setError(null)
    try {
      await axios.post(`${API_BASE}/news/articles/${articleId}/process`)
      await load()
      if (onProcessed) onProcessed()
    } catch (e) {
      setError(formatAxiosError(e))
    } finally {
      setProcessing(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle sx={{ pr: 6 }}>
        {article ? (
          <Link href={article.url} target="_blank" rel="noopener noreferrer" underline="hover" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
            {article.title}
            <OpenInNewIcon fontSize="small" />
          </Link>
        ) : (
          'News article'
        )}
      </DialogTitle>
      <DialogContent dividers>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        )}
        {error && (
          <Typography color="error" variant="body2" sx={{ mb: 2 }}>
            {error}
          </Typography>
        )}
        {article && !loading && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              <Chip size="small" label={article.source} />
              {article.category ? <Chip size="small" label={article.category} /> : null}
              <Chip size="small" label={article.language?.toUpperCase()} />
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
              {article.content}
            </Typography>
            <Typography variant="subtitle2">Generated aphorisms</Typography>
            {(article.aphorisms || []).map((a) => (
              <Box key={a.id} sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                  <Chip size="small" label={a.generation_method} variant="outlined" />
                  <TextToSpeechButton text={a.aphorism_text} language={a.language || 'en'} size="small" />
                </Box>
                <Typography variant="body1" sx={{ fontStyle: 'italic' }}>
                  {a.aphorism_text}
                </Typography>
              </Box>
            ))}
            <Typography variant="subtitle2">Related quotes</Typography>
            {(article.related_quotes || []).map((row, idx) => (
              <Accordion key={row.quote?.id ?? idx} defaultExpanded={idx === 0}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="body2">
                    {authorLabel(row.quote.author, uiLang)} — score {row.relevance_score}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography variant="body2" sx={{ fontStyle: 'italic', mb: 1 }}>
                    &ldquo;{row.quote.text}&rdquo;
                  </Typography>
                  {row.match_reason ? (
                    <Typography variant="caption" color="text.secondary">
                      {row.match_reason}
                    </Typography>
                  ) : null}
                </AccordionDetails>
              </Accordion>
            ))}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        <Button variant="contained" onClick={handleProcess} disabled={processing || !articleId}>
          {processing ? <CircularProgress size={22} /> : 'Process with LLM'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
