<script setup>
import { onMounted, watch, computed } from 'vue'
import { useUIStore } from './stores/uiStore'
import { useStatsStore } from './stores/useStatsStore'
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

const uiStore = useUIStore()
const statsStore = useStatsStore()
const { tg } = useTelegram()

const showBackButton = computed(() => {
  return uiStore.hasOpenLayers || Object.values(uiStore.modals).some(m => m.isOpen)
})

onMounted(async () => {
  if (window.IS_DEBUG || window.USER_ROLE === 'admin') {
    const navigationStart = window.performance?.timing?.navigationStart || window.performance?.timeOrigin;
    if (navigationStart) {
      const latency = Date.now() - navigationStart;
      logger.info(`Bootstrap Latency from Click to App: ${latency.toFixed(2)}ms`);
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
  
  try {
    await statsStore.fetchStats('all', false)
  } catch (e) {
    logger.error('Failed to fetch initial stats during bootstrap:', e)
  } finally {
    uiStore.setLoading(false)
    uiStore.setAppReady(true)
    logger.timeEnd('InitialBootstrap')
  }
})

watch(showBackButton, (val) => {
  if (tg?.BackButton) val ? tg.BackButton.show() : tg.BackButton.hide()
}, { immediate: true })

watch(() => uiStore.theme, (val) => {
  document.body.className = val === 'light' ? 'light' : ''
}, { immediate: true })
</script>

<template>
  <div :class="[uiStore.theme, 'is-webapp']">
    <div v-show="uiStore.isAppReady && !uiStore.hasOpenLayers" id="views-container" class="app-viewport">
      <router-view v-slot="{ Component }">
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
        <CollectionLayer v-if="['person', 'genre', 'country'].includes(layer.type)" 
                        :type="layer.type" :itemId="layer.props.itemId" />
        <HistoryLayer v-if="layer.type === 'history'" v-bind="layer.props" />
      </div>
    </div>
    
    <BottomNav v-show="!uiStore.hasOpenLayers && uiStore.isAppReady" />
    <Loader />
    <Toast />

    <Transition name="modal">
      <ShareModal v-if="uiStore.modals.share.isOpen" />
    </Transition>
    <Transition name="modal">
      <CasinoModal v-if="uiStore.modals.casino.isOpen" />
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
      <WlEditModal v-if="uiStore.modals.wlEdit.isOpen" />
    </Transition>
    <Transition name="modal">
      <WlLimitModal v-if="uiStore.modals.wlLimit.isOpen" />
    </Transition>
    <Transition name="modal">
      <WlDeleteModal v-if="uiStore.modals.wlDelete.isOpen" />
    </Transition>
  </div>
</template>