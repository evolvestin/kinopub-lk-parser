import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '../composables/useApi'
import { useUIStore } from './uiStore'
import { useUserStore } from './userStore'

export const useStatsStore = defineStore('stats', () => {
  const api = useApi()
  const uiStore = useUIStore()
  const userStore = useUserStore()

  const statsCache = ref(new Map())
  const activeTab = ref('personal')
  const currentYear = ref('all')
  const availableYears = ref([])

  const currentStats = computed(() => statsCache.value.get(currentYear.value) || null)
  const hasGroup = computed(() => !!currentStats.value?.group)

  async function fetchStats(year = 'all', isBackground = false) {
    if (!isBackground && statsCache.value.has(year)) {
      currentYear.value = year
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

      statsCache.value.set(year, data)
      currentYear.value = year

      if (data.meta) {
        let years = data.meta.years || []
        if (years.length > 0 && !years.includes('all')) {
          years = ['all', ...years]
        }
        availableYears.value = years
        
        if (data.meta.role) userStore.userRole = data.meta.role
        if (data.meta.photo_url && userStore.userData) {
          userStore.userData.photo_url = data.meta.photo_url
        }
      }
    } catch (error) {
      uiStore.showToast('Ошибка загрузки данных')
    } finally {
      if (!isBackground) uiStore.setLoading(false)
    }
  }

  async function removeHistoryItem(historyId) {
    try {
      await api.post('remove_view/', { view_history_id: historyId })
      
      statsCache.value.forEach(stat => {
        if (stat.history_movies) {
          stat.history_movies = stat.history_movies.filter(i => i.id !== historyId)
        }
        if (stat.history_episodes) {
          stat.history_episodes = stat.history_episodes.filter(i => i.id !== historyId)
        }
        if (stat.group) {
          if (stat.group.history_movies) {
            stat.group.history_movies = stat.group.history_movies.filter(i => i.id !== historyId)
          }
          if (stat.group.history_episodes) {
            stat.group.history_episodes = stat.group.history_episodes.filter(i => i.id !== historyId)
          }
        }
      })
      
      uiStore.showToast('Просмотр удален')
    } catch (e) {
      uiStore.showToast('Не удалось удалить')
    }
  }

  const getHistoryByType = (type, params = {}) => {
    const s = currentStats.value
    if (!s) return []
    
    if (type === 'all') {
      return [...s.history_movies, ...s.history_episodes].sort((a, b) => b.view_date.localeCompare(a.view_date))
    }
    if (type === 'movies') return s.history_movies || []
    if (type === 'episodes') return s.history_episodes || []
    if (type === 'ratings') return s.ratings?.history || []
    if (type === 'wishlist_watched') return s.wishlist_watched_items || []
    if (type === 'casino') return s.casino_history || []
    
    if (type === 'day') {
      return [...s.history_movies, ...s.history_episodes].filter(i => i.view_date === params.date)
    }
    
    if (type === 'weekday') {
      return [...s.history_movies, ...s.history_episodes].filter(item => {
        const dateStr = item.view_date || item.date
        if (!dateStr) return false
        const [y, m, d] = dateStr.split('-').map(Number)
        const date = new Date(y, m - 1, d)
        const jsDay = date.getDay()
        const kpDay = (jsDay === 0 ? 6 : jsDay - 1)
        return kpDay === params.idx
      }).sort((a, b) => b.view_date.localeCompare(a.view_date))
    }

    if (type === 'rating_filter') {
      return (s.ratings?.history || []).filter(item => {
        let b = Math.floor(item.rating)
        if (b < 1) b = 1
        return b === params.idx
      })
    }

    if (type === 'filter' && params.key) {
      const isGroup = params.key.startsWith('group_')
      const source = isGroup ? s.group : s
      const pool = isGroup ? [...source.history_movies, ...source.history_episodes] : [...s.history_movies, ...s.history_episodes]
      
      const keyParts = params.key.replace('group_', '').split('_')
      let itemsList = []
      
      if (keyParts.length === 2) {
          itemsList = s[keyParts[0]]?.[keyParts[1]] || []
      } else {
          itemsList = source[keyParts[0]] || []
      }

      const entry = itemsList[params.idx]
      const allowedIds = entry?.show_ids || []
      return pool.filter(i => allowedIds.includes(i.show_id)).sort((a, b) => b.view_date.localeCompare(a.view_date))
    }

    if (type === 'group_member' && s.group?.members) {
      const member = s.group.members[params.idx]
      if (!member) return []
      return [...s.group.history_movies, ...s.group.history_episodes]
        .filter(item => item.user_ids.includes(member.id))
        .sort((a, b) => b.view_date.localeCompare(a.view_date))
    }

    if (type === 'binge') {
        return s.history_episodes.filter(i => i.show_id === params.showId && i.view_date === params.date)
          .sort((a, b) => (a.season_number - b.season_number) || (a.episode_number - b.episode_number))
    }
    
    return []
  }

  return {
    statsCache, activeTab, currentYear, availableYears, currentStats, hasGroup,
    fetchStats, getHistoryByType, removeHistoryItem,
    setActiveTab: (tab) => { activeTab.value = tab },
    setYear: (year) => fetchStats(year)
  }
})