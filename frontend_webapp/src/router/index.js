import { createRouter, createWebHashHistory } from 'vue-router'
import SearchView from '../views/SearchView.vue'
import WishlistView from '../views/WishlistView.vue'
import StatsView from '../views/StatsView.vue'

const routes = [
  {
    path: '/search/:layers*',
    name: 'search',
    component: SearchView
  },
  {
    path: '/wishlist/:layers*',
    name: 'wishlist',
    component: WishlistView
  },
  {
    path: '/stats/:layers*',
    name: 'stats',
    component: StatsView
  },
  { path: '/', redirect: '/search' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router