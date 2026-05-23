import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import router from '../router'

export const useUIStore = defineStore('ui', () => {
  const isLoading = ref(false)
  const isAppReady = ref(false)
  const theme = ref(localStorage.getItem('kt') === 'l' ? 'light' : 'dark')
  const toast = ref({ text: '', visible: false })
  const isHistoryEditMode = ref(false)

  const modals = ref({
    share: { isOpen: false, context: null },
    casino: { isOpen: false, context: null },
    rateShow: { isOpen: false, context: null },
    addView: { isOpen: false, context: null },
    details: { isOpen: false, context: null },
    wlFolder: { isOpen: false, context: null },
    wlEdit: { isOpen: false, context: null },
    wlLimit: { isOpen: false, context: null },
    wlDelete: { isOpen: false, context: null }
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
          props: { 
            [`${type}Id`]: id,
            itemId: id,
            type: type 
          },
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

  function openLayer(type, id, query = {}) {
    const currentPath = router.currentRoute.value.path
    const newPath = `${currentPath}/${type}/${id}`.replace(/\/+/g, '/')
    router.push({ path: newPath, query })
  }

  function popLayer() {
    isHistoryEditMode.value = false
    router.back()
  }

  function switchBaseView(viewName) {
    isHistoryEditMode.value = false
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

  function fitText(el) {
    if (!el) return
    
    el.style.fontSize = ""
    
    if (el.offsetWidth === 0 && el.offsetHeight === 0) return

    const styles = window.getComputedStyle(el)
    const limitWidth = el.clientWidth
    if (limitWidth <= 0) return

    let limitHeight = parseFloat(styles.maxHeight)
    if (isNaN(limitHeight) || !styles.maxHeight.includes('px')) {
      limitHeight = el.offsetHeight || 40
    }
    
    const isSingleLine = styles.whiteSpace === 'nowrap' || styles.webkitLineClamp === '1'
    let size = parseFloat(styles.fontSize)
    const minSize = 9
    
    if (isSingleLine) {
      while (el.scrollWidth > limitWidth + 1 && size > minSize) {
        size -= 0.5
        el.style.fontSize = size + "px"
      }
    } else {
      const originalClamp = el.style.webkitLineClamp
      const originalMaxH = el.style.maxHeight
      
      el.style.webkitLineClamp = "none"
      el.style.maxHeight = "none"
      
      while (el.scrollHeight > limitHeight + 1 && size > minSize) {
        size -= 0.5
        el.style.fontSize = size + "px"
      }
      
      el.style.webkitLineClamp = originalClamp
      el.style.maxHeight = originalMaxH
    }
  }

  function fitAll(selector, container = document) {
    const elements = container.querySelectorAll(selector)
    elements.forEach(el => fitText(el))
  }

  return {
    isLoading, isAppReady, theme, toast, layerStack, hasOpenLayers, activeView, modals,
    isHistoryEditMode,
    openLayer, popLayer, switchBaseView, showToast, toggleTheme, fitText, fitAll,
    setLoading: (v) => { isLoading.value = v },
    setAppReady: (v) => { isAppReady.value = v },
    openModal: (key, context = null) => { if (modals.value[key]) { modals.value[key].isOpen = true; modals.value[key].context = context; } },
    closeModal: (key) => { if (modals.value[key]) modals.value[key].isOpen = false; }
  }
})