<template>
  <div 
    v-if="viewMode === 'grid'" 
    class="grid-item-wrap anim-item" 
    :class="{ 'history-mode': isHistory, 'wiggle': isWiggling }"
    @click="handleClick"
  >
    <div 
      v-if="showDeleteBadge" 
      class="wl-delete-badge" 
      @click.stop="onDelete"
    >
      <span v-html="icons.minus"></span>
    </div>

    <div class="grid-item">
      <img :src="posterUrl" class="grid-poster" loading="lazy">
      
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
    <div class="grid-below-title" ref="titleEl">{{ show.show__title || show.title }}</div>
  </div>

  <div 
    v-else 
    class="hist-item clickable anim-item" 
    :class="{ 'wiggle': isWiggling }"
    @click="handleClick"
  >
    <div 
      v-if="showDeleteBadge" 
      class="wl-delete-badge" 
      style="left: -5px; top: -5px;"
      @click.stop="onDelete"
    >
      <span v-html="icons.minus"></span>
    </div>

    <img :src="posterUrl" class="hist-poster" loading="lazy">
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
import { computed, ref, onMounted } from 'vue'
import { useUIStore } from '../../stores/uiStore'
import { useStatsStore } from '../../stores/useStatsStore'
import { useTelegram } from '../../composables/useTelegram'
import { icons } from '../../utils/icons'
import { getUserColor } from '../../utils/helpers'

const uiStore = useUIStore()
const statsStore = useStatsStore()
const { showConfirm } = useTelegram()

const props = defineProps({
  show: { type: Object, required: true },
  viewMode: { type: String, default: 'grid' },
  context: { type: String, default: 'search' },
  historyId: { type: String, default: '' }
})

const titleEl = ref(null)

const isHistory = computed(() => props.context === 'history')
const isWiggling = computed(() => isHistory.value && uiStore.isHistoryEditMode)
const showDeleteBadge = computed(() => isHistory.value && uiStore.isHistoryEditMode && props.historyId !== 'ratings')

const itemYear = computed(() => props.show.show__year || props.show.year)
const displayDate = computed(() => props.show.view_date || props.show.date)

const season = computed(() => props.show.season_number ?? props.show.season)
const episode = computed(() => props.show.episode_number ?? props.show.episode)
const rating = computed(() => props.show.user_rating || props.show.rating || props.show.user_show_rating)

const posterUrl = computed(() => {
  const url = props.show.poster_url || ''
  if (!url) return ''
  return props.viewMode === 'grid' ? url.replace('/small/', '/medium/') : url
})

const getRatingClass = (val) => {
  if (!val) return ''
  if (val >= 8) return 'rating-high'
  if (val >= 6) return 'rating-mid'
  return 'rating-low'
}

const handleClick = () => {
  if (uiStore.isHistoryEditMode) return
  const id = props.show.show_id || props.show.id
  if (id) uiStore.openLayer('show', id)
}

const onDelete = () => {
  showConfirm("Удалить эту запись?", (ok) => {
    if (ok) statsStore.removeHistoryItem(props.show.id)
  })
}

const addToWishlist = () => {
  uiStore.openModal('wlFolder', { 
    showId: props.show.id || props.show.show_id, 
    title: props.show.show__title || props.show.title 
  })
}

onMounted(() => {
    if (titleEl.value) uiStore.fitText(titleEl.value)
})
</script>