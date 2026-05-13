import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUIStore = defineStore('ui', () => {
  const isLoading = ref(true)
  const isAppReady = ref(false)
  const theme = ref(localStorage.getItem('kt') === 'l' ? 'light' : 'dark')
  const toast = ref({ text: '', visible: false })

  // Стек слоев (Layers)
  const layerStack = ref([])
  
  // Состояния модалок
  const modals = ref({
    rating: { isOpen: false, showId: null, title: '', initialValue: 5, type: 'Movie' },
    casino: { isOpen: false },
    folderEdit: { isOpen: false, isEdit: false, folderId: null }
  })

  function openLayer(type, props = {}) {
    layerStack.value.push({ type, props })
    updateTelegramBackButton()
  }

  function popLayer() {
    if (layerStack.value.length > 0) {
      layerStack.value.pop()
      updateTelegramBackButton()
    }
  }

  function openRatingModal(showId, title, initialValue, type) {
    modals.value.rating = { isOpen: true, showId, title, initialValue, type }
  }

  function updateTelegramBackButton() {
    const tg = window.Telegram?.WebApp
    if (tg?.BackButton) {
      if (layerStack.value.length > 0) tg.BackButton.show()
      else tg.BackButton.hide()
    }
  }

  function showToast(text) {
    toast.value = { text, visible: true }
    setTimeout(() => { toast.value.visible = false }, 2500)
  }

  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
    localStorage.setItem('kt', theme.value === 'dark' ? 'd' : 'l')
  }

  return {
    isLoading, isAppReady, theme, toast, layerStack, modals,
    openLayer, popLayer, openRatingModal, showToast, toggleTheme,
    setLoading: (val) => { isLoading.value = val },
    setAppReady: (val) => { isAppReady.value = val }
  }
})