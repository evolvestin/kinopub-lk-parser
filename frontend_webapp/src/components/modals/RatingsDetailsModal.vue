<template>
  <div class="modal-overlay show" @click.self="close">
    <div class="modal-content" :class="[activeScoreColorClass, { 'voters-full-screen': showFullVoters }]" :style="{ padding: showFullVoters ? '16px' : '24px', height: modalHeight, minHeight: modalHeight, display: 'flex', flexDirection: 'column' }">
      
      <div class="modal-header-container" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-shrink: 0; width: 100%;">
        <template v-if="showFullVoters">
          <button class="tab clickable" @click="showFullVoters = false" style="margin: 0; padding: 8px 16px; color: var(--text-primary) !important; background: var(--bg-input); display: inline-flex; align-items: center; gap: 4px; border: none; font-size: 14px; font-weight: 700; border-radius: 12px;">
            <span v-html="icons.chevron_left"></span> Назад
          </button>
          <span style="font-size: 16px; font-weight: 800; color: var(--text-primary); margin-left: 12px; margin-right: auto; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            Все оценившие ({{ totalVotesCount }})
          </span>
        </template>
        <template v-else>
          <div style="font-size: 12px; font-weight: 900; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px;">
            Рейтинги и оценки
          </div>
        </template>
        <button class="modal-close" @click="close">×</button>
      </div>

      <div class="show-title" :style="showFullVoters ? { marginBottom: '12px', fontSize: '16px' } : { marginBottom: '16px', fontSize: '20px' }" style="font-weight: 900; color: var(--text-primary); text-align: center; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.2; word-break: break-word;">
        {{ showData?.title || 'Загрузка...' }}
      </div>

      <div v-if="showData && availableTabsCount > 1 && !showFullVoters" class="view-toggle" style="margin-bottom: 20px; flex-shrink: 0; padding: 3px; background: var(--bg-input);">
        <button v-if="hasKp" class="vt-btn" :class="{ active: ratingType === 'kp' }" style="flex: 1;" @click="ratingType = 'kp'">Кинопоиск</button>
        <button v-if="hasImdb" class="vt-btn" :class="{ active: ratingType === 'imdb' }" style="flex: 1;" @click="ratingType = 'imdb'">IMDb</button>
        <button v-if="hasLr" class="vt-btn" :class="{ active: ratingType === 'lr' }" style="flex: 1;" @click="ratingType = 'lr'">LocalRating (LR)</button>
      </div>

      <div style="flex: 1; display: flex; flex-direction: column; min-height: 0; overflow-x: hidden;" :style="{ overflowY: showFullVoters ? 'hidden' : 'auto' }" class="custom-scrollbar">
        <div v-if="loading" class="loader-inline">
          <div class="spinner"></div>
        </div>

        <div v-else-if="showData" :style="showFullVoters ? { display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 } : {}">
          <div v-if="ratingType === 'kp'" class="rate-container" style="padding: 0;">
            <div class="rate-score-display" style="margin-bottom: 10px; height: auto; padding: 15px 0; display: flex; align-items: center; justify-content: center; gap: 16px; position: relative;">
              <div class="rate-score-huge">
                {{ showData.kinopoisk_rating ? showData.kinopoisk_rating.toFixed(1) : '—' }}<span style="font-size: 16px;">/ 10</span>
              </div>
              <a v-if="showData.kinopoisk_url" :href="showData.kinopoisk_url" target="_blank" class="external-link-btn" style="color: #f15a24; background: rgba(241, 90, 36, 0.15); border: 1px solid rgba(241, 90, 36, 0.3); padding: 8px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; transition: all 0.2s; height: 38px; width: 38px; right: 6px;" title="Открыть на Кинопоиске">
                <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                  <polyline points="15 3 21 3 21 9"></polyline>
                  <line x1="10" y1="14" x2="21" y2="3"></line>
                </svg>
              </a>
              <a v-else :href="'https://www.kinopoisk.ru/index.php?kp_query=' + encodeURIComponent(showData.title)" target="_blank" class="external-link-btn" style="color: #f15a24; background: rgba(241, 90, 36, 0.15); border: 1px solid rgba(241, 90, 36, 0.3); padding: 8px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; transition: all 0.2s; height: 38px; width: 38px; right: 6px;" title="Найти на Кинопоиске">
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
                  <span style="color: var(--text-primary); font-weight: 800;">{{ showData.ext_rating.film_critics.toFixed(1) }} / 10</span>
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
              <a v-if="showData.imdb_url" :href="showData.imdb_url" target="_blank" class="external-link-btn" style="color: #f5c518; background: rgba(245, 197, 24, 0.15); border: 1px solid rgba(245, 197, 24, 0.3); padding: 8px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; transition: all 0.2s; height: 38px; width: 38px; right: 6px;" title="Открыть на IMDb">
                <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                  <polyline points="15 3 21 3 21 9"></polyline>
                  <line x1="10" y1="14" x2="21" y2="3"></line>
                </svg>
              </a>
              <a v-else :href="'https://www.imdb.com/find?q=' + encodeURIComponent(showData.original_title || showData.title)" target="_blank" class="external-link-btn" style="color: #f5c518; background: rgba(245, 197, 24, 0.15); border: 1px solid rgba(245, 197, 24, 0.3); padding: 8px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; transition: all 0.2s; height: 38px; width: 38px; right: 6px;" title="Найти на IMDb">
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

          <div v-else-if="ratingType === 'lr'" class="rate-container" :style="showFullVoters ? { display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, padding: 0, alignItems: 'stretch', width: '100%' } : { padding: 0, alignItems: 'stretch', width: '100%' }">
            <template v-if="!showFullVoters">
              <div class="rate-score-display" style="margin-bottom: 10px; height: auto; padding: 15px 0; align-self: center;">
                <div class="rate-score-huge">
                  {{ showData.internal_rating ? showData.internal_rating.toFixed(1) : '—' }}<span style="font-size: 16px; color: var(--text-muted);">/ 10</span>
                </div>
              </div>

              <div style="text-align: center; font-size: 14px; color: var(--text-secondary); margin-bottom: 12px; font-weight: 600; display: flex; flex-direction: column; gap: 4px; align-items: center; justify-content: center;">
                <div>Проголосовало участников: <span style="color: var(--text-primary); font-weight: 800;">{{ totalVotesCount }}</span></div>
                <div v-if="isSeries && showData.total_ratings_count">Общее количество оценок: <span style="color: var(--text-primary); font-weight: 800;">{{ showData.total_ratings_count }}</span></div>
              </div>

              <div style="font-size: 11px; color: var(--text-muted); line-height: 1.4; text-align: center; background: var(--bg-input); padding: 10px 14px; border-radius: 12px; margin-bottom: 12px; border: 1px dashed var(--border);">
                Локальный рейтинг (LocalRating) рассчитывается на основе оценок всех пользователей бота, которые оценили данное шоу.
              </div>

              <button v-if="totalVotesCount > 0" class="btn-primary" style="margin-top: 8px; background: var(--bg-input); color: var(--text-primary); border: 1px solid var(--border); box-shadow: none;" @click="openFullVotersList">
                👥 Показать всех оценивших ({{ totalVotesCount }})
              </button>
            </template>

            <template v-else>
              <div style="display: flex; flex-direction: column; gap: 12px; width: 100%; flex: 1; min-height: 0; overflow-y: auto; padding-right: 4px;" class="custom-scrollbar" ref="votersListContainer">
                <div v-for="ur in fullVotersList" :key="ur.user" style="display: flex; flex-direction: column; gap: 8px; padding: 14px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px; text-align: left; width: 100%;">
                  <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                    <span style="font-size: 14px; font-weight: 800; color: var(--text-primary);">
                      {{ ur.user_name || ur.user }}
                      <template v-if="ur.user_username">
                        (<a href="#" @click.prevent="openTelegramLink('https://t.me/' + ur.user_username)" class="shared-banner-link">@{{ ur.user_username }}</a>)
                      </template>
                    </span>
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

                <div v-if="fullVotersLoading" class="loader-inline" style="padding: 15px;">
                  <div class="spinner" style="width: 24px; height: 24px;"></div>
                </div>

                <div ref="votersSentinel" style="height: 20px; width: 100%; grid-column: 1/-1;"></div>
              </div>
            </template>
          </div>
        </div>
      </div>

      <div v-if="showData && !showFullVoters" style="display: flex; gap: 12px; margin-top: 16px; flex-shrink: 0; width: 100%;">
        <button class="btn-primary" style="margin: 0;" @click="openRating">
          🌟 Оценить
        </button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch, nextTick, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUIStore } from '../../stores/uiStore'
import { useStatsStore } from '../../stores/useStatsStore'
import { useApi } from '../../composables/useApi'
import { useTelegram } from '../../composables/useTelegram'
import { icons } from '../../utils/icons'
import { getRatingClass } from '../../utils/helpers'

const uiStore = useUIStore()
const statsStore = useStatsStore()
const api = useApi()
const router = useRouter()
const { tg, showConfirm } = useTelegram()

const showData = ref(null)
const loading = ref(true)

const showFullVoters = ref(false)
const fullVotersList = ref([])
const fullVotersLoading = ref(false)
const fullVotersHasMore = ref(true)
const fullVotersOffset = ref(0)
const votersSentinel = ref(null)
const votersListContainer = ref(null)
let votersObserver = null

const openTelegramLink = (url) => {
  showConfirm('Переход в профиль Telegram может свернуть текущее мини-приложение. Продолжить?', (ok) => {
    if (ok) {
      if (tg && typeof tg.openTelegramLink === 'function') {
        tg.openTelegramLink(url)
      } else {
        window.open(url, '_blank')
      }
    }
  })
}

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

const totalVotesCount = computed(() => {
  return showData.value ? (showData.value.total_voters_count || showData.value.user_ratings?.length || 0) : 0
})

const recentVoters = computed(() => {
  return showData.value ? (showData.value.user_ratings_details || []) : []
})

const formatSe = (season, episode) => {
  if (!season || !episode) return ''
  const epStr = episode < 10 ? `0${episode}` : `${episode}`
  return `S${season}E${epStr}`
}

const close = () => {
  uiStore.closeModal('details')
}

const hasKp = computed(() => {
  return showData.value && (showData.value.kinopoisk_rating !== null || !!showData.value.kinopoisk_url)
})

const hasImdb = computed(() => {
  return showData.value && (showData.value.imdb_rating !== null || !!showData.value.imdb_url)
})

const hasLr = computed(() => {
  return showData.value && (showData.value.internal_rating !== null || showData.value.user_ratings?.length > 0)
})

const availableTabsCount = computed(() => {
  let count = 0
  if (hasKp.value) count++
  if (hasImdb.value) count++
  if (hasLr.value) count++
  return count
})

const selectDefaultTab = () => {
  if (!showData.value) return
  
  if (ratingType.value === 'kp' && !hasKp.value) {
    if (hasImdb.value) ratingType.value = 'imdb'
    else if (hasLr.value) ratingType.value = 'lr'
  } else if (ratingType.value === 'imdb' && !hasImdb.value) {
    if (hasKp.value) ratingType.value = 'kp'
    else if (hasLr.value) ratingType.value = 'lr'
  } else if (ratingType.value === 'lr' && !hasLr.value) {
    if (hasKp.value) ratingType.value = 'kp'
    else if (hasImdb.value) ratingType.value = 'imdb'
  }
}

const loadShowData = async () => {
  if (!showId.value) return
  
  if (uiStore.showsCache[showId.value]) {
    showData.value = uiStore.showsCache[showId.value]
    loading.value = false
    return
  }

  loading.value = true
  try {
    const data = await api.get(`show/${showId.value}/`)
    showData.value = data
    uiStore.showsCache[showId.value] = data
  } catch (e) {
    uiStore.showToast('Ошибка загрузки данных рейтингов')
    close()
  } finally {
    loading.value = false
  }
}

const loadFullVoters = async (isLoadMore = false) => {
  if (fullVotersLoading.value) return
  if (!isLoadMore) {
    fullVotersOffset.value = 0
    fullVotersList.value = []
    fullVotersHasMore.value = true
  }
  fullVotersLoading.value = true
  try {
    const data = await api.post(`show/${showId.value}/ratings_paginated/`, {
      offset: fullVotersOffset.value,
      limit: 20,
      shared_id: router.currentRoute.value.query.shared_id || null
    })
    if (isLoadMore) {
      fullVotersList.value.push(...(data.ratings || []))
    } else {
      fullVotersList.value = data.ratings || []
    }
    fullVotersHasMore.value = data.has_more
  } catch (e) {
    uiStore.showToast('Ошибка загрузки оценок')
  } finally {
    fullVotersLoading.value = false
  }
}

const setupVotersObserver = () => {
  if (votersObserver) votersObserver.disconnect()
  votersObserver = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && fullVotersHasMore.value && !fullVotersLoading.value) {
      fullVotersOffset.value += 20
      loadFullVoters(true)
    }
  }, {
    root: votersListContainer.value,
    rootMargin: '200px'
  })
  if (votersSentinel.value) {
    votersObserver.observe(votersSentinel.value)
  }
}

const openFullVotersList = async () => {
  showFullVoters.value = true
  await loadFullVoters()
  nextTick(setupVotersObserver)
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

const modalHeight = computed(() => {
  if (loading.value || !showData.value) {
    return '300px'
  }
  if (showFullVoters.value) {
    return '100vh'
  }

  let staticHeight = 220
  if (statsStore.isShared) {
    staticHeight += 80
  }
  if (availableTabsCount.value > 1) {
    staticHeight += 44
  }

  let criticsHeight = 0
  if (showData.value.ext_rating) {
    let rowsCount = 0
    if (showData.value.ext_rating.film_critics !== null) rowsCount++
    if (showData.value.ext_rating.russian_film_critics !== null) rowsCount++
    if (showData.value.ext_rating.await_rating !== null) rowsCount++
    if (showData.value.ext_rating.tmdb !== null) rowsCount++
    
    if (rowsCount > 0) {
      criticsHeight = 52 + (rowsCount * 20) + ((rowsCount - 1) * 10)
    }
  }

  const kpContentHeight = 110 + (showData.value.kinopoisk_votes ? 30 : 0) + criticsHeight
  const imdbContentHeight = 110 + (showData.value.imdb_votes ? 30 : 0)
  const lrContentHeight = 110 + 55 + 85 + (totalVotesCount.value > 0 ? 64 : 0)

  const kpHeight = hasKp.value ? (staticHeight + kpContentHeight) : 0
  const imdbHeight = hasImdb.value ? (staticHeight + imdbContentHeight) : 0
  const lrHeight = hasLr.value ? (staticHeight + lrContentHeight) : 0

  const maxCalculated = Math.max(kpHeight, imdbHeight, lrHeight)
  const maxHeightLimit = Math.min(600, Math.floor(window.innerHeight * 0.95))
  const finalHeight = Math.max(380, Math.min(maxCalculated, maxHeightLimit))

  return `${finalHeight}px`
})

onUnmounted(() => {
  if (votersObserver) votersObserver.disconnect()
})

watch(showId, (newId) => {
  if (newId) {
    showData.value = null
    showFullVoters.value = false
    if (votersObserver) votersObserver.disconnect()
    loadShowData()
  }
}, { immediate: true })

watch(showData, () => {
  selectDefaultTab()
})

watch(ratingType, () => {
  showFullVoters.value = false
  if (votersObserver) votersObserver.disconnect()
})
</script>

<style scoped>
@import '../../../../kinopub_parser/static/css/rating.css';

.modal-content {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              width 0.35s cubic-bezier(0.4, 0, 0.2, 1),
              max-width 0.35s cubic-bezier(0.4, 0, 0.2, 1),
              height 0.35s cubic-bezier(0.4, 0, 0.2, 1),
              max-height 0.35s cubic-bezier(0.4, 0, 0.2, 1),
              border-radius 0.35s cubic-bezier(0.4, 0, 0.2, 1),
              margin 0.35s cubic-bezier(0.4, 0, 0.2, 1),
              padding 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.voters-full-screen {
  width: 100vw !important;
  max-width: 100vw !important;
  height: 100vh !important;
  max-height: 100vh !important;
  border-radius: 0 !important;
  margin: 0 !important;
  border: none !important;
  padding: 16px !important;
  padding-top: calc(16px + env(safe-area-inset-top)) !important;
  padding-bottom: calc(16px + env(safe-area-inset-bottom)) !important;
}

.external-link-btn:hover {
  transform: scale(1.05);
  filter: brightness(1.1);
}
</style>