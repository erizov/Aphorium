import React from 'react'
import {
  ListItem,
  ListItemText,
  Chip,
  Tooltip,
  IconButton,
  Box,
} from '@mui/material'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import TextToSpeechButton from './TextToSpeechButton'

function authorLabel(author, uiLang) {
  if (!author) return 'Unknown author'
  if (uiLang === 'ru') return author.name_ru || author.name_en || 'Unknown author'
  return author.name_en || author.name_ru || 'Unknown author'
}

export default function RelatedQuoteRow({ row, uiLang = 'en' }) {
  const { quote, relevance_score, match_reason } = row
  const secondary = [
    authorLabel(quote.author, uiLang),
    quote.source ? quote.source.title : null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <ListItem
      alignItems="flex-start"
      sx={{ py: 1.25, px: 0 }}
      secondaryAction={
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {match_reason ? (
            <Tooltip title={match_reason}>
              <IconButton size="small" edge="end" aria-label="Match reason">
                <InfoOutlinedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          ) : null}
          <Chip label={`${relevance_score}`} size="small" variant="outlined" />
        </Box>
      }
    >
      <ListItemText
        primary={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, pr: 6 }}>
            <TextToSpeechButton
              text={quote.text}
              language={quote.language || 'en'}
              size="small"
            />
            <Box component="span" sx={{ fontStyle: 'italic' }}>
              &ldquo;{quote.text}&rdquo;
            </Box>
          </Box>
        }
        secondary={secondary}
        primaryTypographyProps={{ variant: 'body2' }}
        secondaryTypographyProps={{ variant: 'caption', color: 'text.secondary' }}
      />
    </ListItem>
  )
}
