<template>
  <div class="bottom-nav" id="bottom-nav">
    <button class="bn-btn" :class="{ active: currentRoute === 'search' }" @click="navigate('search')">
      <div class="icon" v-html="icons.search"></div> Поиск
    </button>
    <button class="bn-btn" :class="{ active: currentRoute === 'wishlist' }" @click="navigate('wishlist')">
      <div class="icon" v-html="icons.bookmark"></div> Избранное
    </button>
    <button v-if="!userStore.isGuest" class="bn-btn" :class="{ active: currentRoute === 'stats' }" @click="navigate('stats')">
      <div class="icon" v-html="icons.nav_stats"></div> Статистика
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../../stores/userStore'
import { icons } from '../../utils/icons'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const currentRoute = computed(() => route.name)
const navigate = (name) => router.push({ name })
</script>