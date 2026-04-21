import React from 'react'

export default function NewsNotifications({ onEvent }) {
  React.useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${proto}//${window.location.host}/api/news/notifications`
    let ws
    try {
      ws = new WebSocket(url)
    } catch (e) {
      return undefined
    }
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data)
        const title = data.title || data.article_id || 'News'
        if (onEvent) onEvent(`News: ${title} updated`)
      } catch {
        if (onEvent) onEvent('News channel message')
      }
    }
    return () => {
      try {
        ws.close()
      } catch {
        /* ignore */
      }
    }
  }, [onEvent])

  return null
}
