import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { useApi } from '../composables/useApi'
import { useUIStore } from './uiStore'

export const useDataStore = defineStore('data', () => {
  const api = useApi()
  const uiStore = useUIStore()

  // Восстановление из sessionStorage
  const savedSearch = JSON.parse(sessionStorage.getItem('kp_search_cache') || '{"query":"","results":{"shows":[],"persons":[]}}')

  const searchQuery = ref(savedSearch.query)
  const searchResults = ref(savedSearch.results)
  const isSearching = ref(false)
  const hasSearched = ref(savedSearch.query.length > 0)

  // Авто-сохранение при изменениях
  watch([searchQuery, searchResults], () => {
    sessionStorage.setItem('kp_search_cache', JSON.stringify({
      query: searchQuery.value,
      results: searchResults.value
    }))
  }, { deep: true })

  async function performSearch(query) {
    if (query.length < 2) {
      clearSearch()
      return
    }
    searchQuery.value = query
    isSearching.value = true
    hasSearched.value = true

    try {
      const data = await api.post('search/', { query })
      if (searchQuery.value === query) {
        searchResults.value = data
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

  return { searchQuery, searchResults, isSearching, hasSearched, performSearch, clearSearch }
})
