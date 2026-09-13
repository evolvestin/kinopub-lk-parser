import { defineStore } from 'pinia'
import { ref, computed, markRaw, watch } from 'vue'
import { useApi } from '../composables/useApi'
import { useUIStore } from './uiStore'
import { useUserStore } from './userStore'
import router from '../router'

export const useStatsStore = defineStore('stats', () => {
  const api = useApi()
  const uiStore = useUIStore()
  const userStore = useUserStore()

  const statsCache = ref({})
  const sharedDataMap = ref({})
  const availableYears = ref([])
  const optimisticRatings = ref({})
  const pendingRequests = ref(0)
  const statsError = ref(null)
  const isLoading = computed(() => pendingRequests.value > 0)

  const currentYear = computed({
    get() {
      return router.currentRoute.value.query.y || 'all'
    },
    set(val) {
      const query = { ...router.currentRoute.value.query }
      const oldVal = query.y || 'all'
      if (oldVal === val) return

      if (val === 'all') {
        delete query.y
      } else {
        query.y = val
      }
      router.replace({ query }).catch(() => {})
    }
  })

  const activeTab = computed({
    get() {
      return router.currentRoute.value.query.tab || 'personal'
    },
    set(val) {
      const query = { ...router.currentRoute.value.query }
      const oldVal = query.tab || 'personal'
      if (oldVal === val) return

      if (val === 'personal') {
        delete query.tab
      } else {
        query.tab = val
      }
      // Stats tabs belong to the stats route. Keeping the route explicit also
      // makes the action resilient if a cached keep-alive view briefly lags
      // behind the router during a hot update.
      const path = router.currentRoute.value.path.startsWith('/stats')
        ? router.currentRoute.value.path
        : '/stats'
      router.replace({ path, query }).catch(() => {})
    }
  })

  const isShared = computed(() => !!router.currentRoute.value.query.shared_id)
  const sharedId = computed(() => router.currentRoute.value.query.shared_id || null)

  const currentStats = computed(() => {
    if (isShared.value && sharedId.value) {
      const cacheKey = `shared_${sharedId.value}_${currentYear.value}`
      return statsCache.value[cacheKey] || null
    }
    return statsCache.value[currentYear.value] || null
  })

  const hasGroup = computed(() => !!(currentStats.value?.group || currentStats.value?.meta?.has_group))

  const userShowRatings = computed(() => {
    const ratingsMap = {}
    Object.keys(statsCache.value).forEach(key => {
      if (key.startsWith('shared_')) return
      const stats = statsCache.value[key]
      if (stats?.ratings?.history) {
        stats.ratings.history.forEach(r => {
          if (r.show_id && r.rating && !r.season && !r.episode) {
            ratingsMap[r.show_id] = r.rating
          }
        })
      }
    })
    Object.entries(optimisticRatings.value).forEach(([showId, rating]) => {
      if (rating === null) {
        delete ratingsMap[showId]
      } else {
        ratingsMap[showId] = rating
      }
    })
    return ratingsMap
  })

  const sharedShowRatings = computed(() => {
    const ratingsMap = {}
    if (isShared.value && sharedId.value) {
      Object.keys(statsCache.value).forEach(key => {
        if (key.startsWith(`shared_${sharedId.value}_`)) {
          const stats = statsCache.value[key]
          if (stats?.ratings?.history) {
            stats.ratings.history.forEach(r => {
              if (r.show_id && r.rating && !r.season && !r.episode) {
                ratingsMap[r.show_id] = r.rating
              }
            })
          }
        }
      })
    }
    return ratingsMap
  })

  function setOptimisticRating(showId, rating) {
    if (rating === null) {
      optimisticRatings.value[showId] = null
    } else {
      optimisticRatings.value[showId] = rating
    }
  }

  function clearOptimisticRatings() {
    optimisticRatings.value = {}
  }

  const activeRequests = {}

  async function fetchSharedStats(statId, year = 'all', isBackground = false) {
    const cacheKey = `shared_${statId}_${year}`
    if (statsCache.value[cacheKey]) {
      if (!isBackground) {
        currentYear.value = year
      }
      return statsCache.value[cacheKey]
    }

    pendingRequests.value += 1
    statsError.value = null
    try {
      if (!sharedDataMap.value[statId]) {
        const res = await api.get(`shared_stats/${statId}/`)
        sharedDataMap.value[statId] = res.data
        if (res.metadata?.years) {
          let years = res.metadata.years || []
          if (years.length > 0 && !years.includes('all')) years = ['all', ...years]
          availableYears.value = years
        }
      }

      const yearData = sharedDataMap.value[statId][year]
      if (yearData) {
        statsCache.value[cacheKey] = markRaw(yearData)
        if (!isBackground) {
          currentYear.value = year
          clearOptimisticRatings()
        }
        return yearData
      }
    } catch (error) {
      console.error('[StatsStore] Shared fetch error:', error)
      statsError.value = error
      if (!isBackground) uiStore.showToast('Ошибка загрузки общей статистики')
    } finally {
      pendingRequests.value = Math.max(0, pendingRequests.value - 1)
    }
  }

  async function fetchStats(
    year = 'all',
    isBackground = false,
    force = false,
    includeGroup = activeTab.value === 'group'
  ) {
    if (isShared.value && sharedId.value) {
      return fetchSharedStats(sharedId.value, year, isBackground)
    }

    if (statsCache.value[year] && !force) {
      if (!isBackground) {
        currentYear.value = year
      }
      return statsCache.value[year]
    }

    if (activeRequests[year]) {
      const promise = activeRequests[year]
      if (!isBackground) {
        const data = await promise
        currentYear.value = year
        return data
      }
      return promise
    }

    pendingRequests.value += 1
    statsError.value = null

    const promise = (async () => {
      try {
        const data = await api.post('detailed_stats/', {
          period_type: 'year',
          period_value: year === 'all' ? 0 : year,
          include_group: includeGroup,
          screen_width: window.innerWidth,
          screen_height: window.innerHeight
        })

        if (data.meta) {
          let years = data.meta.years || []
          if (years.length > 0 && !years.includes('all')) years = ['all', ...years]
          availableYears.value = years
          if (data.meta.role) userStore.userRole = data.meta.role
          
          if (data.meta.is_anonymous !== undefined) userStore.isAnonymous = data.meta.is_anonymous
          if (data.meta.privacy_choice_made !== undefined) userStore.privacyChoiceMade = data.meta.privacy_choice_made
        }

        statsCache.value[year] = markRaw(data)
        return data
      } finally {
        delete activeRequests[year]
        pendingRequests.value = Math.max(0, pendingRequests.value - 1)
      }
    })()

    activeRequests[year] = promise

    try {
      const data = await promise
      if (!isBackground) {
        currentYear.value = year
      }
      clearOptimisticRatings()
      return data
    } catch (error) {
      console.error('[StatsStore] Fetch error:', error)
      statsError.value = error
      if (!isBackground) uiStore.showToast('Ошибка загрузки данных')
      throw error
    }
  }

  async function prefetchInitialStats() {
    const year = currentYear.value
    try {
      const data = await fetchStats(year, true, false, activeTab.value === 'group')

      // Warm the group tab after the personal response tells us that a group
      // exists. It remains fully background work and replaces the same cache
      // entry with the richer payload when complete.
      if (data?.meta?.has_group && !data.group) {
        await fetchStats(year, true, true, true)
      }
    } catch (error) {
      console.warn('[StatsStore] Background stats prefetch failed:', error)
    }
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

    if (layerHistoryId === 'wishlist_watched') {
      Object.keys(statsCache.value).forEach(year => {
        const stats = statsCache.value[year]
        if (stats && Array.isArray(stats.wishlist_watched_items)) {
          const filtered = stats.wishlist_watched_items.filter(item => item.wl_item_id !== historyId)
          
          const newSummary = { ...stats.summary }
          if (filtered.length !== stats.wishlist_watched_items.length) {
            if (newSummary.wishlist_watched > 0) newSummary.wishlist_watched--
          }

          statsCache.value[year] = markRaw({
            ...stats,
            summary: newSummary,
            wishlist_watched_items: filtered
          })
        }
      })
      
      uiStore.showToast('Удалено из статистики')
      
      try {
        await api.post('wishlist/', {
          action: 'remove_item',
          item_id: historyId,
          keep_stats: false,
          is_stat_removal: true
        })
      } catch (error) {
        console.error('[StatsStore] Failed to remove wishlist watched item:', error)
        uiStore.showToast('Не удалось удалить')
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

    Object.keys(uiStore.showsCache).forEach(showId => {
      const show = uiStore.showsCache[showId]
      if (show && Array.isArray(show.view_history)) {
        const filtered = show.view_history.filter(item => item.id !== historyId)
        if (filtered.length !== show.view_history.length) {
          show.view_history = filtered
          delete uiStore.episodesCache[showId]
          if (filtered.length > 0) {
            const myLast = filtered[0]
            let se_suffix = ''
            if (myLast.season_number > 0) {
              const epStr = myLast.episode_number < 10 ? `0${myLast.episode_number}` : myLast.episode_number
              se_suffix = ` (s${myLast.season_number}e${epStr})`
            }
            show.last_view = { display: `${myLast.view_date}${se_suffix}` }
          } else {
            show.last_view = null
          }
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
      case 'show_history': {
        if (isShared.value) {
            const D_show = currentStats.value
            if (!D_show) return []
            const pool_show = [...(D_show.history_movies || []), ...(D_show.history_episodes || [])]
            return pool_show.filter(i => i.show_id === showId)
              .sort((a, b) => b.view_date.localeCompare(a.view_date))
        } else {
            return uiStore.showsCache[showId]?.view_history || []
        }
      }
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
      fetchStats(newYear, true)
    }
  })

  watch(() => activeTab.value, (newTab) => {
    const stats = currentStats.value
    if (newTab === 'group' && stats?.meta?.has_group && !stats.group) {
      fetchStats(currentYear.value, true, true, true)
    }
  })

  return {
    statsCache, activeTab, currentYear, availableYears, currentStats, hasGroup, isShared, sharedId,
    isLoading, statsError,
    userShowRatings, sharedShowRatings, setOptimisticRating, clearOptimisticRatings,
    fetchStats, prefetchInitialStats, getHistoryByType, removeHistoryItem, fetchCasinoHistory,
    setActiveTab: (tab) => { activeTab.value = tab },
    setYear: (year) => { currentYear.value = year }
  }
})
