<template>
  <div class="layer-content" v-if="show">
    <div class="layer-header">
       <button class="tab clickable" @click="uiStore.popLayer">
         <span v-html="icons.chevron_left"></span> Назад
       </button>
       <div class="layer-title-main">{{ show.title }}</div>
    </div>

    <div class="hero-container">
      <div class="hero-bg" :style="{ backgroundImage: `url(${show.poster_large})` }"></div>
      <div class="hero-gradient"></div>
      
      <div style="position: relative; z-index: 3; height: 85%; max-width: 65%; display: flex; align-items: flex-end;">
        <div style="position: relative; height: 100%; display: flex; align-items: flex-end;">
          <img :src="show.poster_large" class="hero-poster" style="max-width: 100%; height: 100%; margin: 0; box-shadow: none;" alt="poster">
          
          <div class="grid-badges" style="position: absolute; top: 12px; left: 12px; right: auto; align-items: flex-start; z-index: 10;">
            <span v-if="currentPersonalRating" class="rating-badge" style="background: rgba(0, 0, 0, 0.6); color: var(--accent); border: 1px solid rgba(255, 255, 255, 0.1); font-size: 20px; padding: 4px 10px; border-radius: 10px; gap: 5px; display: inline-flex; align-items: center; font-weight: 800; text-shadow: none;">
              <span v-html="icons.star" style="font-size: 20px; display: inline-flex; align-items: center;"></span>{{ currentPersonalRating }}
            </span>
          </div>
        </div>

        <button class="detail-wishlist-btn anim-item" @click="openWishlistModal">
          <span v-html="icons.bookmark_plus"></span>
        </button>
        <button class="detail-add-view-btn anim-item" @click="openAddView">
          <span v-html="icons.eye"></span>
        </button>
        <button class="detail-rate-btn anim-item" @click="openRating">
          <span v-html="icons.star"></span>
        </button>
      </div>
    </div>

    <div class="show-info">
      <div class="show-title">{{ show.title }}</div>
      <div class="show-orig" v-if="show.original_title !== show.title">{{ show.original_title }}</div>
      
      <div class="show-meta-tags">
        <div v-for="c in show.countries" :key="c.id" class="sm-tag clickable" @click="uiStore.openLayer('country', c.id)">
          {{ c.emoji }} {{ c.name }}
        </div>
      </div>

      <div class="show-meta-tags">
        <div class="sm-tag">{{ show.year || '?' }}</div>
        <div class="sm-tag" style="color:var(--info)">{{ show.type }}</div>
        <div class="sm-tag" v-if="show.status">{{ show.status }}</div>
      </div>

      <div class="show-meta-tags">
        <div v-if="show.kinopoisk_rating" class="sm-tag" style="background:rgba(241, 90, 36, 0.15); color:#f15a24; border:none">KP {{ show.kinopoisk_rating }}</div>
        <div v-if="show.imdb_rating" class="sm-tag" style="background:rgba(245, 197, 24, 0.15); color:#f5c518; border:none">IMDb {{ show.imdb_rating }}</div>
        <div v-if="show.internal_rating" class="sm-tag" style="background:var(--accent-dim); color:var(--accent); border:none">★ {{ show.internal_rating.toFixed(1) }}</div>
      </div>
    </div>

    <div class="plot-box" v-if="show.plot">{{ show.plot }}</div>

    <div class="label" v-if="show.genres?.length">
      <div class="icon" style="color:var(--info)" v-html="icons.star"></div> Жанры
    </div>
    <div class="h-scroll-container" v-if="show.genres?.length" style="padding-bottom: 30px;">
      <div v-for="g in show.genres" :key="g.id" class="genre-pill" @click="uiStore.openLayer('genre', g.id)">
        {{ g.name }}
      </div>
    </div>
    
    <template v-for="group in show.crew" :key="group.profession">
      <div class="label">{{ group.profession }}</div>
      <div class="h-scroll-container">
         <PersonPill v-for="person in group.persons" :key="person.id" :person="person" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useApi } from '../../composables/useApi'
import { useUIStore } from '../../stores/uiStore'
import { useStatsStore } from '../../stores/useStatsStore'
import { icons } from '../../utils/icons'
import PersonPill from '../shared/PersonPill.vue'

const props = defineProps(['showId'])
const api = useApi()
const uiStore = useUIStore()
const statsStore = useStatsStore()
const show = ref(null)

const currentPersonalRating = computed(() => {
  if (!show.value) return null
  const local = statsStore.userShowRatings[show.value.id]
  return local !== undefined ? local : show.value.personal_rating
})

const getRatingClass = (val) => {
  if (!val) return ''
  if (val >= 8) return 'rating-high'
  if (val >= 6) return 'rating-mid'
  return 'rating-low'
}

const loadShowData = async () => {
  try {
    const data = await api.get(`show/${props.showId}/`)
    show.value = data
  } catch (e) {
    console.error('[ShowDetailsLayer] Failed to load show:', e)
    uiStore.showToast('Ошибка загрузки')
    uiStore.popLayer()
  }
}

onMounted(loadShowData)

watch(() => uiStore.modals.rateShow.isOpen, async (newVal, oldVal) => {
  if (oldVal === true && newVal === false) {
    await loadShowData()
  }
})

const openWishlistModal = () => {
  uiStore.openModal('wlFolder', { showId: show.value.id, title: show.value.title })
}

const openRating = () => {
  uiStore.openModal('rateShow', {
    showId: show.value.id,
    title: show.value.title,
    initialValue: currentPersonalRating.value,
    type: show.value.type
  })
}

const openAddView = () => uiStore.openModal('addView', { showId: show.value.id, title: show.value.title })
</script>