const TELEGRAM_KEYS = [
  'tgWebAppData',
  'tgWebAppVersion',
  'tgWebAppPlatform',
  'tgWebAppBotInline',
  'tgWebAppThemeParams',
  'hash',
  'user',
  'auth_date',
  'query_id',
  'signature'
]

const TELEGRAM_KEY_RE = /^(?:tgWebAppData|tgWebAppVersion|tgWebAppPlatform|tgWebAppBotInline|tgWebAppThemeParams|hash|user|auth_date|query_id|signature)=/

const stripHashPrefix = (value) => {
  const withoutMarker = String(value || '').replace(/^[#?]/, '')
  return withoutMarker.startsWith('/') ? withoutMarker.slice(1) : withoutMarker
}

export function parseTelegramInitDataFromUrl(hash = '', search = '') {
  for (const source of [hash, search]) {
    if (!source) continue

    const body = stripHashPrefix(source)
    const params = new URLSearchParams(body)
    const data = params.get('tgWebAppData') || params.get('init_data')
    if (data) return data

    // Telegram can also expose the signed init data directly in the hash.
    if (params.has('hash') && (params.has('user') || params.has('query_id') || params.has('auth_date'))) {
      return body
    }

    // A route can precede Telegram's launch parameters, e.g.
    // #/search?tgWebAppData=... . Keep this fallback for that form.
    const match = body.match(/(?:^|[?&])tgWebAppData=([^&]+)/)
    if (match) return decodeURIComponent(match[1])
  }
  return ''
}

export function cleanTelegramHash(hash = '') {
  if (!hash || (!hash.includes('tgWebAppData=') && !hash.includes('tgWebAppVersion='))) {
    return hash
  }

  const raw = hash.replace(/^#/, '')
  const body = raw.startsWith('/') ? raw.slice(1) : raw
  let path = '/'
  let queryPart = body

  // Telegram may append its parameters after the hash-router slash:
  // #/tgWebAppData=...&tgWebAppVersion=... . In that form the first
  // parameter is not a route segment and must be parsed as query data.
  if (!TELEGRAM_KEY_RE.test(body)) {
    if (raw.startsWith('/')) {
      const queryIndex = raw.indexOf('?')
      if (queryIndex === -1) return hash
      path = raw.slice(0, queryIndex)
      queryPart = raw.slice(queryIndex + 1)
    } else {
      return hash
    }
  }

  const params = new URLSearchParams(queryPart)
  TELEGRAM_KEYS.forEach((key) => params.delete(key))
  const remaining = params.toString()
  return `#${path}${remaining ? `?${remaining}` : ''}`
}
