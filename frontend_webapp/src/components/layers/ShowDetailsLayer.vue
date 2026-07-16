<template>
  <div class="layer-content" v-if="show">
    <div class="layer-header">
       <button class="tab clickable" @click="uiStore.popLayer">
         <span v-html="icons.chevron_left"></span> Назад
       </button>
       <div class="layer-title-main">{{ show.title }}</div>
    </div>

    <div class="hero-container">
      <div class="hero-bg" :style="{ backgroundImage: activeBg ? `url(${activeBg})` : 'none' }"></div>
      <div class="hero-gradient"></div>
      
      <div style="position: relative; z-index: 3; height: 95%; max-width: 85%; aspect-ratio: 2/3; display: flex; align-items: flex-end;">
        <div style="position: relative; width: 100%; height: 100%; display: flex; align-items: flex-end;">
          <img :src="activePoster" class="hero-poster" style="margin: 0; box-shadow: none;" alt="poster">
          
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
        <div class="sm-tag" style="color:var(--info)">{{ showTypeRu }}</div>
        <div class="sm-tag" v-if="show.status">{{ showStatusRu }}</div>
      </div>

      <div class="show-meta-tags">
        <div v-if="show.kinopoisk_rating" class="sm-tag clickable" style="background:rgba(241, 90, 36, 0.15); color:#f15a24; border:none" @click="openRatingsDetails('kp')">KP {{ show.kinopoisk_rating }}</div>
        <div v-if="show.imdb_rating" class="sm-tag clickable" style="background:rgba(245, 197, 24, 0.15); color:#f5c518; border:none" @click="openRatingsDetails('imdb')">IMDb {{ show.imdb_rating }}</div>
        <div v-if="show.internal_rating" class="sm-tag clickable" style="background:var(--accent-dim); color:var(--accent); border:none" @click="openRatingsDetails('lr')">★ {{ show.internal_rating.toFixed(1) }}</div>
      </div>
    </div>

    <div class="plot-box" v-if="show.plot">{{ show.plot }}</div>

    <div class="label" v-if="show.genres?.length">
      <div class="icon" style="color:var(--info)" v-html="icons.star"></div> Жанры
    </div>
    <div class="h-scroll-container anim-active" v-if="show.genres?.length" style="padding-bottom: 30px;">
      <div v-for="g in show.genres" :key="g.id" class="genre-pill" @click="uiStore.openLayer('genre', g.id)">
        {{ g.name }}
      </div>
    </div>
    
    <template v-for="group in show.crew" :key="group.profession">
      <div class="label">{{ group.profession }}</div>
      <div class="h-scroll-container anim-active">
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
import { preloadImage } from '../../utils/helpers'
import PersonPill from '../shared/PersonPill.vue'

const props = defineProps(['showId'])
const api = useApi()
const uiStore = useUIStore()
const statsStore = useStatsStore()

const show = ref(null)
const activePoster = ref('')
const activeBg = ref('')

const currentPersonalRating = computed(() => {
  if (!show.value) return null
  if (statsStore.isShared) {
    const sharedRating = statsStore.sharedShowRatings[show.value.id]
    return sharedRating !== undefined ? sharedRating : null
  }
  const local = statsStore.userShowRatings[show.value.id]
  return local !== undefined ? local : show.value.personal_rating
})

const viewerRating = computed(() => {
  if (!show.value) return null
  const local = statsStore.userShowRatings[show.value.id]
  return local !== undefined ? local : show.value.personal_rating
})

const showTypeRu = computed(() => {
  if (!show.value) return ''
  const mapping = {
    'Series': 'Сериал',
    'Movie': 'Фильм',
    'Concert': 'Концерт',
    'Documentary Movie': 'Док. фильм',
    'Documentary Series': 'Док. сериал',
    'TV Show': 'ТВ-шоу',
    '3D Movie': '3D фильм'
  }
  return mapping[show.value.type] || show.value.type || ''
})

const showStatusRu = computed(() => {
  if (!show.value) return ''
  const mapping = {
    'Finished': 'Завершен',
    'Ongoing': 'В эфире',
    'Filming': 'Съемки',
    'Post Production': 'Постпродакшен',
    'Pre Production': 'Препродакшен'
  }
  return mapping[show.value.status] || show.value.status || ''
})

const loadShowData = async () => {
  if (uiStore.showsCache[props.showId]) {
    const cachedData = uiStore.showsCache[props.showId]
    show.value = cachedData
    activePoster.value = cachedData.poster_medium || ''
    activeBg.value = cachedData.poster_medium || ''
    if (cachedData.poster_large) {
      activePoster.value = cachedData.poster_large
      activeBg.value = cachedData.poster_large
    }
  }

  try {
    const data = await api.get(`show/${props.showId}/`)
    show.value = data
    uiStore.showsCache[props.showId] = data

    if (data.crew) {
      data.crew.forEach(group => {
        if (group.persons) {
          group.persons.forEach(person => {
            if (person.photo_url) {
              preloadImage(person.photo_url, 'low').then(success => {
                if (!success && person.fallback_photo_url) {
                  preloadImage(person.fallback_photo_url, 'low')
                }
              })
            } else if (person.fallback_photo_url) {
              preloadImage(person.fallback_photo_url, 'low')
            }
          })
        }
      })
    }

    if (['Series', 'Documentary Series', 'TV Show'].includes(data.type)) {
      if (!uiStore.episodesCache[props.showId]) {
        api.post('get_episodes/', { show_id: props.showId }).then(res => {
          uiStore.episodesCache[props.showId] = res.seasons || []
        }).catch(() => {})
      }
    }

    activePoster.value = data.poster_medium || ''
    activeBg.value = data.poster_medium || ''

    if (data.poster_large) {
      const img = new Image()
      img.src = data.poster_large
      img.onload = () => {
        activePoster.value = data.poster_large
        activeBg.value = data.poster_large
      }
    }
  } catch (e) {
    if (!show.value) {
      console.error('[ShowDetailsLayer] Failed to load show:', e)
      uiStore.showToast('Ошибка загрузки')
      uiStore.popLayer()
    }
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
    initialValue: viewerRating.value,
    type: show.value.type
  })
}

const openAddView = () => uiStore.openModal('addView', { showId: show.value.id, title: show.value.title, type: show.value.type })

const openRatingsDetails = (ratingType) => {
  uiStore.openModal('details', { showId: props.showId, ratingType })
}
</script>