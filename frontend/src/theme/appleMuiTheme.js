import { createTheme } from '@mui/material/styles'

export const APPLE_FONT_STACK =
  '-apple-system, BlinkMacSystemFont, "SF Pro Text", ' +
  '"SF Pro Display", "Segoe UI", Roboto, "Helvetica Neue", Arial, ' +
  'sans-serif'

export function createAppleLightTheme() {
  return createTheme({
    palette: {
      mode: 'light',
      primary: { main: '#007AFF' },
      secondary: { main: '#5856D6' },
      error: { main: '#FF3B30' },
      background: {
        default: '#F2F2F7',
        paper: '#FFFFFF',
      },
      divider: 'rgba(60, 60, 67, 0.12)',
      text: {
        primary: '#000000',
        secondary: 'rgba(60, 60, 67, 0.6)',
      },
    },
    typography: {
      fontFamily: APPLE_FONT_STACK,
      h4: { fontWeight: 600 },
      h5: { fontWeight: 600 },
    },
    shape: { borderRadius: 12 },
  })
}

export function createAppleDarkTheme() {
  return createTheme({
    palette: {
      mode: 'dark',
      primary: { main: '#0A84FF' },
      secondary: { main: '#5E5CE6' },
      error: { main: '#FF453A' },
      background: {
        default: '#000000',
        paper: '#1C1C1E',
      },
      divider: 'rgba(84, 84, 88, 0.65)',
      text: {
        primary: '#FFFFFF',
        secondary: 'rgba(235, 235, 245, 0.6)',
      },
    },
    typography: {
      fontFamily: APPLE_FONT_STACK,
      h4: { fontWeight: 600 },
      h5: { fontWeight: 600 },
    },
    shape: { borderRadius: 12 },
  })
}
