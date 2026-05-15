import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '../composables/useApi'
import { useUIStore } from './uiStore'
import { useUserStore } from './userStore'
import { preloadImage } from '../utils/helpers'

export const useStatsStore = defineStore('stats', () => {
  const api = useApi()
  const uiStore = useUIStore()
  const userStore = useUserStore()

  const statsCache = ref(new Map())
  const activeTab = ref('personal')
  const currentYear = ref('all')
  const availableYears = ref([])
  const isPreloadingYears = ref(false)

  const currentStats = computed(() => statsCache.value.get(currentYear.value) || null)
  const hasGroup = computed(() => !!currentStats.value?.group)

  function _initializeResolvedUrls(data) {
    if (!data) return
    const categories = ['actors', 'directors', 'writers']
    
    categories.forEach(cat => {
      const category = data[cat]
      if (category) {
        ['series', 'others'].forEach(sub => {
          if (Array.isArray(category[sub])) {
            category[sub].forEach(p => { 
              p.resolvedUrl = p.photo_url || p.fallback_photo_url || null 
            })
          }
        })
      }
    })

    if (data.group?.members) {
      data.group.members.forEach(m => { 
        m.resolvedUrl = m.photo_url || null 
      })
    }
  }

  async function resolveAllImages(data) {
    if (!data) return

    const imagesToPreload = new Set()

    const history = [...(data.history_movies || []), ...(data.history_episodes || [])]
    history.slice(0, 100).forEach(item => {
      if (item.poster_url) imagesToPreload.add(item.poster_url)
    })

    const leaderCategories = ['actors', 'directors', 'writers']
    leaderCategories.forEach(cat => {
      const categoryData = data[cat]
      if (categoryData) {
        ['series', 'others'].forEach(subKey => {
          if (Array.isArray(categoryData[subKey])) {
            categoryData[subKey].forEach(person => {
              if (person.photo_url) imagesToPreload.add(person.photo_url)
              if (person.fallback_photo_url) imagesToPreload.add(person.fallback_photo_url)
            })
          }
        })
      }
    })

    if (Array.isArray(data.countries)) {
      data.countries.forEach(c => {
        if (c.photo_url) imagesToPreload.add(c.photo_url)
      })
    }

    if (data.group?.members) {
      data.group.members.forEach(m => {
        if (m.photo_url) imagesToPreload.add(m.photo_url)
      })
    }

    imagesToPreload.forEach(url => preloadImage(url))
  }

  async function fetchStats(year = 'all', isBackground = false) {
    const cached = statsCache.value.get(year)
    if (cached) {
      if (!isBackground) {
        currentYear.value = year
        resolveAllImages(cached)
      }
      return
    }

    if (!isBackground) uiStore.setLoading(true)

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

      _initializeResolvedUrls(data)
      statsCache.value.set(year, data)
      
      if (!isBackground) {
        currentYear.value = year
      }

      const reactiveData = statsCache.value.get(year)
      resolveAllImages(reactiveData)

      if (!isBackground && !isPreloadingYears.value) {
        triggerBackgroundPreload()
      }

    } catch (error) {
      if (!isBackground) uiStore.showToast('Ошибка загрузки данных')
    } finally {
      if (!isBackground) uiStore.setLoading(false)
    }
  }

  async function triggerBackgroundPreload() {
    if (isPreloadingYears.value) return
    isPreloadingYears.value = true
    for (const year of availableYears.value) {
      if (!statsCache.value.has(year)) {
        await new Promise(r => setTimeout(r, 1200))
        await fetchStats(year, true)
      }
    }
    isPreloadingYears.value = false
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

  return {
    statsCache, activeTab, currentYear, availableYears, currentStats, hasGroup,
    fetchStats, resolveAllImages, getHistoryByType,
    setActiveTab: (tab) => { activeTab.value = tab },
    setYear: (year) => fetchStats(year)
  }
})