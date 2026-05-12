import { createRouter, createWebHashHistory } from 'vue-router'
import SearchView from '../views/SearchView.vue'
import WishlistView from '../views/WishlistView.vue'
import StatsView from '../views/StatsView.vue'

const routes = [
  { path: '/', redirect: '/search' },
  { path: '/search', name: 'search', component: SearchView },
  { path: '/wishlist', name: 'wishlist', component: WishlistView },
  { path: '/stats', name: 'stats', component: StatsView }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router