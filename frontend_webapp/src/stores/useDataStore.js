import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useApi } from '../composables/useApi'
import { useUIStore } from './uiStore'
import { preloadImage } from '../utils/helpers'
import router from '../router'

export const useDataStore = defineStore('data', () => {
  const api = useApi()
  const uiStore = useUIStore()

  const searchResults = ref({ shows: [], persons: [] })
  const isSearching = ref(false)
  const hasSearched = ref(false)

  const searchQuery = computed({
    get() {
      return router.currentRoute.value.query.q || ''
    },
    set(val) {
      const query = { ...router.currentRoute.value.query }
      if (!val) {
        delete query.q
      } else {
        query.q = val
      }
      router.replace({ query })
    }
  })

  async function performSearch(query) {
    if (query.length < 2) {
      clearSearch()
      return
    }
    isSearching.value = true
    hasSearched.value = true

    try {
      const data = await api.post('search/', { query })
      if (searchQuery.value === query) {
        searchResults.value = data
        
        if (data.shows) {
          data.shows.forEach(s => s.poster_url && preloadImage(s.poster_url))
        }
        if (data.persons) {
          data.persons.forEach(p => {
            if (p.photo_url) preloadImage(p.photo_url)
            if (p.fallback_photo_url) preloadImage(p.fallback_photo_url)
          })
        }
      }
    } catch (error) {
      uiStore.showToast('Ошибка поиска')
    } finally {
      isSearching.value = false
    }
  }

  function clearSearch() {
    searchQuery.value = ''
    searchResults.value = { shows: [], persons: [] }
    hasSearched.value = false
  }

  watch(() => searchQuery.value, (newQuery) => {
    if (newQuery && newQuery.length >= 2) {
      performSearch(newQuery)
    } else {
      searchResults.value = { shows: [], persons: [] }
      hasSearched.value = false
    }
  }, { immediate: true })

  return { searchQuery, searchResults, isSearching, hasSearched, performSearch, clearSearch }
})