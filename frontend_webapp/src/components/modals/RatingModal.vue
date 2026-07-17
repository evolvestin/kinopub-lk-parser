<template>
  <div class="modal-overlay show" @click.self="close">
    <div class="modal-content" :class="scoreColorClass" :style="{ padding: '24px', height: modalHeight, minHeight: modalHeight, display: 'flex', flexDirection: 'column' }">
      
      <div class="modal-header-container" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-shrink: 0; width: 100%;">
        <div style="display: flex; align-items: center; gap: 12px; min-width: 0;">
          <button v-if="level !== 'show' && level !== 'seasons'" class="modal-back-btn clickable" @click="goBack">
            <span v-html="icons.chevron_left"></span>
          </button>
          <div style="font-size: 12px; font-weight: 900; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            {{ breadcrumbText }}
          </div>
        </div>
        <button class="modal-close" @click="close" style="margin-left: auto;">×</button>
      </div>

      <div class="show-title" style="margin: 12px 0; font-size: 20px; font-weight: 900; color: var(--text-primary); text-align: center; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">{{ title }}</div>
      
      <div v-if="statsStore.isShared" style="margin-bottom: 16px; padding: 12px; background: rgba(46, 204, 113, 0.1); border: 1px solid rgba(46, 204, 113, 0.2); border-radius: 12px; font-size: 13px; color: var(--text-primary); line-height: 1.4; text-align: center; flex-shrink: 0;">
        <span style="color: var(--accent); font-weight: 800; display: block; margin-bottom: 4px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">⭐ Ваша личная оценка</span>
        Вы просматриваете чужую статистику, но здесь вы видите и редактируете <strong>исключительно свою собственную оценку</strong>.
      </div>

      <div v-if="isSeries" class="view-toggle" id="rate-mode-toggle" style="margin-bottom: 20px; flex-shrink: 0;">
        <button class="vt-btn" :class="{ active: level === 'show' }" style="flex: 1;" @click="level = 'show'">Весь сериал</button>
        <button class="vt-btn" :class="{ active: level !== 'show' }" style="flex: 1;" @click="goToSeasons">По сериям</button>
      </div>

      <div id="rate-content-area" style="flex: 1; display: flex; flex-direction: column; justify-content: center; min-height: 0;">
        <div v-if="loading" class="loader-inline">
          <div class="spinner"></div>
        </div>

        <div v-else-if="level === 'show' || level === 'score'" class="rate-container">
          <div v-if="statsStore.currentStats?.ratings?.total === 0 && !uiStore.dismissedHints['rate_modal']" class="modal-hint-box" style="position: relative; width: 100%; text-align: left; margin-bottom: 0;">
            Потяните ползунок вправо или влево, чтобы выбрать нужную оценку для этого тайтла.
            <button @click="uiStore.dismissHint('rate_modal')" style="position: absolute; right: 8px; top: 8px; background: none; border: none; color: var(--text-muted); cursor: pointer;">×</button>
          </div>

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

      <div style="display: flex; gap: 12px; margin-top: 20px; flex-shrink: 0; position: relative; z-index: 10;">
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
          :disabled="isSaving || isRatingUnchanged" 
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
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '../../composables/useApi'
import { useUIStore } from '../../stores/uiStore'
import { useStatsStore } from '../../stores/useStatsStore'
import { icons } from '../../utils/icons'

const props = defineProps(['showId', 'title', 'initialValue', 'type'])
const emit = defineEmits(['close'])

const api = useApi()
const uiStore = useUIStore()
const statsStore = useStatsStore()
const router = useRouter()

const episodesData = ref([])
const loading = ref(false)
const isSaving = ref(false)
const needsRefresh = ref(false)
const sliderRef = ref(null)

const localVal = ref(5.0)

const updateQueryParams = (params) => {
  const query = { ...router.currentRoute.value.query }
  Object.keys(params).forEach(key => {
    const val = params[key]
    if (val === null || val === undefined || val === '') {
      delete query[`modal_${key}`]
    } else {
      query[`modal_${key}`] = String(val)
    }
  })
  router.replace({ query }).catch(() => {})
}

const level = computed({
  get: () => router.currentRoute.value.query.modal_level || 'show',
  set: (v) => updateQueryParams({ level: v })
})

const val = computed({
  get: () => localVal.value,
  set: (v) => {
    localVal.value = v
  }
})

const season = computed({
  get: () => {
    const v = router.currentRoute.value.query.modal_season
    return v ? parseInt(v) : null
  },
  set: (v) => updateQueryParams({ season: v })
})

const isRatingUnchanged = computed(() => {
  if (level.value === 'show') {
    const current = currentPersonalRating.value
    if (current === null || current === undefined || isNaN(current)) {
      return false
    }
    return val.value === current
  }
  if (level.value === 'score') {
    const current = currentEpisodeData.value ? currentEpisodeData.value.rating : null
    if (current === null || current === undefined || isNaN(current)) {
      return false
    }
    return val.value === current
  }
  return false
})

const episode = computed({
  get: () => {
    const v = router.currentRoute.value.query.modal_episode
    return v ? parseInt(v) : null
  },
  set: (v) => updateQueryParams({ episode: v })
})

const debounce = (fn, delay) => {
  let timeout
  return (...args) => {
    clearTimeout(timeout)
    timeout = setTimeout(() => fn(...args), delay)
  }
}

const debouncedUpdateVal = debounce((v) => {
  updateQueryParams({ val: v })
}, 150)

watch(localVal, (newVal) => {
  debouncedUpdateVal(newVal)
})

watch(() => router.currentRoute.value.query.modal_val, (newVal) => {
  if (newVal !== undefined && newVal !== null) {
    const parsed = parseFloat(newVal)
    if (parsed !== localVal.value) {
      localVal.value = parsed
    }
  }
}, { immediate: true })

watch(() => router.currentRoute.value.query.modal_initialValue, (newVal) => {
  if (router.currentRoute.value.query.modal_val === undefined) {
    if (newVal !== undefined && newVal !== null && newVal !== 'null' && newVal !== 'undefined' && newVal !== '') {
      localVal.value = parseFloat(newVal)
    }
  }
}, { immediate: true })

const currentPersonalRating = computed(() => {
  if (!props.showId) return null
  const local = statsStore.userShowRatings[props.showId]
  return local !== undefined ? local : parseFloat(props.initialValue)
})

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

const showHint = computed(() => {
  return statsStore.currentStats?.ratings?.total === 0 && !uiStore.dismissedHints['rate_modal']
})

const modalHeight = computed(() => {
  const hintHeight = showHint.value ? 100 : 0
  const isShared = statsStore.isShared
  const baseHeight = (isShared ? 580 : 520) + hintHeight

  if (!isSeries.value) {
    return `${420 + hintHeight}px`
  }

  if (!episodesData.value.length) {
    return `${baseHeight}px`
  }

  const seasonsCount = episodesData.value.length
  const seasonsRows = Math.ceil(seasonsCount / 3)
  let seasonsHeight = 280 + (seasonsRows * 64)

  let maxEpisodesCount = 0
  episodesData.value.forEach(s => {
    if (s.episodes && s.episodes.length > maxEpisodesCount) {
      maxEpisodesCount = s.episodes.length
    }
  })
  const episodesRows = Math.ceil(maxEpisodesCount / 4)
  let episodesHeight = 230 + (episodesRows * 64)

  if (isShared) {
    seasonsHeight += 60
    episodesHeight += 60
  }

  const maxCalculated = Math.max(seasonsHeight, episodesHeight, baseHeight)
  const maxHeightLimit = Math.min(620, Math.floor(window.innerHeight * 0.8))
  const finalHeight = Math.min(maxCalculated, maxHeightLimit)
  
  return `${finalHeight}px`
})

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
  const queryVal = router.currentRoute.value.query.modal_val
  if (queryVal !== undefined && queryVal !== null) {
    localVal.value = parseFloat(queryVal)
  } else if (hasExistingRating.value) {
    localVal.value = parseFloat(props.initialValue)
  } else {
    localVal.value = 5.0
  }

  if (isSeries.value && !uiStore.episodesCache[props.showId]) {
    await fetchEpisodes(true)
  } else if (isSeries.value) {
    episodesData.value = uiStore.episodesCache[props.showId]
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
  }
}

const selectSeason = (s) => {
  updateQueryParams({
    season: s.season_number,
    level: 'episodes'
  })
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
  updateQueryParams({
    episode: e.episode_number,
    val: e.rating ? parseFloat(e.rating) : 5.0,
    level: 'score'
  })
}

const goBack = () => {
  if (level.value === 'score') {
    updateQueryParams({
      level: 'episodes',
      episode: null
    })
  } else if (level.value === 'episodes') {
    updateQueryParams({
      level: 'seasons',
      season: null
    })
  }
}

const close = () => {
  if (needsRefresh.value) {
    statsStore.fetchStats(statsStore.currentYear, true, true)
    statsStore.fetchStats('all', true, true)
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
    delete uiStore.showsCache[props.showId]
    needsRefresh.value = true
    if (level.value === 'score') {
      await fetchEpisodes()
      updateQueryParams({
        level: 'episodes',
        episode: null
      })
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
    delete uiStore.showsCache[props.showId]
    needsRefresh.value = true
    if (level.value === 'score') {
      await fetchEpisodes()
      updateQueryParams({
        level: 'episodes',
        episode: null
      })
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