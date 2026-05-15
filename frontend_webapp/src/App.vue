<script setup>
import { onMounted, watch } from 'vue'
import { useUIStore } from './stores/uiStore'
import { useStatsStore } from './stores/useStatsStore'
import { useTelegram } from './composables/useTelegram'
import BottomNav from './components/layout/BottomNav.vue'
import Loader from './components/layout/Loader.vue'
import Toast from './components/layout/Toast.vue'

import ShowDetailsLayer from './components/layers/ShowDetailsLayer.vue'
import CollectionLayer from './components/layers/CollectionLayer.vue'
import HistoryLayer from './components/layers/HistoryLayer.vue'

const uiStore = useUIStore()
const statsStore = useStatsStore()
const { tg } = useTelegram()

onMounted(async () => {
  if (tg) {
    tg.ready()
    tg.expand()
    tg.BackButton.onClick(() => uiStore.popLayer())
  }
  
  // При старте загружаем базовые данные, чтобы получить роль пользователя
  // Это автоматически обновит BottomNav и покажет кнопку Статистики
  await statsStore.fetchStats('all', true)
  
  uiStore.setLoading(false)
  uiStore.setAppReady(true)
})

watch(() => uiStore.hasOpenLayers, (val) => {
  if (tg?.BackButton) val ? tg.BackButton.show() : tg.BackButton.hide()
}, { immediate: true })

watch(() => uiStore.theme, (val) => {
  document.body.className = val === 'light' ? 'light' : ''
}, { immediate: true })
</script>

<template>
  <div :class="[uiStore.theme, 'is-webapp']">
    <div v-show="uiStore.isAppReady" id="views-container" class="app-viewport">
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
  </div>
</template>