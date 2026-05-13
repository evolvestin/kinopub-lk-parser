<template>
  <div :class="[uiStore.theme, { 'is-webapp': true }]">
    <!-- Показываем контент только когда приложение готово -->
    <div v-if="uiStore.isAppReady" id="views-container" v-show="!uiStore.hasOpenLayers" class="app-viewport">
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </div>

    <div id="dynamic-layers" v-if="uiStore.hasOpenLayers">
      <div v-for="(layer, index) in uiStore.layerStack" 
           :key="index" 
           class="layer" 
           :style="{ zIndex: 1000 + index, display: index === uiStore.layerStack.length - 1 ? 'block' : 'none' }">
        <ShowDetailsLayer v-if="layer.type === 'show'" v-bind="layer.props" />
        <HistoryLayer v-if="layer.type === 'history'" v-bind="layer.props" />
      </div>
    </div>
    
    <BottomNav v-show="!uiStore.hasOpenLayers && uiStore.isAppReady" />
    <Loader />
    <Toast />
  </div>
</template>

<script setup>
import { onMounted, watch } from 'vue'
import { useUIStore } from './stores/uiStore'
import { useUserStore } from './stores/userStore'
import { useTelegram } from './composables/useTelegram'
import BottomNav from './components/layout/BottomNav.vue'
import Loader from './components/layout/Loader.vue'
import Toast from './components/layout/Toast.vue'
import ShowDetailsLayer from './components/layers/ShowDetailsLayer.vue'
import HistoryLayer from './components/layers/HistoryLayer.vue'

const uiStore = useUIStore()
const userStore = useUserStore()
const { tg } = useTelegram()

onMounted(async () => {
  if (tg) {
    tg.ready()
    tg.expand()
    userStore.setUser(tg.initDataUnsafe?.user)
    tg.BackButton.onClick(() => uiStore.popLayer())
  }
  // Даем приложению время на инициализацию роутера и сторов
  setTimeout(() => {
    uiStore.setLoading(false)
    uiStore.setAppReady(true)
  }, 100)
})

watch(() => uiStore.theme, (val) => {
  document.body.className = val === 'light' ? 'light' : ''
}, { immediate: true })
</script>