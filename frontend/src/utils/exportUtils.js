/**
 * Export search results to CSV
 * 
 * @param {Array} results - Array of quote pairs
 * @param {string} filename - Output filename
 */
export const exportToCSV = (results, filename = 'quotes_export.csv') => {
  if (!results || results.length === 0) {
    alert('No quotes to export')
    return
  }

  // Prepare CSV data - two columns: EN quote + author, RU quote + author
  const headers = ['English Quote', 'Russian Quote']
  const rows = results.map(pair => {
    // Column 1: English quote text + dot + Author name in English
    let enColumn = ''
    if (pair.english?.text) {
      enColumn = pair.english.text
      if (pair.english?.author?.name) {
        enColumn += '. ' + pair.english.author.name
      }
    }
    
    // Column 2: Russian quote text + dot + Author name in Russian
    let ruColumn = ''
    if (pair.russian?.text) {
      ruColumn = pair.russian.text
      if (pair.russian?.author?.name) {
        ruColumn += '. ' + pair.russian.author.name
      }
    }
    
    return [enColumn, ruColumn]
  })

  // Escape CSV values
  const escapeCSV = (value) => {
    if (value === null || value === undefined) return ''
    const stringValue = String(value)
    if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
      return `"${stringValue.replace(/"/g, '""')}"`
    }
    return stringValue
  }

  // Build CSV content
  const csvContent = [
    headers.map(escapeCSV).join(','),
    ...rows.map(row => row.map(escapeCSV).join(','))
  ].join('\n')

  // Add UTF-8 BOM for proper encoding recognition (especially for Excel)
  // BOM helps Excel and other programs recognize UTF-8 encoding
  const BOM = '\uFEFF'
  const csvWithBOM = BOM + csvContent

  // Use TextEncoder for proper UTF-8 encoding
  // This ensures Russian characters are correctly encoded
  const encoder = new TextEncoder()
  const encodedContent = encoder.encode(csvWithBOM)

  // Create blob with UTF-8 encoded content
  const blob = new Blob([encodedContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  
  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

/**
 * Copy text to clipboard
 * 
 * @param {string} text - Text to copy
 * @returns {Promise<boolean>} - Success status
 */
export const copyToClipboard = async (text) => {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    } else {
      // Fallback for older browsers
      const textArea = document.createElement('textarea')
      textArea.value = text
      textArea.style.position = 'fixed'
      textArea.style.left = '-999999px'
      document.body.appendChild(textArea)
      textArea.focus()
      textArea.select()
      const successful = document.execCommand('copy')
      document.body.removeChild(textArea)
      return successful
    }
  } catch (err) {
    console.error('Failed to copy text:', err)
    return false
  }
}

