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
  const hasMoreShows = ref(true)
  const offset = ref(0)
  const limit = 30

  const searchQuery = computed({
    get() {
      return router.currentRoute.value.query.q || ''
    },
    set(val) {
      const query = { ...router.currentRoute.value.query }
      const oldVal = query.q || ''
      if (oldVal === val) return

      if (!val) {
        delete query.q
      } else {
        query.q = val
      }
      router.replace({ query }).catch(() => {})
    }
  })

  async function performSearch(query, isLoadMore = false) {
    if (query.length < 2) {
      clearSearch()
      return
    }
    isSearching.value = true
    hasSearched.value = true

    if (!isLoadMore) {
      offset.value = 0
      hasMoreShows.value = true
    }

    try {
      const data = await api.post('search/', { query, offset: offset.value, limit })
      if (searchQuery.value === query) {
        if (isLoadMore) {
          searchResults.value.shows.push(...(data.shows || []))
        } else {
          searchResults.value = {
            shows: data.shows || [],
            persons: data.persons || []
          }
        }
        hasMoreShows.value = data.has_more

        if (data.shows) {
          data.shows.forEach(s => s.poster_url && preloadImage(s.poster_url))
        }
        if (data.persons && !isLoadMore) {
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

  async function loadMore() {
    if (isSearching.value || !hasMoreShows.value || searchQuery.value.length < 2) {
      return
    }
    offset.value += limit
    await performSearch(searchQuery.value, true)
  }

  function clearSearch() {
    searchQuery.value = ''
    searchResults.value = { shows: [], persons: [] }
    hasSearched.value = false
    offset.value = 0
    hasMoreShows.value = true
  }

  watch(() => searchQuery.value, (newQuery) => {
    if (newQuery && newQuery.length >= 2) {
      performSearch(newQuery, false)
    } else {
      searchResults.value = { shows: [], persons: [] }
      hasSearched.value = false
      offset.value = 0
      hasMoreShows.value = true
    }
  }, { immediate: true })

  return { searchQuery, searchResults, isSearching, hasSearched, hasMoreShows, performSearch, loadMore, clearSearch }
})