<template>
  <div class="grid-item-wrap anim-item" @click="uiStore.openLayer('show', { showId: show.id })">
    <div class="grid-item">
      <img :src="show.poster_url" class="grid-poster" loading="lazy">
      <div class="grid-badges">
        <span v-if="show.user_rating" class="rating-badge" style="background: rgba(0,0,0,0.6);">
          <span v-html="icons.star"></span>{{ show.user_rating }}
        </span>
      </div>
      <div v-if="show.year" class="grid-year">{{ show.year }}</div>
    </div>
    <div class="grid-below-title">{{ show.title }}</div>
  </div>
</template>

<script setup>
import { useUIStore } from '../../stores/uiStore'
import { icons } from '../../utils/icons'
const props = defineProps(['show'])
const uiStore = useUIStore()
</script>