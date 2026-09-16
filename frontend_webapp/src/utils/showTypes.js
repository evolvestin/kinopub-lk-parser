const TYPE_ALIASES = {
  serial: 'Series',
  series: 'Series',
  movie: 'Movie',
  film: 'Movie',
  concert: 'Concert',
  documovie: 'Documentary Movie',
  'documentary movie': 'Documentary Movie',
  docuserial: 'Documentary Series',
  'documentary series': 'Documentary Series',
  tvshow: 'TV Show',
  'tv show': 'TV Show',
  '3d': '3D Movie',
  '3d movie': '3D Movie',
}

const TYPE_LABELS_RU = {
  Series: 'Сериал',
  Movie: 'Фильм',
  Concert: 'Концерт',
  'Documentary Movie': 'Док. фильм',
  'Documentary Series': 'Док. сериал',
  'TV Show': 'ТВ-шоу',
  '3D Movie': '3D фильм',
}

export const normalizeShowType = (value) => {
  const raw = String(value ?? '').trim()
  if (!raw) return ''
  return TYPE_ALIASES[raw.toLowerCase()] || raw
}

export const isSeriesType = (value) => {
  return ['Series', 'Documentary Series', 'TV Show'].includes(normalizeShowType(value))
}

export const showTypeRu = (value) => {
  const normalized = normalizeShowType(value)
  return TYPE_LABELS_RU[normalized] || normalized
}
