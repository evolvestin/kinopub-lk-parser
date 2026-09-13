import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import router from '../router'

export const useUIStore = defineStore('ui', () => {
  const isLoading = ref(false)
  const isAppReady = ref(false)
  const theme = ref(localStorage.getItem('kt') === 'l' ? 'light' : 'dark')
  const toast = ref({ text: '', visible: false })
  const isHistoryEditMode = ref(false)
  const episodesCache = ref({})
  const showsCache = ref({})
  const dismissedHints = ref(JSON.parse(localStorage.getItem('kp_hints') || '{}'))

  function dismissHint(key) {
    dismissedHints.value[key] = key === 'casino_modal' ? Date.now() : true
    localStorage.setItem('kp_hints', JSON.stringify(dismissedHints.value))
  }

  const modals = computed(() => {
    const active = router.currentRoute.value.query.modal || null
    const query = router.currentRoute.value.query
    const ctx = {}
    Object.keys(query).forEach(key => {
      if (key.startsWith('modal_')) {
        const cleanKey = key.replace('modal_', '')
        let val = query[key]
        if (val === 'true') val = true
        else if (val === 'false') val = false
        else if (/^\d+$/.test(val)) val = parseInt(val)
        ctx[cleanKey] = val
      }
    })

    const result = {}
    const keys = ['share', 'casino', 'rateShow', 'addView', 'details', 'wlFolder', 'wlEdit', 'wlLimit', 'wlDelete', 'privacy']
    keys.forEach(k => {
      result[k] = {
        isOpen: active === k,
        context: active === k ? ctx : {}
      }
    })
    return result
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

  const isCasinoHistoryOpen = computed(() => {
    return layerStack.value.some(layer => layer.type === 'history' && layer.props.historyId === 'casino')
  })

  const hasOpenLayers = computed(() => layerStack.value.length > 0)
  
  const viewNameFromPath = (path) => {
    if (path.startsWith('/search')) return 'search'
    if (path.startsWith('/wishlist')) return 'wishlist'
    if (path.startsWith('/stats')) return 'stats'
    return 'search'
  }

  // Keep the shell's visible base screen as an explicit reactive value. The
  // hash URL remains the source of navigation/deep-links, but rendering the
  // whole screen directly from router-view can lag behind during a rapid tab
  // switch while a lazy chunk is resolving.
  const activeView = ref(viewNameFromPath(router.currentRoute.value.path))
  router.afterEach((to) => {
    activeView.value = viewNameFromPath(to.path)
  })

  function syncActiveView() {
    activeView.value = viewNameFromPath(router.currentRoute.value.path)
  }

  function openLayer(type, id, query = {}) {
    if (window.IS_ADMIN_DASHBOARD) return
    const currentPath = router.currentRoute.value.path
    const newPath = `${currentPath}/${type}/${id}`.replace(/\/+/g, '/')
    router.push({ path: newPath, query: { ...router.currentRoute.value.query, ...query } })
  }

  function popLayer() {
    isHistoryEditMode.value = false
    if (window.history.state && window.history.state.back) {
      router.back()
    } else {
      const currentPath = router.currentRoute.value.path
      const segments = currentPath.split('/')
      if (segments.length > 2) {
        const newPath = segments.slice(0, -2).join('/')
        router.replace({ path: newPath, query: router.currentRoute.value.query })
      } else {
        router.replace({ path: '/search', query: router.currentRoute.value.query })
      }
    }
  }

  function switchBaseView(viewName) {
    if (window.IS_ADMIN_DASHBOARD) return
    isHistoryEditMode.value = false
    localStorage.setItem('kp_last_active_view', viewName)
    const query = { ...router.currentRoute.value.query }
    if (viewName !== 'stats') {
      delete query.shared_id
      delete query.tab
    }
    if (viewName !== 'search') {
      delete query.q
    }
    // Base navigation is a replacement of the current screen, not a nested
    // history entry. This also prevents a fast sequence of tab clicks from
    // leaving an obsolete kept-alive view visible while the hash catches up.
    activeView.value = viewNameFromPath(`/${viewName}`)
    router.replace({ name: viewName, query })
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
    const currentQuery = { ...router.currentRoute.value.query }
    Object.keys(currentQuery).forEach(k => {
      if (k.startsWith('modal_')) delete currentQuery[k]
    })
    currentQuery.modal = key
    if (context) {
      Object.keys(context).forEach(ck => {
        if (context[ck] !== null && context[ck] !== undefined) {
          currentQuery[`modal_${ck}`] = String(context[ck])
        }
      })
    }
    router.push({ query: currentQuery })
  }

  function closeModal(key) {
    const currentQuery = { ...router.currentRoute.value.query }
    if (currentQuery.modal === key) {
      if (window.history.state && window.history.state.back) {
        router.back()
      } else {
        delete currentQuery.modal
        Object.keys(currentQuery).forEach(k => {
          if (k.startsWith('modal_')) delete currentQuery[k]
        })
        router.replace({ query: currentQuery })
      }
    }
  }

  function fitText(el) {
    if (!el) return
    
    el.style.fontSize = ""
    
    if (el.offsetWidth === 0 && el.offsetHeight === 0) return

    const styles = window.getComputedStyle(el)
    const limitWidth = el.clientWidth
    if (limitWidth <= 0) return

    const initialFontSize = parseFloat(styles.fontSize) || 16
    const initialMaxHeight = parseFloat(styles.maxHeight)
    const hasMaxHeight = !isNaN(initialMaxHeight) && styles.maxHeight.includes('px')
    const emRatio = hasMaxHeight ? (initialMaxHeight / initialFontSize) : null

    let limitHeight = hasMaxHeight ? initialMaxHeight : (el.offsetHeight || 40)
    let size = initialFontSize
    const minSize = 9

    const isSingleLine = styles.whiteSpace === 'nowrap' || styles.webkitLineClamp === '1'
    const originalMaxHeight = el.style.maxHeight
    const originalClamp = el.style.webkitLineClamp
    
    if (isSingleLine) {
      while (el.scrollWidth > limitWidth + 1 && size > minSize) {
        size -= 0.5
        el.style.fontSize = size + "px"
      }
    } else {
      el.style.webkitLineClamp = "none"
      el.style.maxHeight = "none"
      
      while (size > minSize) {
        const currentLimitHeight = emRatio ? (size * emRatio) : limitHeight
        if (el.scrollHeight <= currentLimitHeight + 1) {
          break
        }
        size -= 0.5
        el.style.fontSize = size + "px"
      }
      
      el.style.webkitLineClamp = originalClamp
      el.style.maxHeight = originalMaxHeight
    }
  }

  function fitAll(selector, container = document) {
    const elements = container.querySelectorAll(selector)
    elements.forEach(el => fitText(el))
  }

  return {
    isLoading, isAppReady, theme, toast, layerStack, hasOpenLayers, activeView, modals,
    isHistoryEditMode, episodesCache, showsCache, dismissedHints, isCasinoHistoryOpen,
    openLayer, popLayer, switchBaseView, syncActiveView, showToast, toggleTheme, fitText, fitAll,
    openModal, closeModal, dismissHint,
    setLoading: (v) => { isLoading.value = v },
    setAppReady: (v) => { isAppReady.value = v }
  }
})
