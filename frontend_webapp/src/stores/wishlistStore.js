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
  const isReorderItemsMode = ref(false)
  const isSortMenuOpen = ref(false)

  const activeFolder = computed(() => 
    folders.value.find(f => f.id === activeFolderId.value) || null
  )

  const sortedItems = computed(() => {
    if (!activeFolder.value) return []
    const items = [...activeFolder.value.items]

    if (sortMode.value === 'default') return items

    return items.sort((a, b) => {
      if (sortMode.value.startsWith('added')) {
        const dateA = new Date(a.added_at)
        const dateB = new Date(b.added_at)
        return sortMode.value.endsWith('desc') ? dateB - dateA : dateA - dateB
      }
      if (sortMode.value.startsWith('year')) {
        const yearA = a.year || 0
        const yearB = b.year || 0
        return sortMode.value.endsWith('desc') ? yearB - yearA : yearA - yearB
      }
      return 0
    })
  })

  async function fetchWishlist() {
    try {
      const data = await api.post('wishlist/', { action: 'get' })
      folders.value = data.folders || []
      
      if (!activeFolderId.value && folders.value.length > 0) {
        activeFolderId.value = folders.value[0].id
      }
    } catch (error) {
      uiStore.showToast('Ошибка загрузки избранного')
    }
  }

  function setViewMode(mode) {
    viewMode.value = mode
    localStorage.setItem('kp_wl_view_mode', mode)
  }

  async function deleteItem(itemId, keepStats = true) {
    try {
      await api.post('wishlist/', { 
        action: 'remove_item', 
        item_id: itemId, 
        keep_stats: keepStats 
      })
      
      if (activeFolder.value) {
        activeFolder.value.items = activeFolder.value.items.filter(i => i.id !== itemId)
      }
    } catch (error) {
      uiStore.showToast('Ошибка при удалении')
    }
  }

  async function toggleFolderDelete(folderId) {
    try {
      await api.post('wishlist/', { action: 'delete_folder', folder_id: folderId })
      folders.value = folders.value.filter(f => f.id !== folderId)
      if (activeFolderId.value === folderId) {
        activeFolderId.value = folders.value[0]?.id || null
      }
      uiStore.showToast('Папка удалена')
    } catch (error) {
      uiStore.showToast('Ошибка при удалении папки')
    }
  }

  async function reorderFolders(order) {
    try {
      await api.post('wishlist/', { action: 'reorder_folders', order })
    } catch (e) {
      console.error('Reorder folders failed', e)
    }
  }

  async function reorderItems(folderId, order) {
    try {
      await api.post('wishlist/', { action: 'reorder_items', folder_id: folderId, order })
    } catch (e) {
      console.error('Reorder items failed', e)
    }
  }

  return {
    folders,
    activeFolderId,
    activeFolder,
    sortedItems,
    sortMode,
    viewMode,
    isReorderFoldersMode,
    isReorderItemsMode,
    isSortMenuOpen,
    fetchWishlist,
    setViewMode,
    deleteItem,
    toggleFolderDelete,
    reorderFolders,
    reorderItems
  }
})