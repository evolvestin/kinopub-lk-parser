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
            type: type,
            ...(type === 'history' ? { routeQuery: { ...route.query } } : {})
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
  // Keep the intended path synchronously while a router navigation is in
  // flight. A modal can be interacted with before router.currentRoute has
  // caught up; using this snapshot prevents query-only updates from dropping
  // an open show/history layer.
  const stableRoutePath = ref(router.currentRoute.value.path || '/search')
  const stableRouteQuery = ref({ ...router.currentRoute.value.query })
  // Several UI actions can update the hash in the same event loop (for
  // example, the debounced search query and the click that opens a show).
  // Keep the newest intended location authoritative until that navigation is
  // committed, otherwise an older navigation can erase a just-opened layer.
  let pendingNavigation = null

  router.afterEach((to) => {
    activeView.value = viewNameFromPath(to.path)
    // Ignore an older navigation finishing after a newer UI intent. The
    // promise handler below will commit the stable snapshot for the newest
    // successful navigation.
    if (pendingNavigation && to.fullPath !== pendingNavigation.fullPath) return
    stableRoutePath.value = to.path
    stableRouteQuery.value = { ...to.query }
    if (pendingNavigation) pendingNavigation = null
  })

  function navigate(method, location) {
    const target = router.resolve(location)
    pendingNavigation = target
    return router[method](location).then(() => {
      if (pendingNavigation === target && router.currentRoute.value.fullPath === target.fullPath) {
        stableRoutePath.value = router.currentRoute.value.path
        stableRouteQuery.value = { ...router.currentRoute.value.query }
        pendingNavigation = null
      }
    }).catch((error) => {
      if (pendingNavigation === target) {
        pendingNavigation = null
        stableRoutePath.value = router.currentRoute.value.path
        stableRouteQuery.value = { ...router.currentRoute.value.query }
      }
      // A cancelled navigation is expected when two rapid UI actions happen;
      // callers should not get an unhandled promise rejection for it.
      return error
    })
  }

  function syncActiveView() {
    activeView.value = viewNameFromPath(router.currentRoute.value.path)
  }

  function openLayer(type, id, query = {}) {
    if (window.IS_ADMIN_DASHBOARD) return
    const currentPath = stableRoutePath.value || router.currentRoute.value.path
    const newPath = `${currentPath}/${type}/${id}`.replace(/\/+/g, '/')
    // Telegram/mobile touch handling can deliver both the native click and a
    // synthetic click. Do not push the same layer twice while the first
    // navigation is still settling.
    if (currentPath.endsWith(`/${type}/${id}`)) return
    stableRoutePath.value = newPath
    const nextQuery = { ...stableRouteQuery.value, ...query }
    stableRouteQuery.value = nextQuery
    navigate('push', { path: newPath, query: nextQuery })
  }

  function popLayer() {
    isHistoryEditMode.value = false
    if (window.history.state && window.history.state.back) {
      // Back/forward is an external history transition from the store's
      // perspective; let afterEach adopt the route selected by the browser.
      pendingNavigation = null
      router.back()
    } else {
      const currentPath = stableRoutePath.value || router.currentRoute.value.path
      const segments = currentPath.split('/')
      if (segments.length > 2) {
        const newPath = segments.slice(0, -2).join('/')
        stableRoutePath.value = newPath
        navigate('replace', { path: newPath, query: stableRouteQuery.value })
      } else {
        stableRoutePath.value = '/search'
        navigate('replace', { path: '/search', query: stableRouteQuery.value })
      }
    }
  }

  function switchBaseView(viewName) {
    if (window.IS_ADMIN_DASHBOARD) return
    isHistoryEditMode.value = false
    localStorage.setItem('kp_last_active_view', viewName)
    const query = { ...stableRouteQuery.value }

    // Base-tab navigation closes transient layers and edit modes, but keeps
    // user navigation state such as the search text, stats tab/year, and
    // wishlist folder/sort/view settings.
    delete query.modal
    Object.keys(query).forEach((key) => {
      if (key.startsWith('modal_')) delete query[key]
    })
    const transientQueryKeys = ['reorder_folders', 'reorder_items', 'show_id', 'title', 'date', 'idx', 'key', 'name']
    transientQueryKeys.forEach((key) => {
      delete query[key]
    })
    if (viewName !== 'stats') {
      delete query.shared_id
    }
    // Base navigation is a replacement of the current screen, not a nested
    // history entry. This also prevents a fast sequence of tab clicks from
    // leaving an obsolete kept-alive view visible while the hash catches up.
    activeView.value = viewNameFromPath(`/${viewName}`)
    stableRoutePath.value = `/${viewName}`
    navigate('replace', { name: viewName, query })
  }

  function replaceQuery(query) {
    const nextQuery = { ...stableRouteQuery.value }
    Object.entries(query || {}).forEach(([key, value]) => {
      // Query setters pass null/undefined for an intentional removal. Keep
      // the stable route snapshot for rapid navigation, but do not resurrect
      // a flag that the user just turned off.
      if (value === null || value === undefined) {
        delete nextQuery[key]
      } else {
        nextQuery[key] = value
      }
    })
    stableRouteQuery.value = nextQuery
    return navigate('replace', {
      path: stableRoutePath.value || router.currentRoute.value.path,
      query: nextQuery
    })
  }

  function updateModalQuery(params) {
    const nextQuery = { ...stableRouteQuery.value }
    Object.keys(params).forEach((key) => {
      const val = params[key]
      const queryKey = `modal_${key}`
      if (val === null || val === undefined || val === '') {
        delete nextQuery[queryKey]
      } else {
        nextQuery[queryKey] = String(val)
      }
    })
    stableRouteQuery.value = nextQuery
    return navigate('replace', {
      path: stableRoutePath.value || router.currentRoute.value.path,
      query: nextQuery
    })
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
    const currentQuery = { ...stableRouteQuery.value }
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
    // Modal state is UI state, not a navigable page. Replacing the query makes
    // rapid close/open sequences atomic and prevents a stale modal_level from
    // being restored by an asynchronous router.back().
    stableRouteQuery.value = currentQuery
    navigate('replace', {
      path: stableRoutePath.value || router.currentRoute.value.path,
      query: currentQuery
    })
  }

  function closeModal(key) {
    const currentQuery = { ...stableRouteQuery.value }
    if (currentQuery.modal === key) {
      delete currentQuery.modal
      Object.keys(currentQuery).forEach(k => {
        if (k.startsWith('modal_')) delete currentQuery[k]
      })
      stableRouteQuery.value = currentQuery
      navigate('replace', {
        path: stableRoutePath.value || router.currentRoute.value.path,
        query: currentQuery
      })
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
    openModal, closeModal, replaceQuery, updateModalQuery, dismissHint,
    setLoading: (v) => { isLoading.value = v },
    setAppReady: (v) => { isAppReady.value = v }
  }
})
