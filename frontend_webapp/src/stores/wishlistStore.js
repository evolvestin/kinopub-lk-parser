import { defineStore } from 'pinia'
import { ref, computed, markRaw } from 'vue'
import { useApi } from '../composables/useApi'
import { useUIStore } from './uiStore'
import { preloadImage } from '../utils/helpers'

export const useWishlistStore = defineStore('wishlist', () => {
  const api = useApi()
  const uiStore = useUIStore()

  const folders = ref([])
  const activeFolderId = ref(null)
  const sortMode = ref(localStorage.getItem('kp_wl_sort_mode') || 'default')
  const viewMode = ref(localStorage.getItem('kp_wl_view_mode') || 'grid')
  const isReorderFoldersMode = ref(false)
  const isReorderItemsMode = ref(false)

  const FOLDER_COLORS = [
    '#388bfd', '#2ecc71', '#e74c3c', '#f1c40f', '#9b59b6', '#e67e22', '#1abc9c', '#95a5a6', '#fd79a8'
  ]

  const FOLDER_ICONS = [
    'bookmark', 'folder', 'heart', 'star', 'bookmark_plus', 'check', 'search',
    'film', 'video', 'play_circle', 'tv', 'monitor', 'ticket', 'award',
    'user', 'users', 'smile', 'frown', 'music', 'coffee', 'globe',
    'zap', 'flame', 'rocket', 'eye', 'ghost', 'skull', 'trash',
    'clock', 'cal', 'days', 'list', 'target', 'chart', 'help'
  ]

  const activeFolder = computed(() => 
    folders.value.find(f => f.id === activeFolderId.value) || folders.value[0] || null
  )

  const sortedItems = computed(() => {
    if (!activeFolder.value) return []
    const itemsCopy = [...activeFolder.value.items]
    if (sortMode.value === 'added_desc') {
      return itemsCopy.sort((a, b) => new Date(b.added_at) - new Date(a.added_at) || b.id - a.id)
    } else if (sortMode.value === 'added_asc') {
      return itemsCopy.sort((a, b) => new Date(a.added_at) - new Date(b.added_at) || a.id - b.id)
    } else if (sortMode.value === 'year_desc') {
      return itemsCopy.sort((a, b) => (b.year || 0) - (a.year || 0) || b.id - a.id)
    } else if (sortMode.value === 'year_asc') {
      return itemsCopy.sort((a, b) => (a.year || 0) - (b.year || 0) || a.id - b.id)
    }
    return itemsCopy
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
          if (item.poster_url) preloadImage(item.poster_url)
        })
      })
    } catch (error) {
      uiStore.showToast('Ошибка загрузки избранного')
    }
  }

  function setViewMode(mode) {
    viewMode.value = mode
    localStorage.setItem('kp_wl_view_mode', mode)
  }

  function setSortMode(mode) {
    sortMode.value = mode
    localStorage.setItem('kp_wl_sort_mode', mode)
  }

  async function createFolder(name, icon, color) {
    const trimmedName = name?.trim() || ''
    if (trimmedName.length > 100) {
      uiStore.showToast('Название папки не должно превышать 100 символов')
      return
    }
    try {
      const data = await api.post('wishlist/', { action: 'create_folder', name: trimmedName, icon, color })
      await fetchWishlist()
      if (data.id) activeFolderId.value = data.id
      uiStore.showToast('Папка создана')
    } catch (error) {
      uiStore.showToast(error.message || 'Ошибка создания папки')
    }
  }

  async function editFolder(folderId, name, icon, color) {
    const trimmedName = name?.trim() || ''
    if (trimmedName.length > 100) {
      uiStore.showToast('Название папки не должно превышать 100 символов')
      return
    }
    try {
      await api.post('wishlist/', { action: 'edit_folder', folder_id: folderId, name: trimmedName, icon, color })
      await fetchWishlist()
      uiStore.showToast('Папка изменена')
    } catch (error) {
      uiStore.showToast(error.message || 'Ошибка изменения папки')
    }
  }

  async function deleteFolder(folderId) {
    try {
      await api.post('wishlist/', { action: 'delete_folder', folder_id: folderId })
      if (activeFolderId.value === folderId) {
        activeFolderId.value = null
      }
      await fetchWishlist()
      uiStore.showToast('Папка удалена')
    } catch (e) {
      uiStore.showToast('Ошибка удаления папки')
    }
  }

  async function removeItem(itemId, keepStats) {
    try {
      await api.post('wishlist/', { action: 'remove_item', item_id: itemId, keep_stats: keepStats })
      await fetchWishlist()
      uiStore.showToast('Шоу удалено из папки')
    } catch (e) {
      uiStore.showToast('Ошибка удаления')
    }
  }

  async function addItemToFolder(folderId, showId) {
    try {
      await api.post('wishlist/', { action: 'add_item', folder_id: folderId, show_id: showId })
      await fetchWishlist()
      uiStore.showToast('Успешно добавлено')
    } catch (e) {
      uiStore.showToast('Ошибка при добавлении')
    }
  }

  async function reorderFolders(order) {
    const newFolders = []
    order.forEach(id => {
      const f = folders.value.find(x => x.id === id)
      if (f) newFolders.push(f)
    })
    folders.value = newFolders

    try {
      await api.post('wishlist/', { action: 'reorder_folders', order })
    } catch (e) {
      uiStore.showToast('Ошибка сохранения порядка')
    }
  }

  async function reorderItems(folderId, order) {
    const folder = folders.value.find(f => f.id === folderId)
    if (folder) {
      const newItems = []
      order.forEach(id => {
        const it = folder.items.find(x => x.id === id)
        if (it) newItems.push(it)
      })
      folder.items = newItems
    }

    try {
      await api.post('wishlist/', { action: 'reorder_items', folder_id: folderId, order })
    } catch (e) {
      uiStore.showToast('Ошибка сохранения порядка')
    }
  }

  return {
    folders,
    activeFolderId,
    activeFolder,
    sortedItems,
    viewMode,
    sortMode,
    isReorderFoldersMode,
    isReorderItemsMode,
    FOLDER_COLORS,
    FOLDER_ICONS,
    fetchWishlist,
    setViewMode,
    setSortMode,
    createFolder,
    editFolder,
    deleteFolder,
    removeItem,
    addItemToFolder,
    reorderFolders,
    reorderItems
  }
})