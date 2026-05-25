import { defineStore } from 'pinia'
import { ref, computed, markRaw, watch } from 'vue'
import { useApi } from '../composables/useApi'
import { useUIStore } from './uiStore'
import { useUserStore } from './userStore'
import { preloadImage } from '../utils/helpers'
import router from '../router'

export const useStatsStore = defineStore('stats', () => {
  const api = useApi()
  const uiStore = useUIStore()
  const userStore = useUserStore()

  const statsCache = ref({})
  const availableYears = ref([])
  const isPreloadingYears = ref(false)

  const currentYear = computed({
    get() {
      return router.currentRoute.value.query.y || 'all'
    },
    set(val) {
      const query = { ...router.currentRoute.value.query }
      if (val === 'all') {
        delete query.y
      } else {
        query.y = val
      }
      router.replace({ query })
    }
  })

  const activeTab = computed({
    get() {
      return router.currentRoute.value.query.tab || 'personal'
    },
    set(val) {
      const query = { ...router.currentRoute.value.query }
      if (val === 'personal') {
        delete query.tab
      } else {
        query.tab = val
      }
      router.replace({ query })
    }
  })

  const currentStats = computed(() => statsCache.value[currentYear.value] || null)
  const hasGroup = computed(() => !!currentStats.value?.group)

  async function resolveAllImages(data) {
    if (!data) return

    const history = [...(data.history_movies || []), ...(data.history_episodes || [])]
    history.slice(0, 100).forEach(item => {
      if (item.poster_url) preloadImage(item.poster_url)
    })

    const leaderCategories = ['actors', 'directors', 'writers']
    leaderCategories.forEach(cat => {
      const categoryData = data[cat]
      if (!categoryData) return

      ['series', 'others'].forEach(subKey => {
        const persons = categoryData[subKey]
        if (Array.isArray(persons)) {
          persons.forEach(person => {
            if (person.photo_url) {
              preloadImage(person.photo_url).then(success => {
                if (!success && person.fallback_photo_url) {
                  preloadImage(person.fallback_photo_url)
                }
              })
            } else if (person.fallback_photo_url) {
              preloadImage(person.fallback_photo_url)
            }
          })
        }
      })
    })

    if (Array.isArray(data.countries)) {
      data.countries.forEach(c => {
        if (c.photo_url) preloadImage(c.photo_url)
      })
    }

    if (Array.isArray(data.binges)) {
      data.binges.forEach(b => {
        if (b.poster_url) preloadImage(b.poster_url)
      })
    }

    if (data.group?.members) {
      data.group.members.forEach(m => {
        if (m.photo_url) preloadImage(m.photo_url)
      })
    }
    
    if (Array.isArray(data.wishlist_watched_items)) {
      data.wishlist_watched_items.forEach(item => {
        if (item.poster_url) preloadImage(item.poster_url)
      })
    }
  }

  const activeRequests = {}

  async function fetchStats(year = 'all', isBackground = false) {
    if (statsCache.value[year]) {
      if (!isBackground) {
        currentYear.value = year
        resolveAllImages(statsCache.value[year])
      }
      return statsCache.value[year]
    }

    if (activeRequests[year]) {
      const promise = activeRequests[year]
      if (!isBackground) {
        uiStore.setLoading(true)
        try {
          const data = await promise
          currentYear.value = year
          resolveAllImages(data)
          return data
        } finally {
          uiStore.setLoading(false)
        }
      }
      return promise
    }

    if (!isBackground) uiStore.setLoading(true)

    const promise = (async () => {
      try {
        const data = await api.post('detailed_stats/', {
          period_type: 'year',
          period_value: year === 'all' ? 0 : year,
          screen_width: window.innerWidth,
          screen_height: window.innerHeight
        })

        if (data.meta) {
          let years = data.meta.years || []
          if (years.length > 0 && !years.includes('all')) years = ['all', ...years]
          availableYears.value = years
          if (data.meta.role) userStore.userRole = data.meta.role
        }

        statsCache.value[year] = markRaw(data)
        return data
      } finally {
        delete activeRequests[year]
      }
    })()

    activeRequests[year] = promise

    try {
      const data = await promise
      if (!isBackground) {
        currentYear.value = year
        resolveAllImages(data)
      }
      if (!isBackground && !isPreloadingYears.value) {
        triggerBackgroundPreload()
      }
      return data
    } catch (error) {
      console.error('[StatsStore] Fetch error:', error)
      if (!isBackground) uiStore.showToast('Ошибка загрузки данных')
      throw error
    } finally {
      if (!isBackground) uiStore.setLoading(false)
    }
  }

  async function triggerBackgroundPreload() {
    if (isPreloadingYears.value) return
    isPreloadingYears.value = true
    for (const year of availableYears.value) {
      if (!statsCache.value[year]) {
        await new Promise(r => setTimeout(r, 1200))
        await fetchStats(year, true)
      }
    }
    isPreloadingYears.value = false
  }

  async function removeHistoryItem(historyId, layerHistoryId = '') {
    const originalCache = JSON.parse(JSON.stringify(statsCache.value))

    if (layerHistoryId === 'casino') {
      Object.keys(statsCache.value).forEach(year => {
        const stats = statsCache.value[year]
        if (stats && Array.isArray(stats.casino_history)) {
          const filtered = stats.casino_history.filter(item => item.id !== historyId)
          statsCache.value[year] = markRaw({
            ...stats,
            casino_history: filtered
          })
        }
      })
      uiStore.showToast('Запись удалена')
      try {
        await api.post('casino/', { action: 'delete_spin', spin_id: historyId })
      } catch (error) {
        console.error('[StatsStore] Failed to hide casino spin:', error)
        statsCache.value = originalCache
      }
      return
    }

    Object.keys(statsCache.value).forEach(year => {
      const stats = statsCache.value[year]
      if (stats) {
        let updated = false
        let history_movies = stats.history_movies
        let history_episodes = stats.history_episodes

        if (Array.isArray(history_movies)) {
          const filtered = history_movies.filter(item => item.id !== historyId)
          if (filtered.length !== history_movies.length) {
            history_movies = filtered
            updated = true
          }
        }
        if (Array.isArray(history_episodes)) {
          const filtered = history_episodes.filter(item => item.id !== historyId)
          if (filtered.length !== history_episodes.length) {
            history_episodes = filtered
            updated = true
          }
        }

        if (updated) {
          statsCache.value[year] = markRaw({
            ...stats,
            history_movies,
            history_episodes
          })
        }
      }
    })

    uiStore.showToast('Просмотр удален')

    try {
      await api.post('remove_view/', { view_history_id: historyId })
    } catch (error) {
      console.error('[StatsStore] Failed to remove history item:', error)
      uiStore.showToast('Не удалось удалить просмотр на сервере')
      statsCache.value = originalCache
    }
  }

  async function fetchCasinoHistory() {
    if (!currentStats.value) return
    if (currentStats.value.casino_history) return

    try {
      const data = await api.post('casino/', { action: 'history' })
      const year = currentYear.value
      statsCache.value[year] = markRaw({
        ...statsCache.value[year],
        casino_history: data.history || []
      })
    } catch (error) {
      console.error('[StatsStore] Failed to fetch casino history:', error)
    }
  }

  function getHistoryByType(type, { date, idx, key, showId }) {
    const D = currentStats.value
    if (!D) return []

    switch (type) {
      case 'all':
        return [...(D.history_movies || []), ...(D.history_episodes || [])]
          .sort((a, b) => b.view_date.localeCompare(a.view_date))
      case 'movies':
        return D.history_movies || []
      case 'episodes':
        return D.history_episodes || []
      case 'ratings':
        return D.ratings?.history || []
      case 'wishlist_watched':
        return D.wishlist_watched_items || []
      case 'casino':
        return D.casino_history || []
      case 'day':
        return [...(D.history_movies || []), ...(D.history_episodes || [])]
          .filter(i => i.view_date === date)
      case 'binge':
        return (D.history_episodes || [])
          .filter(i => i.show_id === showId && i.view_date === date)
          .sort((a, b) => {
            if (a.season_number !== b.season_number) return a.season_number - b.season_number
            return a.episode_number - b.episode_number
          })
      case 'weekday':
        return [...(D.history_movies || []), ...(D.history_episodes || [])]
          .filter(item => {
            const d = new Date(item.view_date)
            const jsDay = d.getDay()
            return (jsDay === 0 ? 6 : jsDay - 1) === idx
          }).sort((a, b) => b.view_date.localeCompare(a.view_date))
      case 'rating_filter':
        return (D.ratings?.history || []).filter(item => Math.floor(item.rating || 1) === idx)
      case 'group_member':
        const member = D.group?.members?.[idx]
        return [...(D.group?.history_movies || []), ...(D.group?.history_episodes || [])]
          .filter(item => item.user_ids?.includes(member?.id))
          .sort((a, b) => b.view_date.localeCompare(a.view_date))
      case 'filter':
        const isGroup = key?.startsWith('group_')
        const poolKey = key?.replace('group_', '')
        const source = isGroup ? D.group : D
        const pool = [...(source.history_movies || []), ...(source.history_episodes || [])]

        let targetItem = null
        if (poolKey === 'genres_top') targetItem = source.genres?.[idx]
        else if (poolKey?.includes('_')) {
          const [cat, sub] = poolKey.split('_')
          targetItem = D[cat]?.[sub]?.[idx]
        } else {
          targetItem = D[poolKey]?.[idx]
        }

        const allowedIds = targetItem?.show_ids || []
        return pool.filter(i => allowedIds.includes(i.show_id))
          .sort((a, b) => b.view_date.localeCompare(a.view_date))
      case 'show_history':
        return key || []
      default:
        return []
    }
  }

  watch(() => currentYear.value, (newYear) => {
    if (newYear && !statsCache.value[newYear]) {
      fetchStats(newYear)
    }
  })

  return {
    statsCache, activeTab, currentYear, availableYears, currentStats, hasGroup,
    fetchStats, resolveAllImages, getHistoryByType, removeHistoryItem, fetchCasinoHistory,
    setActiveTab: (tab) => { activeTab.value = tab },
    setYear: (year) => { currentYear.value = year }
  }
})