import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '../composables/useApi'
import { useUIStore } from './uiStore'

export const useDataStore = defineStore('data', () => {
  const api = useApi()
  const uiStore = useUIStore()

  const searchQuery = ref('')
  const searchResults = ref({ shows: [], persons: [] })
  const isSearching = ref(false)
  const hasSearched = ref(false)

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
      }
    } catch (error) {
      if (searchQuery.value === query) {
        uiStore.showToast('Ошибка при поиске')
        searchResults.value = { shows: [], persons: [] }
      }
    } finally {
      if (searchQuery.value === query) {
        isSearching.value = false
      }
    }
  }

  function clearSearch() {
    searchResults.value = { shows: [], persons: [] }
    hasSearched.value = false
    isSearching.value = false
  }

  return {
    searchQuery,
    searchResults,
    isSearching,
    hasSearched,
    performSearch,
    clearSearch
  }
})