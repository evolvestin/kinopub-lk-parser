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
    const cacheKey = `stats_${year}`
    if (statsCache.value.has(cacheKey)) {
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

      statsCache.value.set(cacheKey, data)
      currentYear.value = year

      if (data.meta?.years) {
        availableYears.value = data.meta.years
      }
      
      if (data.meta?.photo_url && userStore.userData) {
        userStore.userData.photo_url = data.meta.photo_url
      }
    } catch (error) {
      uiStore.showToast(error.message)
    } finally {
      if (!isBackground) uiStore.setLoading(false)
    }
  }

  function setActiveTab(tab) {
    activeTab.value = tab
  }

  function setYear(year) {
    fetchStats(year)
  }

  return {
    statsCache,
    activeTab,
    currentYear,
    availableYears,
    currentStats,
    hasGroup,
    fetchStats,
    setActiveTab,
    setYear
  }
})