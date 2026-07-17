<template>
  <div class="bottom-nav" id="bottom-nav">
    <button class="bn-btn" :class="{ active: uiStore.activeView === 'search' }" @click="uiStore.switchBaseView('search')">
      <div class="icon" v-html="icons.search"></div> Поиск
    </button>
    <button class="bn-btn" :class="{ active: uiStore.activeView === 'wishlist' }" @click="uiStore.switchBaseView('wishlist')">
      <div class="icon" v-html="icons.bookmark"></div> Избранное
    </button>
    <button class="bn-btn" :class="{ active: uiStore.activeView === 'stats' }" @click="uiStore.switchBaseView('stats')">
      <div class="icon" v-html="icons.nav_stats"></div> Статистика
    </button>
  </div>
</template>

<script setup>
import { useUIStore } from '../../stores/uiStore'
import { useUserStore } from '../../stores/userStore'
import { icons } from '../../utils/icons'

const uiStore = useUIStore()
const userStore = useUserStore()
</script>