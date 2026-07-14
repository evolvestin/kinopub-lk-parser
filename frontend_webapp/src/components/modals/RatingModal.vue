<template>
  <div class="modal-overlay show" @click.self="close">
    <div class="modal-content" :class="scoreColorClass" :style="{ padding: '24px', height: modalHeight, minHeight: modalHeight, display: 'flex', flexDirection: 'column' }">
      <div id="rate-nav-bar">
        <button v-if="level !== 'show' && level !== 'seasons'" class="vt-btn" style="padding: 4px 8px; margin-right: 8px;" @click="goBack">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="3"><path d="M15 18l-6-6 6-6"/></svg>
        </button>
        <div id="rate-breadcrumb">{{ breadcrumbText }}</div>
      </div>

      <div class="show-title" style="margin: 12px 0; font-size: 20px; font-weight: 900; color: var(--text-primary); text-align: center; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">{{ title }}</div>
      
      <div v-if="isSeries" class="view-toggle" id="rate-mode-toggle" style="margin-bottom: 20px; flex-shrink: 0;">
        <button class="vt-btn" :class="{ active: level === 'show' }" style="flex: 1;" @click="level = 'show'">Весь сериал</button>
        <button class="vt-btn" :class="{ active: level === 'seasons' }" style="flex: 1;" @click="goToSeasons">По сериям</button>
      </div>

      <div id="rate-content-area" style="flex: 1; display: flex; flex-direction: column; justify-content: center; min-height: 0;">
        <div v-if="loading" class="loader-inline">
          <div class="spinner"></div>
        </div>

        <div v-else-if="level === 'show' || level === 'score'" class="rate-container">
          <div class="rate-score-display">
            <div class="rate-score-huge">{{ displayValue }}<span>/ 10</span></div>
          </div>
          
          <div class="rate-slider-wrap" ref="sliderRef" @pointerdown="startDrag">
            <div class="rate-slider-track">
              <div class="rate-slider-fill" :style="{ width: percent + '%' }"></div>
              <div class="rate-slider-handle" :style="{ left: percent + '%' }"></div>
            </div>
            <div class="rate-scale-labels">
              <span v-for="n in 10" :key="n">{{ n }}</span>
            </div>
          </div>
        </div>

        <div v-else-if="level === 'seasons'" id="rate-episodes-nav" class="custom-scrollbar" style="flex: 1; overflow-y: auto; min-height: 0; padding: 4px; padding-right: 8px;">
          <div class="rating-grid-wa">
            <button 
              v-for="s in episodesData" 
              :key="s.season_number" 
              class="rating-grid-btn" 
              :class="getSeasonClass(s)"
              @click="selectSeason(s)"
            >
              Сезон {{ s.season_number }}
              <span v-if="getRatedEpisodesCount(s) > 0" style="font-size:10px; display:block; font-weight:800;">
                ★ {{ getSeasonAverage(s).toFixed(1) }} ({{ getRatedEpisodesCount(s) }}/{{ s.episodes.length }})
              </span>
              <span v-else style="opacity:0.5; font-size:10px; display:block;">
                0/{{ s.episodes.length }}
              </span>
            </button>
          </div>
        </div>

        <div v-else-if="level === 'episodes' && selectedSeason" id="rate-episodes-nav" class="custom-scrollbar" style="flex: 1; overflow-y: auto; min-height: 0; padding: 4px; padding-right: 8px;">
          <div class="rating-grid-wa" style="grid-template-columns: repeat(4, 1fr);">
            <button 
              v-for="e in selectedSeason.episodes" 
              :key="e.episode_number" 
              class="rating-grid-btn" 
              :class="getEpisodeClass(e)"
              @click="selectEpisode(e)"
            >
              <span v-if="e.rating" style="font-weight:900;">★ {{ e.rating }}</span>
              <span v-else>E{{ e.episode_number }}</span>
            </button>
          </div>
        </div>
      </div>

      <div style="display: flex; gap: 12px; margin-top: 20px; flex-shrink: 0;">
        <button 
          v-if="showDeleteButton" 
          class="btn-primary" 
          style="margin: 0; background: var(--bg-input); color: var(--danger); flex: 1; box-shadow: none;" 
          @click="deleteRating"
        >
          Удалить
        </button>
        <button 
          v-if="level === 'show' || level === 'score'" 
          class="btn-primary" 
          style="margin: 0; flex: 2;" 
          :disabled="isSaving" 
          @click="saveRating"
        >
          <div v-if="isSaving" class="spinner" style="width:16px;height:16px;"></div>
          <span v-else>Сохранить</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { useUIStore } from '../../stores/uiStore'
import { useStatsStore } from '../../stores/useStatsStore'

const props = defineProps(['showId', 'title', 'initialValue', 'type'])
const emit = defineEmits(['close'])

const api = useApi()
const uiStore = useUIStore()
const statsStore = useStatsStore()

const level = ref('show')
const val = ref(5.0)
const season = ref(null)
const episode = ref(null)
const episodesData = ref([])

const loading = ref(false)
const isSaving = ref(false)
const needsRefresh = ref(false)
const sliderRef = ref(null)
const modalHeight = ref('520px')

const hasExistingRating = computed(() => {
  const iv = props.initialValue
  if (iv === undefined || iv === null || iv === 'null' || iv === 'undefined' || iv === '') {
    return false
  }
  const parsed = parseFloat(iv)
  return !isNaN(parsed) && parsed > 0
})

const isSeries = computed(() => {
  const seriesTypes = ['Series', 'Documentary Series', 'TV Show']
  return props.type && seriesTypes.includes(props.type)
})

const percent = computed(() => ((val.value - 1) / 9) * 100)
const displayValue = computed(() => val.value.toFixed(val.value % 1 === 0 ? 0 : 1))

const getSeasonAverage = (s) => {
  if (!s || !s.episodes) return 0
  const rated = s.episodes.filter(e => e.rating)
  if (!rated.length) return 0
  const sum = rated.reduce((acc, e) => acc + parseFloat(e.rating), 0)
  return sum / rated.length
}

const getSeasonClass = (s) => {
  const avg = getSeasonAverage(s)
  if (avg === 0) return ''
  let cls = 'active '
  if (avg < 5) cls += 'score-low'
  else if (avg < 8) cls += 'score-mid'
  else cls += 'score-high'
  return cls
}

const scoreColorClass = computed(() => {
  let scoreVal = val.value
  if (level.value === 'episodes' && selectedSeason.value) {
    const avg = getSeasonAverage(selectedSeason.value)
    if (avg === 0) return ''
    scoreVal = avg
  } else if (level.value === 'seasons') {
    return ''
  }
  if (scoreVal < 5) return 'score-low'
  if (scoreVal < 8) return 'score-mid'
  return 'score-high'
})

const breadcrumbText = computed(() => {
  if (level.value === 'show') return 'Общая оценка'
  if (level.value === 'seasons') return 'Выбор сезона'
  if (level.value === 'episodes' && season.value) return `Сезон ${season.value}`
  if (level.value === 'score' && season.value && episode.value) return `S${season.value} E${episode.value}`
  return 'Оценка контента'
})

const selectedSeason = computed(() => {
  if (!season.value) return null
  return episodesData.value.find(s => s.season_number === season.value) || null
})

const currentEpisodeData = computed(() => {
  if (!selectedSeason.value || !episode.value) return null
  return selectedSeason.value.episodes.find(e => e.episode_number === episode.value) || null
})

const showDeleteButton = computed(() => {
  if (level.value === 'show') {
    return hasExistingRating.value
  }
  if (level.value === 'score') {
    return !!(currentEpisodeData.value && currentEpisodeData.value.rating)
  }
  return false
})

const calculateStableHeight = () => {
  if (!isSeries.value || !episodesData.value.length) {
    modalHeight.value = '520px'
    return
  }

  const seasonsCount = episodesData.value.length
  const seasonsRows = Math.ceil(seasonsCount / 3)
  const seasonsHeight = 280 + (seasonsRows * 64)

  let maxEpisodesCount = 0
  episodesData.value.forEach(s => {
    if (s.episodes && s.episodes.length > maxEpisodesCount) {
      maxEpisodesCount = s.episodes.length
    }
  })
  const episodesRows = Math.ceil(maxEpisodesCount / 4)
  const episodesHeight = 230 + (episodesRows * 64)

  const maxCalculated = Math.max(seasonsHeight, episodesHeight, 520)
  const maxHeightLimit = Math.min(620, Math.floor(window.innerHeight * 0.8))
  const finalHeight = Math.min(maxCalculated, maxHeightLimit)
  
  modalHeight.value = `${finalHeight}px`
}

const fetchEpisodes = async (silent = false) => {
  if (!silent) loading.value = true
  try {
    if (uiStore.episodesCache[props.showId]) {
      episodesData.value = uiStore.episodesCache[props.showId]
    } else {
      const data = await api.post('get_episodes/', { show_id: props.showId })
      episodesData.value = data.seasons || []
      uiStore.episodesCache[props.showId] = episodesData.value
    }
  } catch (e) {
    uiStore.showToast('Ошибка загрузки серий')
  } finally {
    if (!silent) loading.value = false
  }
}

onMounted(async () => {
  if (hasExistingRating.value) {
    val.value = parseFloat(props.initialValue)
  } else {
    val.value = 5.0
  }
  if (isSeries.value) {
    if (uiStore.episodesCache[props.showId]) {
      episodesData.value = uiStore.episodesCache[props.showId]
      calculateStableHeight()
    } else {
      await fetchEpisodes(true)
      calculateStableHeight()
    }
  } else {
    modalHeight.value = '420px'
  }
})

const startDrag = (e) => {
  const move = (event) => {
    if (!sliderRef.value) return
    const rect = sliderRef.value.getBoundingClientRect()
    const clientX = event.clientX || (event.touches ? event.touches[0].clientX : 0)
    let p = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
    let newVal = Math.round((1 + (p * 9)) * 2) / 2
    if (newVal !== val.value) {
      if (window.navigator.vibrate) window.navigator.vibrate(5)
      val.value = newVal
    }
  }
  const stop = () => {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', stop)
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', stop)
  move(e)
}

const goToSeasons = async () => {
  level.value = 'seasons'
  if (!episodesData.value.length) {
    await fetchEpisodes()
    calculateStableHeight()
  }
}

const selectSeason = (s) => {
  season.value = s.season_number
  level.value = 'episodes'
}

const getRatedEpisodesCount = (s) => {
  return s.episodes.filter(e => e.rating).length
}

const getEpisodeClass = (e) => {
  if (!e.rating) return ''
  let cls = 'active '
  if (e.rating < 5) cls += 'score-low'
  else if (e.rating < 8) cls += 'score-mid'
  else cls += 'score-high'
  return cls
}

const selectEpisode = (e) => {
  episode.value = e.episode_number
  val.value = e.rating ? parseFloat(e.rating) : 5.0
  level.value = 'score'
}

const goBack = () => {
  if (level.value === 'score') {
    level.value = 'episodes'
  } else if (level.value === 'episodes') {
    level.value = 'seasons'
  }
}

const close = () => {
  if (needsRefresh.value) {
    statsStore.statsCache = {}
    statsStore.fetchStats(statsStore.currentYear)
  }
  emit('close')
}

const saveRating = async () => {
  isSaving.value = true
  try {
    await api.post('rate/', {
      show_id: props.showId,
      rating: val.value,
      season: season.value,
      episode: episode.value
    })
    if (!season.value && !episode.value) {
      statsStore.setOptimisticRating(props.showId, val.value)
    }
    uiStore.showToast('Оценка сохранена')
    needsRefresh.value = true
    if (level.value === 'score') {
      await fetchEpisodes()
      level.value = 'episodes'
    } else {
      close()
    }
  } catch (e) {
    uiStore.showToast('Ошибка сохранения')
  } finally {
    isSaving.value = false
  }
}

const deleteRating = async () => {
  if (!confirm('Удалить оценку?')) return
  isSaving.value = true
  try {
    await api.post('delete_rating/', {
      show_id: props.showId,
      season: season.value,
      episode: episode.value
    })
    if (!season.value && !episode.value) {
      statsStore.setOptimisticRating(props.showId, null)
    }
    uiStore.showToast('Оценка удалена')
    needsRefresh.value = true
    if (level.value === 'score') {
      await fetchEpisodes()
      level.value = 'episodes'
    } else {
      close()
    }
  } catch (e) {
    uiStore.showToast('Ошибка удаления')
  } finally {
    isSaving.value = false
  }
}
</script>

<style scoped>
@import '../../../../kinopub_parser/static/css/rating.css';
</style>