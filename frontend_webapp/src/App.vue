<template>
  <div id="app" :class="{ hidden: !uiStore.isAppReady }">
    <div id="views-container">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </div>
    
    <BottomNav />
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

const uiStore = useUIStore()
const userStore = useUserStore()
const { tg, initData } = useTelegram()

watch(() => uiStore.theme, (newTheme) => {
  document.body.classList.toggle('light', newTheme === 'light')
  document.body.classList.toggle('dark', newTheme === 'dark')
}, { immediate: true })

onMounted(() => {
  if (tg) {
    tg.expand()
    if (tg.initDataUnsafe?.user) {
      userStore.setUserData(tg.initDataUnsafe.user)
    }
    userStore.setInitData(initData)
    
    const isDark = tg.colorScheme !== 'light'
    uiStore.theme = isDark ? 'dark' : 'light'
  }

  document.body.classList.add('is-webapp', 'has-nav')

  setTimeout(() => {
    uiStore.setLoading(false)
    uiStore.setAppReady(true)
  }, 300)
})
</script>

<style>
@import '../../kinopub_parser/static/css/webapp.css';

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>