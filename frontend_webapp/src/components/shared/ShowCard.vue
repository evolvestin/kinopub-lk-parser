<template>
  <div class="grid-item-wrap anim-item" @click="openShow">
    <div class="grid-item">
      <img v-if="show.poster_url" :src="show.poster_url" class="grid-poster" loading="lazy">
      <div v-else class="grid-poster"></div>
      
      <div class="grid-badges">
        <span v-if="show.user_rating" class="rating-badge" style="background: rgba(0,0,0,0.6); border: none;">
          <span v-html="icons.star" style="margin-right: 2px;"></span>{{ show.user_rating }}
        </span>
      </div>
      
      <div v-if="show.year" class="grid-year">{{ show.year }}</div>
      
      <button class="wishlist-add-btn" @click.stop="addToWishlist">
        <span v-html="icons.bookmark_plus"></span>
      </button>
    </div>
    
    <div class="grid-below-title">{{ show.title }}</div>
  </div>
</template>

<script setup>
import { icons } from '../../utils/icons'

const props = defineProps({
  show: {
    type: Object,
    required: true
  }
})

const openShow = () => {
  console.log('Open show layer', props.show.id)
}

const addToWishlist = () => {
  console.log('Add to wishlist modal', props.show.id)
}
</script>