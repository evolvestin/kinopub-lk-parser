import { createRouter, createWebHashHistory } from 'vue-router'
import SearchView from '../views/SearchView.vue'
import WishlistView from '../views/WishlistView.vue'
import StatsView from '../views/StatsView.vue'

const routes = [
  {
    path: '/search',
    name: 'search',
    component: SearchView,
    children: [{ path: ':layers(.*)*', name: 'search-stack' }]
  },
  {
    path: '/wishlist',
    name: 'wishlist',
    component: WishlistView,
    children: [{ path: ':layers(.*)*', name: 'wishlist-stack' }]
  },
  {
    path: '/stats',
    name: 'stats',
    component: StatsView,
    children: [{ path: ':layers(.*)*', name: 'stats-stack' }]
  },
  { path: '/', redirect: '/search' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router