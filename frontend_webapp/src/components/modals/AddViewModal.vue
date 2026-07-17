<template>
  <div class="modal-overlay show" @click.self="close">
    <div class="modal-content" :style="{ padding: '24px', height: modalHeight, minHeight: modalHeight, display: 'flex', flexDirection: 'column' }">
      
      <div class="modal-header-container" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-shrink: 0; width: 100%;">
        <div style="display: flex; align-items: center; gap: 12px; min-width: 0;">
          <button v-if="level !== 'main'" class="modal-back-btn clickable" @click="goBack">
            <span v-html="icons.chevron_left"></span>
          </button>
          <div style="font-size: 12px; font-weight: 900; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            {{ level === 'main' ? 'Отметить просмотр' : (level === 'seasons' ? 'Выбор сезона' : `Сезон ${selectedSeasonNumber}: Выбор серии`) }}
          </div>
        </div>
        <button class="modal-close" @click="close" style="margin-left: auto;">×</button>
      </div>

      <div v-if="level === 'main'" style="display: flex; flex-direction: column; height: 100%; min-height: 0; flex-grow: 1;">
        <div style="font-size: clamp(18px, 5vw, 22px); font-weight: 900; color: var(--accent); margin-bottom: 24px; line-height: 1.2; text-align: center; letter-spacing: -0.5px;">
          {{ context.title }}
        </div>

        <div v-if="statsStore.currentStats?.summary?.total_views === 0 && !uiStore.dismissedHints['add_view_modal']" class="modal-hint-box" style="position: relative;">
          Выберите точную дату или месяц для построения графиков активности. Если точная дата неизвестна — используйте <b>"Не помню"</b>.
          <button @click="uiStore.dismissHint('add_view_modal')" style="position: absolute; right: 8px; top: 8px; background: none; border: none; color: var(--text-muted); cursor: pointer;">×</button>
        </div>

        <div v-if="statsStore.isShared" style="margin-bottom: 16px; padding: 10px; background: rgba(231, 76, 60, 0.1); border: 1px solid rgba(231, 76, 60, 0.2); border-radius: 10px; font-size: 11px; color: var(--text-secondary); line-height: 1.3; text-align: center;">
          ⚠️ Вы отмечаете просмотр для своего <strong style="color: var(--text-primary);">личного профиля</strong>.
        </div>

        <div v-if="isSeries" style="margin-bottom: 20px; flex-shrink: 0;">
          <div style="font-size: 12px; color: var(--text-muted); font-weight: 700; margin-bottom: 6px; text-transform: uppercase;">Серия</div>
          <button class="search-input" style="width: 100%; text-align: left; display: flex; align-items: center; justify-content: space-between; background: var(--bg-input); border: 1px solid var(--border); color: var(--text-primary); cursor: pointer;" @click="openEpisodeSelector">
            <span>Сезон {{ season }}, Серия {{ episode }}</span>
            <span v-html="icons.chevron_left" style="transform: rotate(180deg); display: flex; align-items: center; height: 24px; width: 24px; color: var(--text-muted);"></span>
          </button>
        </div>

        <div style="font-size:12px; color:var(--text-muted); font-weight:700; margin-bottom:8px; text-transform:uppercase;">Когда смотрели?</div>
        <div class="view-toggle" style="margin-bottom: 16px; padding: 3px; background: var(--bg-input); flex-shrink: 0;">
          <button class="vt-btn" :class="{ active: dateMode === 'exact' }" @click="dateMode = 'exact'">Точная дата</button>
          <button class="vt-btn" :class="{ active: dateMode === 'month' }" @click="dateMode = 'month'">Месяц</button>
          <button class="vt-btn" :class="{ active: dateMode === 'year' }" @click="dateMode = 'year'">Год</button>
          <button class="vt-btn" :class="{ active: dateMode === 'unknown' }" @click="dateMode = 'unknown'">Не помню</button>
        </div>

        <div style="margin-bottom: 24px; flex-grow: 1; overflow-y: auto; min-height: 0;">
          <input v-if="dateMode === 'exact'" type="date" v-model="exactDate" class="search-input" style="width: 100%;" />
          <input v-if="dateMode === 'month'" type="month" v-model="monthDate" class="search-input" style="width: 100%;" />
          <input v-if="dateMode === 'year'" type="number" v-model="yearDate" class="search-input" placeholder="YYYY" style="width: 100%;" min="1900" max="2100" />
          <div v-if="dateMode === 'unknown'" style="font-size: 13px; color: var(--text-secondary); text-align: center; padding: 10px; background: var(--bg-input); border-radius: 12px; border: 1px dashed var(--border);">
            Просмотр будет учтен в статистике "Всё время" и закреплен в самом низу истории.
          </div>
        </div>

        <div style="display: flex; gap: 12px; margin-top: auto; flex-shrink: 0;">
          <button class="btn-primary" style="margin-top: 0; background: var(--bg-input); color: var(--text-primary); box-shadow: none; flex: 1;" @click="close">
            Отмена
          </button>
          <button class="btn-primary" style="margin-top: 0; flex: 2;" :disabled="isSaving" @click="save">
            <div v-if="isSaving" class="spinner" style="width: 16px; height: 16px;"></div>
            <span v-else>Сохранить</span>
          </button>
        </div>
      </div>

      <div v-else-if="level === 'seasons'" style="flex: 1; display: flex; flex-direction: column; min-height: 0;">
        <div v-if="loading" class="loader-inline">
          <div class="spinner"></div>
        </div>
        <div v-else class="custom-scrollbar" style="flex: 1; overflow-y: auto; padding: 4px; padding-right: 8px;">
          <div class="rating-grid-wa">
            <button 
              v-for="s in episodesData" 
              :key="s.season_number" 
              class="rating-grid-btn" 
              :class="{ active: season === s.season_number }"
              @click="selectSeason(s)"
            >
              Сезон {{ s.season_number }}
              <span style="font-size:10px; display:block; opacity: 0.6; font-weight: normal; margin-top: 2px;">
                {{ getWatchedCount(s) }} / {{ s.episodes.length }} просмотрено
              </span>
            </button>
          </div>
        </div>
      </div>

      <div v-else-if="level === 'episodes'" style="flex: 1; display: flex; flex-direction: column; min-height: 0;">
        <div class="custom-scrollbar" style="flex: 1; overflow-y: auto; padding: 4px; padding-right: 8px;">
          <div class="rating-grid-wa" style="grid-template-columns: repeat(4, 1fr);">
            <button 
              v-for="e in selectedSeason?.episodes" 
              :key="e.episode_number" 
              class="rating-grid-btn" 
              :class="{ active: e.watched }"
              @click="selectEpisode(e)"
            >
              <span v-if="e.watched" style="font-weight:900;">✓ E{{ e.episode_number }}</span>
              <span v-else>E{{ e.episode_number }}</span>
            </button>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUIStore } from '../../stores/uiStore'
import { useStatsStore } from '../../stores/useStatsStore'
import { useApi } from '../../composables/useApi'
import { icons } from '../../utils/icons'

const uiStore = useUIStore()
const statsStore = useStatsStore()
const api = useApi()
const router = useRouter()

const context = computed(() => uiStore.modals.addView.context || {})
const isSeries = computed(() => ['Series', 'Documentary Series', 'TV Show'].includes(context.value.type))

const episodesData = ref([])
const loading = ref(false)
const isSaving = ref(false)
const modalHeight = ref('520px')

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
  get: () => router.currentRoute.value.query.modal_level || 'main',
  set: (val) => updateQueryParams({ level: val })
})

const season = computed({
  get: () => parseInt(router.currentRoute.value.query.modal_season) || 1,
  set: (val) => updateQueryParams({ season: val })
})

const episode = computed({
  get: () => parseInt(router.currentRoute.value.query.modal_episode) || 1,
  set: (val) => updateQueryParams({ episode: val })
})

const selectedSeasonNumber = computed({
  get: () => {
    const val = router.currentRoute.value.query.modal_selectedSeasonNumber
    return val ? parseInt(val) : null
  },
  set: (val) => updateQueryParams({ selectedSeasonNumber: val })
})

const exactDate = computed({
  get: () => router.currentRoute.value.query.modal_exactDate || new Date().toISOString().split('T')[0],
  set: (val) => updateQueryParams({ exactDate: val })
})

const monthDate = computed({
  get: () => router.currentRoute.value.query.modal_monthDate || new Date().toISOString().substring(0, 7),
  set: (val) => updateQueryParams({ monthDate: val })
})

const yearDate = computed({
  get: () => parseInt(router.currentRoute.value.query.modal_yearDate) || new Date().getFullYear(),
  set: (val) => updateQueryParams({ yearDate: val })
})

const dateMode = computed({
  get: () => router.currentRoute.value.query.modal_dateMode || 'exact',
  set: (val) => updateQueryParams({ dateMode: val })
})

const selectedSeason = computed(() => {
  if (!selectedSeasonNumber.value) return null
  return episodesData.value.find(s => s.season_number === selectedSeasonNumber.value) || null
})

const getWatchedCount = (s) => {
  return s.episodes.filter(e => e.watched).length
}

const calculateStableHeight = () => {
  if (!isSeries.value || !episodesData.value.length) {
    modalHeight.value = '520px'
    return
  }

  const seasonsCount = episodesData.value.length
  const seasonsRows = Math.ceil(seasonsCount / 3)
  const seasonsHeight = 220 + (seasonsRows * 64)

  let maxEpisodesCount = 0
  episodesData.value.forEach(s => {
    if (s.episodes && s.episodes.length > maxEpisodesCount) {
      maxEpisodesCount = s.episodes.length
    }
  })
  const episodesRows = Math.ceil(maxEpisodesCount / 4)
  const episodesHeight = 170 + (episodesRows * 64)

  const maxCalculated = Math.max(seasonsHeight, episodesHeight, 520)
  const maxHeightLimit = Math.min(620, Math.floor(window.innerHeight * 0.8))
  
  modalHeight.value = `${Math.min(maxCalculated, maxHeightLimit)}px`
}

const fetchEpisodes = async (silent = false) => {
  if (!silent) loading.value = true
  try {
    if (uiStore.episodesCache[context.value.showId]) {
      episodesData.value = uiStore.episodesCache[context.value.showId]
    } else {
      const data = await api.post('get_episodes/', { show_id: context.value.showId })
      episodesData.value = data.seasons || []
      uiStore.episodesCache[context.value.showId] = episodesData.value
    }
  } catch (e) {
    uiStore.showToast('Ошибка загрузки серий')
  } finally {
    if (!silent) loading.value = false
  }
}

onMounted(async () => {
  if (isSeries.value) {
    if (uiStore.episodesCache[context.value.showId]) {
      episodesData.value = uiStore.episodesCache[context.value.showId]
      calculateStableHeight()
    } else {
      await fetchEpisodes(true)
      calculateStableHeight()
    }
  } else {
    modalHeight.value = '420px'
  }
})

const openEpisodeSelector = async () => {
  level.value = 'seasons'
  if (!episodesData.value.length) {
    await fetchEpisodes()
    calculateStableHeight()
  }
}

const selectSeason = (s) => {
  updateQueryParams({
    selectedSeasonNumber: s.season_number,
    level: 'episodes'
  })
}

const selectEpisode = (e) => {
  updateQueryParams({
    season: selectedSeasonNumber.value,
    episode: e.episode_number,
    level: 'main'
  })
}

const goBack = () => {
  if (level.value === 'episodes') {
    updateQueryParams({
      level: 'seasons',
      selectedSeasonNumber: null
    })
  } else if (level.value === 'seasons') {
    updateQueryParams({
      level: 'main'
    })
  }
}

const close = () => {
  uiStore.closeModal('addView')
}

const save = async () => {
  if (isSeries.value && (!season.value || !episode.value)) {
    uiStore.showToast('Укажите сезон и эпизод')
    return
  }

  let dateVal = null
  if (dateMode.value === 'exact') dateVal = exactDate.value
  if (dateMode.value === 'month') dateVal = monthDate.value
  if (dateMode.value === 'year') dateVal = yearDate.value

  isSaving.value = true
  try {
    await api.post('add_view/', {
      show_id: context.value.showId,
      season: isSeries.value ? season.value : 0,
      episode: isSeries.value ? episode.value : 0,
      date_mode: dateMode.value,
      date_val: dateVal
    })
    uiStore.showToast('Просмотр добавлен!')
    close()
  } catch (e) {
    uiStore.showToast('Ошибка сохранения')
  } finally {
    isSaving.value = false
  }
}
</script>

<style scoped>
@import '../../../../kinopub_parser/static/css/rating.css';
</style>