<template>
  <div :class="{ hidden: !uiStore.isAppReady }">
    <div id="views-container">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </div>

    <!-- Слой Оверлеев (Layers) -->
    <div id="dynamic-layers">
      <transition-group name="layer">
        <div v-for="(layer, index) in uiStore.layerStack" 
             :key="index" 
             class="layer" 
             :style="{ zIndex: 1000 + index }">
          
          <ShowDetailsLayer v-if="layer.type === 'show'" v-bind="layer.props" />
          <HistoryLayer v-if="layer.type === 'history'" v-bind="layer.props" />
        </div>
      </transition-group>
    </div>
    
    <!-- Глобальные модалки -->
    <RatingModal v-if="uiStore.modals.rating.isOpen" 
                 v-bind="uiStore.modals.rating" 
                 @close="uiStore.modals.rating.isOpen = false" />
                 
    <CasinoModal v-if="uiStore.modals.casino.isOpen" />

    <BottomNav v-show="uiStore.layerStack.length === 0" />
    <Loader />
    <Toast />
  </div>
</template>

<script setup>
import { onMounted, watch } from 'vue'
import { useUIStore } from './stores/uiStore'
import ShowDetailsLayer from './components/layers/ShowDetailsLayer.vue'
import HistoryLayer from './components/layers/HistoryLayer.vue'
import RatingModal from './components/modals/RatingModal.vue'
import CasinoModal from './components/modals/CasinoModal.vue'
import { useUserStore } from './stores/userStore'
import { useTelegram } from './composables/useTelegram'
import BottomNav from './components/layout/BottomNav.vue'
import Loader from './components/layout/Loader.vue'
import Toast from './components/layout/Toast.vue'

const uiStore = useUIStore()
const userStore = useUserStore()
const { tg, initData } = useTelegram()

watch(() => uiStore.theme, (newTheme) => {
  document.body.classList.toggle('light', newTheme === 'light')
  document.body.classList.toggle('dark', newTheme === 'dark')
}, { immediate: true })

onMounted(() => {
  if (window.Telegram?.WebApp) {
    window.Telegram.WebApp.ready()
    window.Telegram.WebApp.expand()
    window.Telegram.WebApp.BackButton.onClick(() => {
      uiStore.popLayer()
    })
  }

  uiStore.setAppReady(true)
  uiStore.setLoading(false)
})
</script>

<style>
.layer-enter-active, .layer-leave-active {
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.3s ease;
}
.layer-enter-from { transform: translateX(100%); opacity: 0; }
.layer-leave-to { transform: translateX(100%); opacity: 0; }
</style>