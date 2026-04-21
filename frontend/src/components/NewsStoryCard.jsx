import React from 'react'
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Link,
  List,
  Button,
  Divider,
} from '@mui/material'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import RelatedQuoteRow from './RelatedQuoteRow'

export default function NewsStoryCard({ article, uiLang, onOpenDetail, onProcess }) {
  const primaryAph = article.aphorisms && article.aphorisms[0]
  const pairs = article.related_quotes || []

  return (
    <Card variant="outlined" sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        <Box>
          <Link
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            underline="hover"
            sx={{ fontWeight: 600, fontSize: '1.05rem', display: 'inline-flex', alignItems: 'center', gap: 0.5 }}
          >
            {article.title}
            <OpenInNewIcon sx={{ fontSize: 18 }} />
          </Link>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 0.75 }}>
            <Chip size="small" label={article.source} variant="outlined" />
            {article.category ? (
              <Chip size="small" label={article.category} color="error" variant="outlined" />
            ) : null}
            <Chip size="small" label={article.language?.toUpperCase() || 'EN'} />
            {article.published_at ? (
              <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>
                {new Date(article.published_at).toLocaleString()}
              </Typography>
            ) : null}
          </Box>
        </Box>

        {primaryAph ? (
          <Box
            sx={{
              py: 1.5,
              px: 2,
              borderRadius: 2,
              bgcolor: 'action.hover',
            }}
          >
            <Typography variant="overline" color="text.secondary">
              Aphorism
              {primaryAph.generation_method ? ` · ${primaryAph.generation_method}` : ''}
            </Typography>
            <Typography variant="body1" sx={{ fontStyle: 'italic', mt: 0.5, lineHeight: 1.7 }}>
              {primaryAph.aphorism_text}
            </Typography>
          </Box>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No generated aphorism yet — run Process on this story.
          </Typography>
        )}

        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            From the archive
          </Typography>
          {pairs.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No matched aphorisms yet.
            </Typography>
          ) : (
            <List dense disablePadding>
              {pairs.map((row, i) => (
                <React.Fragment key={row.quote?.id ?? i}>
                  {i > 0 ? <Divider component="li" /> : null}
                  <RelatedQuoteRow row={row} uiLang={uiLang} />
                </React.Fragment>
              ))}
            </List>
          )}
        </Box>

        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 'auto', pt: 1 }}>
          <Button size="small" variant="text" onClick={() => onOpenDetail(article.id)}>
            Expand
          </Button>
          <Button size="small" variant="outlined" onClick={() => onProcess(article.id)}>
            Process
          </Button>
        </Box>
      </CardContent>
    </Card>
  )
}
