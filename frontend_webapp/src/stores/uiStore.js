import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import router from '../router'

export const useUIStore = defineStore('ui', () => {
  const isLoading = ref(false)
  const isAppReady = ref(false)
  const theme = ref(localStorage.getItem('kt') === 'l' ? 'light' : 'dark')
  const toast = ref({ text: '', visible: false })

  const modals = ref({
    share: { isOpen: false, context: null },
    casino: { isOpen: false, context: null },
    rateShow: { isOpen: false, context: null },
    addView: { isOpen: false, context: null },
    details: { isOpen: false, context: null }
  })

  const layerStack = computed(() => {
    const route = router.currentRoute.value
    const segments = route.path.split('/').filter(s => s && !['search', 'wishlist', 'stats'].includes(s))
    
    const stack = []
    for (let i = 0; i < segments.length; i += 2) {
      const type = segments[i]
      const id = segments[i + 1]
      if (type && id) {
        stack.push({
          type,
          props: { [`${type}Id`]: id, itemId: id, type: type },
          key: `${type}-${id}-${i}`
        })
      }
    }
    return stack
  })

  const hasOpenLayers = computed(() => layerStack.value.length > 0)
  
  const activeView = computed(() => {
    const path = router.currentRoute.value.path
    if (path.startsWith('/search')) return 'search'
    if (path.startsWith('/wishlist')) return 'wishlist'
    if (path.startsWith('/stats')) return 'stats'
    return 'search'
  })

  function openLayer(type, id) {
    const currentPath = router.currentRoute.value.path.replace(/\/$/, '')
    router.push(`${currentPath}/${type}/${id}`)
  }

  function popLayer() {
    router.back()
  }

  function switchBaseView(viewName) {
    router.push({ name: viewName })
  }

  function showToast(text) {
    toast.value = { text, visible: true }
    setTimeout(() => { toast.value.visible = false }, 2500)
  }

  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
    localStorage.setItem('kt', theme.value === 'dark' ? 'd' : 'l')
  }

  function openModal(key, context = null) {
    if (modals.value[key]) {
      modals.value[key].isOpen = true
      modals.value[key].context = context
    }
  }

  function closeModal(key) {
    if (modals.value[key]) {
      modals.value[key].isOpen = false
    }
  }

  return {
    isLoading, isAppReady, theme, toast, layerStack, hasOpenLayers, activeView, modals,
    openLayer, popLayer, switchBaseView, showToast, toggleTheme, openModal, closeModal,
    setLoading: (v) => { isLoading.value = v },
    setAppReady: (v) => { isAppReady.value = v }
  }
})