import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '../composables/useApi'
import { useUIStore } from './uiStore'

export const useWishlistStore = defineStore('wishlist', () => {
  const api = useApi()
  const uiStore = useUIStore()

  const folders = ref([])
  const activeFolderId = ref(null)
  const sortMode = ref('default')
  const viewMode = ref(localStorage.getItem('kp_wl_view_mode') || 'grid')
  const isReorderFoldersMode = ref(false)

  const activeFolder = computed(() => 
    folders.value.find(f => f.id === activeFolderId.value) || folders.value[0] || null
  )

  const sortedItems = computed(() => {
    if (!activeFolder.value) return []
    return [...activeFolder.value.items] // Сортировку можно добавить позже по аналогии с оригиналом
  })

async function fetchWishlist() {
    try {
      const data = await api.post('wishlist/', { action: 'get' })
      folders.value = data.folders || []
      
      if (folders.value.length > 0) {
        if (!activeFolderId.value || !folders.value.some(f => f.id === activeFolderId.value)) {
          activeFolderId.value = folders.value[0].id
        }
      } else {
        activeFolderId.value = null
      }

      folders.value.forEach(f => {
        f.items.forEach(item => {
          if (item.poster_url) preloadImage(item.poster_url);
        });
      });
      
    } catch (error) {
      uiStore.showToast('Ошибка загрузки избранного')
    }
  }

  function setViewMode(mode) {
    viewMode.value = mode
    localStorage.setItem('kp_wl_view_mode', mode)
  }

  return {
    folders,
    activeFolderId,
    activeFolder,
    sortedItems,
    viewMode,
    isReorderFoldersMode,
    fetchWishlist,
    setViewMode
  }
})