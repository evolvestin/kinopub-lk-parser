<template>
  <div 
    v-if="viewMode === 'grid'" 
    v-memo="[show.id || show.show_id, isHistory, isWiggling, showDeleteBadge, isAnimated]"
    class="grid-item-wrap" 
    :class="{ 'anim-item': isAnimated, 'history-mode': isHistory, 'wiggle': isWiggling }"
    :data-id="show.id || show.show_id"
    @click="handleClick"
    @animationend="handleAnimationEnd"
  >
    <div v-if="showDeleteBadge" class="wl-delete-badge" @click.stop="onDelete">
      <span v-html="icons.minus"></span>
    </div>

    <div class="grid-item">
      <div v-if="isBroken" class="grid-poster is-placeholder" v-html="icons.person_placeholder"></div>
      <img v-else :src="currentPosterUrl" class="grid-poster" loading="lazy" decoding="async" @load="validateImage" @error="handleError">
      
      <div class="grid-badges">
        <span v-if="season > 0" class="hist-badge">
          s{{ season }}e{{ String(episode).padStart(2, '0') }}
        </span>
        <span v-if="rating" class="rating-badge" :class="getRatingClass(rating)">
          <span v-html="icons.star"></span>{{ rating }}
        </span>
      </div>
      <div v-if="itemYear" class="grid-year">{{ itemYear }}</div>
      <div v-if="isHistory" class="grid-overlay">
        <div v-if="show.user_names?.length > 0" class="grid-users">
          <template v-for="(name, idx) in show.user_names" :key="idx">
            <img v-if="show.user_photos?.[idx]" :src="show.user_photos[idx]" class="grid-user-avatar">
            <div v-else class="grid-user-avatar" :style="{ background: getUserColor(show.user_ids?.[idx] || 0) }">
              {{ name.charAt(0).toUpperCase() }}
            </div>
          </template>
        </div>
        <div class="grid-date">{{ displayDate }}</div>
      </div>
      <button v-if="!isHistory" class="wishlist-add-btn" @click.stop="addToWishlist">
        <span v-html="icons.bookmark_plus"></span>
      </button>
    </div>
    <div class="grid-below-title">{{ show.show__title || show.title }}</div>
  </div>

  <div 
    v-else 
    v-memo="[show.id || show.show_id, isHistory, isWiggling, showDeleteBadge, isAnimated]" 
    class="hist-item clickable" 
    :class="{ 'anim-item': isAnimated, 'wiggle': isWiggling }" 
    :data-id="show.id || show.show_id" 
    @click="handleClick"
    @animationend="handleAnimationEnd"
  >
    <div v-if="showDeleteBadge" class="wl-delete-badge" style="left: -5px; top: -5px;" @click.stop="onDelete">
      <span v-html="icons.minus"></span>
    </div>

    <div v-if="isBroken" class="hist-poster is-placeholder" v-html="icons.person_placeholder"></div>
    <img v-else :src="currentPosterUrl" class="hist-poster" loading="lazy" decoding="async" @load="validateImage" @error="handleError">
    <div class="hist-info">
      <div class="hist-title">{{ show.show__title || show.title }}</div>
      <div class="hist-orig" v-if="show.show__original_title && show.show__original_title !== (show.show__title || show.title)">
        {{ show.show__original_title }}
      </div>
      <div class="hist-meta">
        <span v-if="itemYear">{{ itemYear }}</span>
        <span v-if="season > 0" class="hist-badge">s{{ season }}e{{ String(episode).padStart(2, '0') }}</span>
        <span v-if="rating" class="rating-badge" :class="getRatingClass(rating)">
          <span v-html="icons.star"></span>{{ rating }}
        </span>
        <span style="opacity: 0.6;" v-if="displayDate">· {{ displayDate }}</span>
      </div>
      <div v-if="show.user_names?.length > 1" class="li-sub" style="font-size:11px; margin-top:4px;">
        👥 {{ show.user_names.join(', ') }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useUIStore } from '../../stores/uiStore'
import { useStatsStore } from '../../stores/useStatsStore'
import { useTelegram } from '../../composables/useTelegram'
import { icons } from '../../utils/icons'
import { getUserColor, getRatingClass } from '../../utils/helpers'

const props = defineProps({
  show: { type: Object, required: true },
  viewMode: { type: String, default: 'grid' },
  context: { type: String, default: 'search' },
  historyId: { type: String, default: '' }
})

const uiStore = useUIStore()
const statsStore = useStatsStore()
const { showConfirm } = useTelegram()
const isBroken = ref(false)
const isAnimated = ref(true)

const isHistory = computed(() => props.context === 'history' || props.context === 'wishlist')
const isWiggling = computed(() => {
  if (props.context === 'wishlist') return wishlistStoreActive.value && wishlistStoreActive.value.isReorderItemsMode
  return props.context === 'history' && uiStore.isHistoryEditMode
})
const showDeleteBadge = computed(() => {
  if (props.context === 'wishlist') return true
  return props.context === 'history' && uiStore.isHistoryEditMode && props.historyId !== 'ratings'
})
const itemYear = computed(() => props.show.show__year || props.show.year)
const displayDate = computed(() => props.show.view_date || props.show.date || props.show.added_at)
const season = computed(() => props.show.season_number ?? props.show.season)
const episode = computed(() => props.show.episode_number ?? props.show.episode)
const rating = computed(() => {
  const showId = props.show.show_id || props.show.id
  if (statsStore.isShared) {
    return props.show.user_rating || props.show.rating || props.show.user_show_rating
  }
  const local = statsStore.userShowRatings[showId]
  if (local !== undefined) return local
  return props.show.user_rating || props.show.rating || props.show.user_show_rating
})

const currentPosterUrl = computed(() => {
  const url = props.show.poster_url || ''
  if (!url) return ''
  return props.viewMode === 'grid' ? url.replace('/small/', '/medium/') : url
})

import { useWishlistStore } from '../../stores/wishlistStore'
const wishlistStoreActive = computed(() => {
  try {
    return useWishlistStore()
  } catch (e) {
    return null
  }
})

const handleAnimationEnd = () => {
  isAnimated.value = false
}

const validateImage = (e) => {
  if (e.target.naturalWidth === 208 && e.target.naturalHeight === 304) {
    isBroken.value = true
  }
}

const handleError = () => {
  isBroken.value = true
}

const handleClick = () => {
  if (props.context === 'wishlist' && wishlistStoreActive.value?.isReorderItemsMode) return
  if (uiStore.isHistoryEditMode) return
  const id = props.show.show_id || props.show.id
  if (id) uiStore.openLayer('show', id)
}

const onDelete = (event) => {
  if (props.context === 'wishlist') {
    uiStore.openModal('wlDelete', { id: props.show.id, title: props.show.show__title || props.show.title })
    return
  }

  const el = event?.currentTarget?.closest('.grid-item-wrap, .hist-item')

  showConfirm("Удалить эту запись?", (ok) => {
    if (ok) {
      const itemId = props.show.id || props.show.show_id;
      if (el) {
        el.classList.remove('wiggle')
        el.classList.add('anim-shrink')
        setTimeout(() => {
          statsStore.removeHistoryItem(itemId, props.historyId)
        }, 350)
      } else {
        statsStore.removeHistoryItem(itemId, props.historyId)
      }
    }
  })
}

const addToWishlist = () => {
  uiStore.openModal('wlFolder', { 
    showId: props.show.id || props.show.show_id, 
    title: props.show.show__title || props.show.title 
  })
}
</script>