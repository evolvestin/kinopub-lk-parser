<template>
  <div class="modal-overlay show" @click.self="close">
    <div class="modal-content" :class="activeScoreColorClass" style="padding: 24px; min-height: 480px; display: flex; flex-direction: column;">
      
      <div class="modal-header-container" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-shrink: 0; width: 100%;">
        <div style="font-size: 12px; font-weight: 900; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px;">
          Рейтинги и оценки
        </div>
        <button class="modal-close" @click="close">×</button>
      </div>

      <div class="show-title" style="margin-bottom: 16px; font-size: 20px; font-weight: 900; color: var(--text-primary); text-align: center; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.2;">
        {{ showData?.title || 'Загрузка...' }}
      </div>

      <div class="view-toggle" style="margin-bottom: 20px; flex-shrink: 0; padding: 3px; background: var(--bg-input);">
        <button class="vt-btn" :class="{ active: ratingType === 'kp' }" style="flex: 1;" @click="ratingType = 'kp'">Кинопоиск</button>
        <button class="vt-btn" :class="{ active: ratingType === 'imdb' }" style="flex: 1;" @click="ratingType = 'imdb'">IMDb</button>
        <button class="vt-btn" :class="{ active: ratingType === 'lr' }" style="flex: 1;" @click="ratingType = 'lr'">LocalRating (LR)</button>
      </div>

      <div style="flex: 1; display: flex; flex-direction: column; min-height: 0; overflow-y: auto;" class="custom-scrollbar">
        <div v-if="loading" class="loader-inline">
          <div class="spinner"></div>
        </div>

        <div v-else-if="showData">
          <div v-if="ratingType === 'kp'" class="rate-container" style="padding: 0;">
            <div class="rate-score-display" style="margin-bottom: 10px; height: auto; padding: 15px 0; display: flex; align-items: center; justify-content: center; gap: 16px; position: relative;">
              <div class="rate-score-huge">
                {{ showData.kinopoisk_rating ? showData.kinopoisk_rating.toFixed(1) : '—' }}<span style="font-size: 16px;">/ 10</span>
              </div>
              <a v-if="showData.kinopoisk_url" :href="showData.kinopoisk_url" target="_blank" class="external-link-btn" style="color: #f15a24; background: rgba(241, 90, 36, 0.15); border: 1px solid rgba(241, 90, 36, 0.3); padding: 8px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; transition: all 0.2s; height: 38px; width: 38px;" title="Открыть на Кинопоиске">
                <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                  <polyline points="15 3 21 3 21 9"></polyline>
                  <line x1="10" y1="14" x2="21" y2="3"></line>
                </svg>
              </a>
              <a v-else :href="'https://www.kinopoisk.ru/index.php?kp_query=' + encodeURIComponent(showData.title)" target="_blank" class="external-link-btn" style="color: #f15a24; background: rgba(241, 90, 36, 0.15); border: 1px solid rgba(241, 90, 36, 0.3); padding: 8px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; transition: all 0.2s; height: 38px; width: 38px;" title="Найти на Кинопоиске">
                <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                  <polyline points="15 3 21 3 21 9"></polyline>
                  <line x1="10" y1="14" x2="21" y2="3"></line>
                </svg>
              </a>
            </div>

            <div style="text-align: center; font-size: 14px; color: var(--text-secondary); margin-bottom: 24px; font-weight: 600;">
              Голосов: <span style="color: var(--text-primary); font-weight: 800;">{{ showData.kinopoisk_votes ? showData.kinopoisk_votes.toLocaleString('ru-RU') : '—' }}</span>
            </div>

            <div v-if="showData.ext_rating" class="card" style="margin: 0 0 20px 0; padding: 16px; background: var(--bg-input); border-radius: 16px; width: 100%;">
              <div style="display: flex; flex-direction: column; gap: 10px; font-size: 13px; font-weight: 600;">
                <div v-if="showData.ext_rating.film_critics !== null" style="display: flex; justify-content: space-between;">
                  <span style="color: var(--text-secondary);">Критики мира:</span>
                  <span style="color: var(--text-primary); font-weight: 800;">{{ showData.ext_rating.film_critics.toFixed(1) }}%</span>
                </div>
                <div v-if="showData.ext_rating.russian_film_critics !== null" style="display: flex; justify-content: space-between;">
                  <span style="color: var(--text-secondary);">Критики РФ:</span>
                  <span style="color: var(--text-primary); font-weight: 800;">{{ showData.ext_rating.russian_film_critics.toFixed(1) }}%</span>
                </div>
                <div v-if="showData.ext_rating.await_rating !== null" style="display: flex; justify-content: space-between;">
                  <span style="color: var(--text-secondary);">Рейтинг ожидания:</span>
                  <span style="color: var(--text-primary); font-weight: 800;">{{ showData.ext_rating.await_rating.toFixed(1) }}%</span>
                </div>
                <div v-if="showData.ext_rating.tmdb !== null" style="display: flex; justify-content: space-between;">
                  <span style="color: var(--text-secondary);">Рейтинг TMDB:</span>
                  <span style="color: var(--text-primary); font-weight: 800;">{{ showData.ext_rating.tmdb.toFixed(1) }} / 10</span>
                </div>
              </div>
            </div>

            <div v-if="lastUpdatedDate" style="display: flex; justify-content: space-between; font-size: 11px; padding: 10px 14px; margin-bottom: 20px; width: 100%;">
              <span style="color: var(--text-muted);">Последнее обновление:</span>
              <span style="color: var(--text-muted); font-family: monospace;">{{ lastUpdatedDate }}</span>
            </div>
          </div>

          <div v-else-if="ratingType === 'imdb'" class="rate-container" style="padding: 0;">
            <div class="rate-score-display" style="margin-bottom: 10px; height: auto; padding: 15px 0; display: flex; align-items: center; justify-content: center; gap: 16px; position: relative;">
              <div class="rate-score-huge">
                {{ showData.imdb_rating ? showData.imdb_rating.toFixed(1) : '—' }}<span style="font-size: 16px;">/ 10</span>
              </div>
              <a v-if="showData.imdb_url" :href="showData.imdb_url" target="_blank" class="external-link-btn" style="color: #f5c518; background: rgba(245, 197, 24, 0.15); border: 1px solid rgba(245, 197, 24, 0.3); padding: 8px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; transition: all 0.2s; height: 38px; width: 38px;" title="Открыть на IMDb">
                <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                  <polyline points="15 3 21 3 21 9"></polyline>
                  <line x1="10" y1="14" x2="21" y2="3"></line>
                </svg>
              </a>
              <a v-else :href="'https://www.imdb.com/find?q=' + encodeURIComponent(showData.original_title || showData.title)" target="_blank" class="external-link-btn" style="color: #f5c518; background: rgba(245, 197, 24, 0.15); border: 1px solid rgba(245, 197, 24, 0.3); padding: 8px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; transition: all 0.2s; height: 38px; width: 38px;" title="Найти на IMDb">
                <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                  <polyline points="15 3 21 3 21 9"></polyline>
                  <line x1="10" y1="14" x2="21" y2="3"></line>
                </svg>
              </a>
            </div>

            <div style="text-align: center; font-size: 14px; color: var(--text-secondary); margin-bottom: 24px; font-weight: 600;">
              Голосов: <span style="color: var(--text-primary); font-weight: 800;">{{ showData.imdb_votes ? showData.imdb_votes.toLocaleString('ru-RU') : '—' }}</span>
            </div>

            <div v-if="lastUpdatedDate" style="display: flex; justify-content: space-between; font-size: 11px; padding: 10px 14px; margin-bottom: 20px; width: 100%;">
              <span style="color: var(--text-muted);">Последнее обновление:</span>
              <span style="color: var(--text-muted); font-family: monospace;">{{ lastUpdatedDate }}</span>
            </div>
          </div>

          <div v-else-if="ratingType === 'lr'" class="rate-container" style="padding: 0; align-items: stretch;">
            <div class="rate-score-display" style="margin-bottom: 10px; height: auto; padding: 15px 0; align-self: center;">
              <div class="rate-score-huge">
                {{ showData.internal_rating ? showData.internal_rating.toFixed(1) : '—' }}<span style="font-size: 16px; color: var(--text-muted);">/ 10</span>
              </div>
            </div>

            <div style="text-align: center; font-size: 14px; color: var(--text-secondary); margin-bottom: 20px; font-weight: 600; display: flex; flex-direction: column; gap: 4px; align-items: center; justify-content: center;">
              <div>Проголосовало участников: <span style="color: var(--text-primary); font-weight: 800;">{{ showData.user_ratings ? showData.user_ratings.length : '0' }}</span></div>
              <div v-if="isSeries && showData.total_ratings_count">Общее количество оценок: <span style="color: var(--text-primary); font-weight: 800;">{{ showData.total_ratings_count }}</span></div>
            </div>

            <div style="font-size: 11px; color: var(--text-muted); line-height: 1.4; text-align: center; background: var(--bg-input); padding: 10px 14px; border-radius: 12px; margin-bottom: 20px; border: 1px dashed var(--border);">
              Локальный рейтинг (LocalRating) рассчитывается на основе оценок всех пользователей бота, которые оценили данное шоу.
            </div>

            <div v-if="showData.user_ratings_details?.length" style="display: flex; flex-direction: column; gap: 12px; width: 100%;">
              <div v-for="ur in showData.user_ratings_details" :key="ur.user" style="display: flex; flex-direction: column; gap: 8px; padding: 14px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px; text-align: left; width: 100%;">
                <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                  <span style="font-size: 14px; font-weight: 800; color: var(--text-primary);">{{ ur.user }}</span>
                  <div style="display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Оценка {{ isSeries ? 'сериала' : 'фильма' }}:</span>
                    <span v-if="ur.show_rating" class="rating-badge" :class="getRatingClass(ur.show_rating)" style="font-size: 13px; font-weight: 800; padding: 3px 8px; border-radius: 8px; display: inline-flex; align-items: center; gap: 4px;">
                      <span v-html="icons.star"></span>{{ ur.show_rating.toFixed(1) }}
                    </span>
                    <span v-else style="font-size: 13px; font-weight: 800; color: var(--text-muted);">—</span>
                  </div>
                </div>

                <div v-if="isSeries && ur.episodes?.length" style="display: flex; flex-direction: column; gap: 6px; margin-top: 4px; padding-top: 8px; border-top: 1px dashed var(--border);">
                  <div style="font-size: 11px; font-weight: 800; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;">Оценки серий:</div>
                  <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                    <span v-for="ep in ur.episodes" :key="`${ep.season}-${ep.episode}`" class="rating-badge" :class="getRatingClass(ep.rating)" style="font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 6px; display: inline-flex; align-items: center; gap: 2px;">
                      {{ formatSe(ep.season, ep.episode) }}: {{ ep.rating }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div v-else-if="showData.user_ratings?.length" style="display: flex; flex-direction: column; gap: 8px; width: 100%;">
              <div v-for="ur in showData.user_ratings" :key="ur.label" style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; width: 100%;">
                <span style="font-size: 14px; font-weight: 700; color: var(--text-primary);">{{ ur.label }}</span>
                <span class="rating-badge" :class="getRatingClass(ur.rating)" style="font-size: 13px; font-weight: 800; padding: 3px 8px; border-radius: 8px; display: inline-flex; align-items: center; gap: 4px;">
                  <span v-html="icons.star"></span>{{ ur.rating.toFixed(1) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="showData" style="display: flex; gap: 12px; margin-top: 16px; flex-shrink: 0; width: 100%;">
        <button class="btn-primary" style="margin: 0;" @click="openRating">
          🌟 Оценить
        </button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUIStore } from '../../stores/uiStore'
import { useStatsStore } from '../../stores/useStatsStore'
import { useApi } from '../../composables/useApi'
import { icons } from '../../utils/icons'

const uiStore = useUIStore()
const statsStore = useStatsStore()
const api = useApi()
const router = useRouter()

const showData = ref(null)
const loading = ref(true)

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

const showId = computed(() => {
  const val = router.currentRoute.value.query.modal_showId
  return val ? parseInt(val) : null
})

const ratingType = computed({
  get: () => router.currentRoute.value.query.modal_ratingType || 'kp',
  set: (val) => updateQueryParams({ ratingType: val })
})

const lastUpdatedDate = computed(() => {
  if (!showData.value) return null
  if (showData.value.ext_rating?.updated_at) {
    return showData.value.ext_rating.updated_at
  }
  return showData.value.updated_at || null
})

const isSeries = computed(() => {
  const seriesTypes = ['Series', 'Documentary Series', 'TV Show']
  return showData.value && seriesTypes.includes(showData.value.type)
})

const activeRatingValue = computed(() => {
  if (!showData.value) return 0
  if (ratingType.value === 'kp') return showData.value.kinopoisk_rating || 0
  if (ratingType.value === 'imdb') return showData.value.imdb_rating || 0
  if (ratingType.value === 'lr') return showData.value.internal_rating || 0
  return 0
})

const activeScoreColorClass = computed(() => {
  const val = activeRatingValue.value
  if (!val) return ''
  if (val < 5) return 'score-low'
  if (val < 8) return 'score-mid'
  return 'score-high'
})

const currentPersonalRating = computed(() => {
  if (!showData.value) return null
  const local = statsStore.userShowRatings[showData.value.id]
  return local !== undefined ? local : showData.value.personal_rating
})

const formatSe = (season, episode) => {
  if (!season || !episode) return ''
  const epStr = episode < 10 ? `0${episode}` : `${episode}`
  return `S${season}E${epStr}`
}

const close = () => {
  uiStore.closeModal('details')
}

const loadShowData = async () => {
  if (!showId.value) return
  loading.value = true
  try {
    const data = await api.get(`show/${showId.value}/`)
    showData.value = data
  } catch (e) {
    uiStore.showToast('Ошибка загрузки данных рейтингов')
    close()
  } finally {
    loading.value = false
  }
}

const openRating = () => {
  if (!showData.value) return
  uiStore.openModal('rateShow', {
    showId: showData.value.id,
    title: showData.value.title,
    initialValue: currentPersonalRating.value,
    type: showData.value.type
  })
}

const getRatingClass = (val) => {
  if (!val) return ''
  if (val >= 8) return 'rating-high'
  if (val >= 6) return 'rating-mid'
  return 'rating-low'
}

watch(showId, (newId) => {
  if (newId) {
    showData.value = null
    loadShowData()
  }
}, { immediate: true })
</script>

<style scoped>
@import '../../../../kinopub_parser/static/css/rating.css';

.external-link-btn:hover {
  transform: scale(1.05);
  filter: brightness(1.1);
}
</style>