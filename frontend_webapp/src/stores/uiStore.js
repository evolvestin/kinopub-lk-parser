import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUIStore = defineStore('ui', () => {
  const isLoading = ref(true)
  const isAppReady = ref(false)
  const theme = ref(localStorage.getItem('kt') === 'l' ? 'light' : 'dark')
  const toast = ref({ text: '', visible: false })
  const layerStack = ref([])
  
  // Состояния модалок
  const modals = ref({
    share: { isOpen: false }
  })

  const hasOpenLayers = computed(() => layerStack.value.length > 0)

  function openLayer(type, props = {}) {
    layerStack.value.push({ type, props })
    const tg = window.Telegram?.WebApp
    if (tg?.BackButton) tg.BackButton.show()
  }

  function popLayer() {
    if (layerStack.value.length > 0) layerStack.value.pop()
    const tg = window.Telegram?.WebApp
    if (layerStack.value.length === 0 && tg?.BackButton) tg.BackButton.hide()
  }

  function showToast(text) {
    toast.value = { text, visible: true }
    setTimeout(() => { toast.value.visible = false }, 2500)
  }

  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
    localStorage.setItem('kt', theme.value === 'dark' ? 'd' : 'l')
  }

  function openModal(name) {
    if (modals.value[name]) modals.value[name].isOpen = true
  }

  return {
    isLoading, isAppReady, theme, toast, layerStack, hasOpenLayers, modals,
    openLayer, popLayer, showToast, toggleTheme, openModal,
    setLoading: (val) => { isLoading.value = val },
    setAppReady: (val) => { isAppReady.value = val }
  }
})