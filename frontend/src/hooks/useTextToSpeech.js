import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * Check if browser supports Web Speech API
 */
export const isTTSSupported = () => {
  return (
    typeof window !== 'undefined' &&
    'speechSynthesis' in window &&
    'SpeechSynthesisUtterance' in window
  )
}

/**
 * Map language code to SpeechSynthesis language code
 */
const getLanguageCode = (language) => {
  const langMap = {
    en: 'en-US',
    ru: 'ru-RU',
  }
  return langMap[language] || language
}

// Global state to track current speaking instance
let globalUtteranceRef = null
let globalIsSpeaking = false
let globalIsPaused = false
const listeners = new Set()

const notifyListeners = () => {
  listeners.forEach(listener => listener())
}

/**
 * React hook for text-to-speech functionality
 * 
 * @returns {Object} TTS controls and state
 */
export const useTextToSpeech = () => {
  const [, forceUpdate] = useState({})
  const utteranceRef = useRef(null)
  const supported = isTTSSupported()

  // Subscribe to global state changes
  useEffect(() => {
    const listener = () => {
      forceUpdate({})
    }
    listeners.add(listener)
    return () => {
      listeners.delete(listener)
    }
  }, [])

  const isSpeaking = globalIsSpeaking && utteranceRef.current === globalUtteranceRef
  const isPaused = globalIsPaused && utteranceRef.current === globalUtteranceRef

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (utteranceRef.current === globalUtteranceRef) {
        window.speechSynthesis.cancel()
        globalUtteranceRef = null
        globalIsSpeaking = false
        globalIsPaused = false
        notifyListeners()
      }
    }
  }, [])

  // Handle speech events
  useEffect(() => {
    if (!supported || !utteranceRef.current) return

    const utterance = utteranceRef.current

    const handleStart = () => {
      globalIsSpeaking = true
      globalIsPaused = false
      notifyListeners()
    }

    const handleEnd = () => {
      if (utteranceRef.current === globalUtteranceRef) {
        globalIsSpeaking = false
        globalIsPaused = false
        globalUtteranceRef = null
        utteranceRef.current = null
        notifyListeners()
      }
    }

    const handleError = (event) => {
      console.error('Speech synthesis error:', event.error)
      if (utteranceRef.current === globalUtteranceRef) {
        globalIsSpeaking = false
        globalIsPaused = false
        globalUtteranceRef = null
        utteranceRef.current = null
        notifyListeners()
      }
    }

    const handlePause = () => {
      if (utteranceRef.current === globalUtteranceRef) {
        globalIsPaused = true
        notifyListeners()
      }
    }

    const handleResume = () => {
      if (utteranceRef.current === globalUtteranceRef) {
        globalIsPaused = false
        notifyListeners()
      }
    }

    utterance.addEventListener('start', handleStart)
    utterance.addEventListener('end', handleEnd)
    utterance.addEventListener('error', handleError)
    utterance.addEventListener('pause', handlePause)
    utterance.addEventListener('resume', handleResume)

    return () => {
      utterance.removeEventListener('start', handleStart)
      utterance.removeEventListener('end', handleEnd)
      utterance.removeEventListener('error', handleError)
      utterance.removeEventListener('pause', handlePause)
      utterance.removeEventListener('resume', handleResume)
    }
  }, [supported])

  /**
   * Speak text
   */
  const speak = useCallback((text, language = 'en', options = {}) => {
    if (!supported) {
      console.warn('Text-to-speech is not supported in this browser')
      return
    }

    // Cancel any ongoing speech
    window.speechSynthesis.cancel()
    globalUtteranceRef = null
    globalIsSpeaking = false
    globalIsPaused = false

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = getLanguageCode(language)
    utterance.rate = options.rate || 1.0
    utterance.pitch = options.pitch || 1.0
    utterance.volume = options.volume || 1.0

    utteranceRef.current = utterance
    globalUtteranceRef = utterance
    window.speechSynthesis.speak(utterance)
    notifyListeners()
  }, [supported])

  /**
   * Pause speaking
   */
  const pause = useCallback(() => {
    if (!supported || !isSpeaking) return
    window.speechSynthesis.pause()
  }, [supported, isSpeaking])

  /**
   * Resume speaking
   */
  const resume = useCallback(() => {
    if (!supported || !isPaused) return
    window.speechSynthesis.resume()
  }, [supported, isPaused])

  /**
   * Stop speaking
   */
  const stop = useCallback(() => {
    if (!supported) return
    window.speechSynthesis.cancel()
    if (utteranceRef.current === globalUtteranceRef) {
      globalIsSpeaking = false
      globalIsPaused = false
      globalUtteranceRef = null
      utteranceRef.current = null
      notifyListeners()
    }
  }, [supported])

  /**
   * Cancel all queued speech
   */
  const cancel = useCallback(() => {
    if (!supported) return
    window.speechSynthesis.cancel()
    globalIsSpeaking = false
    globalIsPaused = false
    globalUtteranceRef = null
    utteranceRef.current = null
    notifyListeners()
  }, [supported])

  return {
    supported,
    isSpeaking,
    isPaused,
    speak,
    pause,
    resume,
    stop,
    cancel,
  }
}

