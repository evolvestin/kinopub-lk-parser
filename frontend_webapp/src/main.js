import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import AdminDashboard from './views/AdminDashboard.vue'
import AdminStatsDashboard from './views/AdminStatsDashboard.vue'
import AdminWishlistPreview from './views/AdminWishlistPreview.vue'
import router from './router'

import '../../kinopub_parser/static/css/webapp.css'

const pinia = createPinia()

if (document.getElementById('app')) {
  const app = createApp(App)
  app.use(pinia)
  app.use(router)
  app.mount('#app')
}

if (document.getElementById('admin-app')) {
  const adminApp = createApp(AdminDashboard)
  adminApp.use(pinia)
  adminApp.mount('#admin-app')
}

if (document.getElementById('admin-stats-app')) {
  const adminStatsApp = createApp(AdminStatsDashboard)
  adminStatsApp.use(pinia)
  adminStatsApp.use(router)
  adminStatsApp.mount('#admin-stats-app')
}

if (document.getElementById('admin-wishlist-preview')) {
  const wishlistPreview = createApp(AdminWishlistPreview)
  wishlistPreview.use(pinia)
  wishlistPreview.mount('#admin-wishlist-preview')
}

let touchStartX = 0
let touchStartY = 0
let touchStartTime = 0
let touchTarget = null

const clickableSelector = '.clickable, .li-clickable, .grid-item-wrap, .hist-item, .person-pill, .genre-pill, .tab, .yr, .btn-primary, .theme-btn, .share-btn, .wl-edit-btn, .vt-btn, .bn-btn, .legend-item, .chart-box canvas, .bar-item-wrap'
document.addEventListener('touchstart', (e) => {
  const target = e.target.closest(clickableSelector)
  if (!target) return

  const touch = e.touches[0]
  touchStartX = touch.clientX
  touchStartY = touch.clientY
  touchStartTime = Date.now()
  touchTarget = target
}, { passive: true })

document.addEventListener('touchend', (e) => {
  if (!touchTarget) return

  const touch = e.changedTouches[0]
  const distX = Math.abs(touch.clientX - touchStartX)
  const distY = Math.abs(touch.clientY - touchStartY)
  const duration = Date.now() - touchStartTime

  if (distX < 10 && distY < 10 && duration >= 300) {
    const clickEvent = new MouseEvent('click', {
      bubbles: true,
      cancelable: true,
      view: window,
      clientX: touch.clientX,
      clientY: touch.clientY,
      screenX: touch.screenX,
      screenY: touch.screenY
    })
    touchTarget.dispatchEvent(clickEvent)
  }
  touchTarget = null
}, { passive: true })

document.addEventListener('contextmenu', (e) => {
  if (e.target.closest(clickableSelector)) {
    e.preventDefault()
  }
})

document.addEventListener('wheel', (e) => {
  const container = e.target.closest('.h-scroll-container')
  if (container && e.deltaY !== 0) {
    e.preventDefault()
    container.scrollLeft += e.deltaY
  }
}, { passive: false })