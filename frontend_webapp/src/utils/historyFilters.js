export function getHistoryDate(item) {
  const value = item?.raw_date || item?.view_date || item?.date || ''
  return String(value).slice(0, 10)
}

export function getHistoryPool(stats) {
  return [
    ...(Array.isArray(stats?.history_movies) ? stats.history_movies : []),
    ...(Array.isArray(stats?.history_episodes) ? stats.history_episodes : []),
  ]
}

export function sortHistory(items) {
  return [...items].sort((a, b) =>
    getHistoryDate(b).localeCompare(getHistoryDate(a)) || Number(b.id || 0) - Number(a.id || 0)
  )
}

export function buildGenreFilterItems(genres) {
  const sorted = (Array.isArray(genres) ? genres : [])
    .map((genre) => ({ ...genre, minutes: Number(genre.minutes) || 0 }))
    .sort((a, b) => b.minutes - a.minutes)

  const top = sorted.slice(0, 10)
  const totalMinutes = sorted.reduce((sum, genre) => sum + genre.minutes, 0)
  const topMinutes = top.reduce((sum, genre) => sum + genre.minutes, 0)

  if (totalMinutes > topMinutes) {
    top.push({
      name: 'Другие',
      minutes: totalMinutes - topMinutes,
      show_ids: [...new Set(sorted.slice(10).flatMap((genre) => genre.show_ids || []))],
    })
  }

  return top
}

export function findStatItem(items, index, name) {
  if (!Array.isArray(items)) return null
  if (name) {
    const byName = items.find((item) => item?.name === name)
    if (byName) return byName
  }
  return items[index] || null
}
