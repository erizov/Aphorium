import React from 'react'
import { IconButton, Tooltip, Box } from '@mui/material'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import PauseIcon from '@mui/icons-material/Pause'
import StopIcon from '@mui/icons-material/Stop'
import VolumeUpIcon from '@mui/icons-material/VolumeUp'
import { useTextToSpeech, isTTSSupported } from '../hooks/useTextToSpeech'

/**
 * Text-to-Speech button component
 * 
 * Returns null if browser doesn't support TTS (no button shown)
 * 
 * @param {string} text - Quote text to speak
 * @param {string} language - Language code ('en' or 'ru')
 * @param {string} size - Button size ('small', 'medium', 'large')
 */
const TextToSpeechButton = ({ text, language = 'en', size = 'small' }) => {
  const { isSpeaking, isPaused, speak, pause, resume, stop } = useTextToSpeech()

  // Return null if TTS is not supported (no button shown)
  if (!isTTSSupported()) {
    return null
  }

  // Don't render if no text
  if (!text || !text.trim()) {
    return null
  }

  const handleClick = () => {
    if (isSpeaking && !isPaused) {
      // Currently speaking - pause it
      pause()
    } else if (isPaused) {
      // Currently paused - resume it
      resume()
    } else {
      // Not speaking - start speaking
      // Stop any other speech first
      stop()
      speak(text, language)
    }
  }

  const handleStop = (e) => {
    e.stopPropagation()
    stop()
  }

  // Determine which icon to show
  let icon
  let tooltipText

  if (isSpeaking && !isPaused) {
    // Currently speaking - show pause icon
    icon = <PauseIcon />
    tooltipText = `Pause ${language.toUpperCase()} quote`
  } else if (isPaused) {
    // Currently paused - show play icon
    icon = <PlayArrowIcon />
    tooltipText = `Resume ${language.toUpperCase()} quote`
  } else {
    // Not speaking - show play icon
    icon = <VolumeUpIcon />
    tooltipText = `Listen to ${language.toUpperCase()} quote`
  }

  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center' }}>
      <Tooltip title={tooltipText} arrow>
        <IconButton
          size={size}
          onClick={handleClick}
          color={isSpeaking ? 'primary' : 'default'}
          sx={{
            opacity: isSpeaking ? 1 : 0.7,
            '&:hover': {
              opacity: 1,
            },
          }}
        >
          {icon}
        </IconButton>
      </Tooltip>
      {isSpeaking && (
        <Tooltip title={`Stop ${language.toUpperCase()} quote`} arrow>
          <IconButton
            size={size}
            onClick={handleStop}
            color="error"
            sx={{
              ml: 0.5,
              opacity: 0.7,
              '&:hover': {
                opacity: 1,
              },
            }}
          >
            <StopIcon fontSize="inherit" />
          </IconButton>
        </Tooltip>
      )}
    </Box>
  )
}

export default TextToSpeechButton

