import { createRouter, createWebHashHistory } from 'vue-router'
const routes = [
  {
    path: '/search/:layers*',
    name: 'search',
    component: () => import('../views/SearchView.vue')
  },
  {
    path: '/wishlist/:layers*',
    name: 'wishlist',
    component: () => import('../views/WishlistView.vue')
  },
  {
    path: '/stats/:layers*',
    name: 'stats',
    component: () => import('../views/StatsView.vue')
  },
  { path: '/', redirect: '/search' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
