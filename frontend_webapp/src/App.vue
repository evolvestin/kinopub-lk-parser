<script setup>
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useUIStore } from './stores/uiStore'
import { useStatsStore } from './stores/useStatsStore'
import { useWishlistStore } from './stores/wishlistStore'
import { useTelegram } from './composables/useTelegram'
import { logger } from './utils/logger'
import BottomNav from './components/layout/BottomNav.vue'
import Loader from './components/layout/Loader.vue'
import Toast from './components/layout/Toast.vue'

import ShowDetailsLayer from './components/layers/ShowDetailsLayer.vue'
import CollectionLayer from './components/layers/CollectionLayer.vue'
import HistoryLayer from './components/layers/HistoryLayer.vue'

import ShareModal from './components/modals/ShareModal.vue'
import CasinoModal from './components/modals/CasinoModal.vue'
import RatingModal from './components/modals/RatingModal.vue'
import AddViewModal from './components/modals/AddViewModal.vue'
import WlFolderModal from './components/modals/WlFolderModal.vue'
import WlEditModal from './components/modals/WlEditModal.vue'
import WlLimitModal from './components/modals/WlLimitModal.vue'
import WlDeleteModal from './components/modals/WlDeleteModal.vue'
import RatingsDetailsModal from './components/modals/RatingsDetailsModal.vue'
import UnsubscribeLayer from './components/layers/UnsubscribeLayer.vue'
import PrivacyModal from './components/modals/PrivacyModal.vue'

const uiStore = useUIStore()
const statsStore = useStatsStore()
const wishlistStore = useWishlistStore()
const { tg, showConfirm } = useTelegram()
const router = useRouter()

const bannerRef = ref(null)
let bannerObserver = null

const updateBannerHeight = () => {
  if (bannerRef.value) {
    document.documentElement.style.setProperty('--banner-height', `${bannerRef.value.offsetHeight}px`)
  } else {
    document.documentElement.style.setProperty('--banner-height', '0px')
  }
}

const showBackButton = computed(() => {
  return uiStore.hasOpenLayers || Object.values(uiStore.modals).some(m => m.isOpen)
})

const sharedUser = computed(() => {
  return statsStore.currentStats?.meta || null
})

const openTelegramLink = (url) => {
  showConfirm('Переход в профиль Telegram может свернуть текущее мини-приложение. Продолжить?', (ok) => {
    if (ok) {
      if (tg && typeof tg.openTelegramLink === 'function') {
        tg.openTelegramLink(url)
      } else {
        window.open(url, '_blank')
      }
    }
  })
}

watch(() => statsStore.isShared, (val) => {
  if (val) {
    document.body.classList.add('has-banner')
    nextTick(() => {
      if (bannerRef.value) {
        updateBannerHeight()
        if (typeof ResizeObserver !== 'undefined') {
          bannerObserver = new ResizeObserver(() => {
            updateBannerHeight()
          })
          bannerObserver.observe(bannerRef.value)
        }
      }
    })
  } else {
    document.body.classList.remove('has-banner')
    document.documentElement.style.setProperty('--banner-height', '0px')
    if (bannerObserver) {
      bannerObserver.disconnect()
      bannerObserver = null
    }
  }
}, { immediate: true })

onMounted(async () => {
  document.documentElement.classList.add('is-webapp')
  document.body.classList.add('is-webapp')

  if (window.USER_ROLE === 'admin') {
    const navigationStart = window.performance?.timing?.navigationStart || window.performance?.timeOrigin;
    if (navigationStart) {
      const latency = Date.now() - navigationStart;
      console.info(`[AppInfo] [${new Date().toISOString()}] Bootstrap Latency from Click to App: ${latency.toFixed(2)}ms`);
    }
  }

  logger.time('InitialBootstrap')
  logger.info('App.vue onMounted hook triggered')

  if (tg) {
    tg.ready()
    tg.expand()
    tg.BackButton.onClick(() => {
      const openModalKey = Object.keys(uiStore.modals).find(key => uiStore.modals[key].isOpen)
      if (openModalKey) {
        uiStore.closeModal(openModalKey)
      } else {
        uiStore.popLayer()
      }
    })
  }

  await router.isReady()

  let startParam = tg?.initDataUnsafe?.start_param || ''
  if (!startParam) {
    const params = new URLSearchParams(window.location.search)
    startParam = params.get('tgWebAppStartParam') || params.get('start_param') || ''
  }
  
  const lastView = localStorage.getItem('kp_last_active_view')
  const currentPath = router.currentRoute.value.path

  let targetPath = '/search'
  if (currentPath && currentPath !== '/') {
    targetPath = currentPath
  } else if (lastView && ['search', 'wishlist', 'stats'].includes(lastView)) {
    targetPath = `/${lastView}`
  }

  let targetQuery = { ...router.currentRoute.value.query }

  if (!targetQuery.shared_id) {
    const params = new URLSearchParams(window.location.search)
    const sId = params.get('shared_id')
    if (sId) {
      targetQuery.shared_id = sId
    }
  }

  if (targetQuery.shared_id) {
    targetPath = '/stats'
  }

  const processedStartParam = sessionStorage.getItem('processed_start_param')

  if (startParam && startParam !== processedStartParam) {
    sessionStorage.setItem('processed_start_param', startParam)

    if (startParam.startsWith('stat_')) {
      targetPath = '/stats'
      targetQuery.shared_id = startParam.replace('stat_', '')
    } else if (startParam.startsWith('show_')) {
      targetPath = '/search'
      nextTick(() => {
        uiStore.openLayer('show', startParam.replace('show_', ''))
      })
    } else if (startParam.startsWith('unsub_')) {
      const showId = startParam.replace('unsub_', '')
      targetPath = `/search/show/${showId}/unsubscribe/${showId}`
    }
  }

  await router.replace({ path: targetPath, query: targetQuery })

  try {
    await Promise.allSettled([
      statsStore.fetchStats(statsStore.currentYear, false),
      wishlistStore.fetchWishlist()
    ])
  } catch (e) {
    logger.error('Failed to fetch initial data during bootstrap:', e)
  } finally {
    uiStore.setLoading(false)
    uiStore.setAppReady(true)
    logger.timeEnd('InitialBootstrap')
  }
})

onUnmounted(() => {
  document.documentElement.classList.remove('is-webapp')
  document.body.classList.remove('is-webapp')
  if (bannerObserver) {
    bannerObserver.disconnect()
  }
})

watch(showBackButton, (val) => {
  if (tg?.BackButton) val ? tg.BackButton.show() : tg.BackButton.hide()
}, { immediate: true })

watch(() => uiStore.theme, (val) => {
  document.body.classList.toggle('light', val === 'light')
}, { immediate: true })
</script>

<template>
  <div :class="[uiStore.theme, 'is-webapp']">
    <div v-if="statsStore.isShared" ref="bannerRef" class="shared-banner">
      <span class="shared-banner-icon">📊</span>
      <span class="shared-banner-text">
        Вы просматриваете статистику
        <template v-if="sharedUser">
          <template v-if="!sharedUser.is_anonymous && sharedUser.name !== 'Аноним'">
            пользователя <strong class="shared-banner-name">{{ sharedUser.name }}</strong>
            <template v-if="sharedUser.username">
              (<a href="#" @click.prevent="openTelegramLink('https://t.me/' + sharedUser.username)" class="shared-banner-link">@{{ sharedUser.username }}</a>)
            </template>
          </template>
          <template v-else>
            анонимного пользователя
          </template>
        </template>
        <template v-else>
          другого пользователя
        </template>
      </span>
    </div>
    <div v-show="uiStore.isAppReady && !uiStore.hasOpenLayers" id="views-container" class="app-viewport">
      <router-view v-if="uiStore.isAppReady" v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" :key="uiStore.activeView" />
        </keep-alive>
      </router-view>
    </div>

    <div id="dynamic-layers">
      <div v-for="(layer, index) in uiStore.layerStack" 
           :key="layer.key" 
           class="layer" 
           :style="{ 
             zIndex: 1000 + index, 
             display: index === uiStore.layerStack.length - 1 ? 'block' : 'none' 
           }">
        <ShowDetailsLayer v-if="layer.type === 'show'" :showId="layer.props.showId" />
        <CollectionLayer v-if="['person', 'genre', 'country', 'show_type', 'year', 'status'].includes(layer.type)" 
                        :type="layer.type" :itemId="layer.props.itemId" />
        <HistoryLayer v-if="layer.type === 'history'" v-bind="layer.props" />
        <UnsubscribeLayer v-if="layer.type === 'unsubscribe'" :showId="layer.props.itemId" />
      </div>
    </div>
    
    <BottomNav v-show="!uiStore.hasOpenLayers && uiStore.isAppReady && !statsStore.isShared" />
    <Loader />
    <Toast />

    <Transition name="modal">
      <ShareModal v-if="uiStore.modals.share.isOpen" />
    </Transition>
    <Transition name="modal">
      <CasinoModal v-if="uiStore.modals.casino.isOpen && !uiStore.isCasinoHistoryOpen" />
    </Transition>
    <Transition name="modal">
      <RatingModal v-if="uiStore.modals.rateShow.isOpen" v-bind="uiStore.modals.rateShow.context" @close="uiStore.closeModal('rateShow')" />
    </Transition>
    <Transition name="modal">
      <AddViewModal v-if="uiStore.modals.addView.isOpen" v-bind="uiStore.modals.addView.context" />
    </Transition>
    <Transition name="modal">
      <WlFolderModal v-if="uiStore.modals.wlFolder.isOpen" />
    </Transition>
    <Transition name="modal">
      <WlFolderModal v-if="uiStore.modals.wlFolder.isOpen" />
    </Transition>
    <Transition name="modal">
      <WlEditModal v-if="uiStore.modals.wlEdit.isOpen" />
    </Transition>
    <Transition name="modal">
      <WlLimitModal v-if="uiStore.modals.wlLimit.isOpen" />
    </Transition>
    <Transition name="modal">
      <WlDeleteModal v-if="uiStore.modals.wlDelete.isOpen" />
    </Transition>
    <Transition name="modal">
      <RatingsDetailsModal v-if="uiStore.modals.details.isOpen" />
    </Transition>
    <Transition name="modal">
      <PrivacyModal v-if="uiStore.modals.privacy.isOpen" />
    </Transition>
  </div>
</template>