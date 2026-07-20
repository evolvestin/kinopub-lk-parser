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
            <span v-if="currentPersonalRating" class="rating-badge" :class="getRatingClass(currentPersonalRating)" style="font-size: 20px; padding: 4px 10px; border-radius: 10px; gap: 5px; display: inline-flex; align-items: center; font-weight: 800; text-shadow: none;">
              <span v-html="icons.star" style="font-size: 20px; display: inline-flex; align-items: center;"></span>{{ currentPersonalRating }}
            </span>
          </div>
        </div>

        <button class="detail-wishlist-btn anim-item" style="position: relative; animation-delay: 0s;" @click="openWishlistModal">
          <span v-html="icons.bookmark_plus"></span>
          <div v-if="showWishlistGuide" class="guide-tooltip-left wishlist-guide">В избранное</div>
        </button>
        <button class="detail-add-view-btn anim-item" style="position: relative; animation-delay: 0.1s;" @click="openAddView()">
          <span v-html="icons.eye"></span>
          <div v-if="showViewGuide" class="guide-tooltip-left view-guide">Отметить просмотр</div>
        </button>
        <button class="detail-rate-btn anim-item" style="position: relative; animation-delay: 0.2s;" @click="openRating">
          <span v-html="icons.star"></span>
          <div v-if="showRateGuide" class="guide-tooltip-left rate-guide">Поставить оценку</div>
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
        <div v-if="show.year" class="sm-tag clickable" @click="uiStore.openLayer('year', show.year)">{{ show.year }}</div>
        <div v-if="show.type" class="sm-tag clickable" style="color:var(--info)" @click="uiStore.openLayer('show_type', show.type)">{{ showTypeRu }}</div>
        <div v-if="show.status" class="sm-tag clickable" @click="uiStore.openLayer('status', show.status)">{{ showStatusRu }}</div>
      </div>

      <div class="show-meta-tags">
        <div v-if="show.kinopoisk_rating" class="sm-tag clickable" style="background:rgba(241, 90, 36, 0.15); color:#f15a24; border:none" @click="openRatingsDetails('kp')">KP {{ show.kinopoisk_rating }}</div>
        <div v-if="show.imdb_rating" class="sm-tag clickable" style="background:rgba(245, 197, 24, 0.15); color:#f5c518; border:none" @click="openRatingsDetails('imdb')">IMDb {{ show.imdb_rating }}</div>
        <div v-if="show.internal_rating" class="sm-tag clickable" style="background:var(--accent-dim); color:var(--accent); border:none" @click="openRatingsDetails('lr')">★ {{ show.internal_rating.toFixed(1) }}</div>
      </div>

      <div v-if="lastViewDisplay" style="display: flex; justify-content: center; margin-top: 12px; margin-bottom: 4px; animation: fadeInUp 0.5s ease-out 0.35s both;">
        <div class="clickable" style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: var(--text-muted); background: var(--bg-input); padding: 6px 16px; border-radius: 100px; transition: all 0.2s;" @click="openShowHistory">
          <span v-html="icons.clock" style="display: flex; width: 14px; height: 14px; opacity: 0.8;"></span> 
          Последний просмотр: <span style="color: var(--text-primary); font-weight: 800;">{{ lastViewDisplay }}</span>
        </div>
      </div>
    </div>

    <div class="plot-box" v-if="show.plot">{{ show.plot }}</div>

    <div v-if="!isSeries && (show.total_duration || lastViewDisplay)" style="margin-bottom: 24px; animation: fadeInUp 0.5s ease-out 0.5s both;">
      <div class="label">
        <div class="icon" style="color:var(--info)" v-html="icons.film"></div> Информация
      </div>
      
      <div style="padding: 0 20px;">
        <div class="ep-badge clickable" 
             :class="{ 'watched': isAllEpisodesWatched }"
             @click="handleMovieBlockClick"
             style="display: flex; flex-direction: row; justify-content: space-between; padding: 14px 18px; align-items: center; min-height: 58px; width: 100%; cursor: pointer; border-radius: 16px; background: var(--bg-card); border: 1px solid var(--border); box-shadow: var(--shadow-sm); transition: all 0.2s ease;">
          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="display: flex; flex-direction: column; align-items: flex-start; gap: 4px;">
              <div v-if="show.total_duration" class="ep-dur" style="font-size: 15px; font-weight: 800; color: var(--text-primary); display: flex; align-items: center; gap: 6px;">
                <span v-html="icons.time" style="width: 18px; height: 18px; color: var(--info); display: flex; align-items: center;"></span>
                {{ formatEpisodeDuration(show.total_duration) }}
              </div>
              <div v-else style="font-size: 14px; font-weight: 700; color: var(--text-secondary);">Информация о фильме</div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 12px;">
             <div v-if="isAllEpisodesWatched" style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: var(--accent); display: flex; align-items: center; gap: 4px; background: var(--accent-dim); padding: 4px 10px; border-radius: 8px; border: 1px solid rgba(46, 204, 113, 0.2);">
                <span v-html="icons.check" style="width: 14px; height: 14px; display: flex; align-items: center;"></span> Просмотрено
             </div>
             <div v-else style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: var(--text-muted); display: flex; align-items: center; gap: 4px; background: var(--bg-input); padding: 4px 10px; border-radius: 8px; border: 1px solid var(--border);">
                <span v-html="icons.eye" style="width: 14px; height: 14px; display: flex; align-items: center; opacity: 0.5;"></span> Просмотрено?
             </div>

             <div v-if="viewerRating" class="ep-rating clickable" style="font-size: 12px; padding: 4px 8px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 4px; background: rgba(0,0,0,0.2);" @click.stop="openRating">
                <span v-html="icons.star" style="color: #f1c40f; width: 12px; height: 12px; display: flex; align-items: center;"></span>
                {{ viewerRating }}
             </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="seasonsData.length > 0" style="margin-bottom: 24px; animation: fadeInUp 0.5s ease-out 0.5s both;">
      <div class="label" style="justify-content: space-between; align-items: center;">
        <div style="display:flex; align-items:center; gap:8px;">
            <div class="icon" style="color:var(--info)" v-html="icons.list"></div> Эпизоды
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          <div v-if="show.total_duration" 
               :style="isAllEpisodesWatched ? 'color:var(--accent); background:var(--accent-dim); border-color:var(--accent);' : 'color:var(--text-muted); background:var(--bg-input); border-color:var(--border);'"
               style="display:flex; align-items:center; gap:6px; font-size:11px; font-weight:800; padding:4px 10px; border-radius:12px; border: 1px solid; text-transform: uppercase;">
            <span v-html="isAllEpisodesWatched ? icons.check : icons.time" style="width:14px; height:14px; opacity:0.7; display:flex; align-items:center;"></span>
            Всего: {{ formatEpisodeDuration(show.total_duration) }}
          </div>
          <div v-if="activeSeasonTotalDuration" 
               :style="isActiveSeasonFullyWatched ? 'color:var(--accent); background:var(--accent-dim); border-color:var(--accent);' : 'color:var(--text-muted); background:var(--bg-input); border-color:var(--border);'"
               style="display:flex; align-items:center; gap:6px; font-size:11px; font-weight:800; padding:4px 10px; border-radius:12px; border: 1px solid; text-transform: uppercase;">
            <span v-html="isActiveSeasonFullyWatched ? icons.check : icons.time" style="width:14px; height:14px; opacity:0.7; display:flex; align-items:center;"></span>
            Сезон: {{ activeSeasonTotalDuration }}
          </div>
        </div>
      </div>
      
      <div v-if="seasonsData.length > 1" class="h-scroll-container" style="padding-bottom: 16px; gap: 8px;">
        <button 
          v-for="s in seasonsData" 
          :key="s.season_number"
          class="sm-tag clickable"
          :style="getSeasonButtonStyle(s)"
          @click="activeSeasonStr = s.season_number"
          style="border-radius: 12px; font-size: 14px; padding: 6px 14px; white-space: nowrap; outline: none; display: flex; align-items: center; gap: 4px;"
        >
          <span v-if="isSeasonFullyWatched(s)" v-html="icons.check" style="width: 14px; height: 14px; display: flex; align-items: center;"></span>
          Сезон {{ s.season_number }}
        </button>
      </div>

      <div style="padding: 0 20px; display: grid; grid-template-columns: repeat(auto-fill, minmax(64px, 1fr)); gap: 10px;">
        <div v-for="ep in activeSeasonEpisodes" :key="ep.episode_number" 
             class="ep-badge ep-grid-btn" 
             :class="{ 'watched': ep.watched }"
             @click="ep.watched ? openEpisodeModal(ep) : openAddView(activeSeasonStr, ep.episode_number)">
          <div class="ep-num">E{{ ep.episode_number }}</div>
          <div v-if="ep.duration" class="ep-dur">{{ Math.round(ep.duration / 60) }}м</div>
          <div v-if="ep.rating" class="ep-rating"><span v-html="icons.star"></span>{{ ep.rating }}</div>
        </div>
      </div>
    </div>

    <div v-if="show.genres?.length" style="margin-bottom: 24px; animation: fadeInUp 0.5s ease-out 0.6s both;">
      <div class="label">
        <div class="icon" style="color:var(--info)" v-html="icons.star"></div> Жанры
      </div>
      <div class="h-scroll-container" style="padding-bottom: 30px;">
        <div v-for="g in show.genres" :key="g.id" class="genre-pill" @click="uiStore.openLayer('genre', g.id)">
          {{ g.name }}
        </div>
      </div>
    </div>
    
    <template v-for="(group, idx) in show.crew" :key="group.profession">
      <div :style="{ animation: `fadeInUp 0.5s ease-out ${0.7 + idx * 0.1}s both` }">
        <div class="label">{{ group.profession }}</div>
        <div class="h-scroll-container">
           <PersonPill v-for="person in group.persons" :key="person.id" :person="person" />
        </div>
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
import { preloadImage, getRatingClass } from '../../utils/helpers'
import PersonPill from '../shared/PersonPill.vue'

const props = defineProps(['showId'])
const api = useApi()
const uiStore = useUIStore()
const statsStore = useStatsStore()

const show = ref(null)
const activePoster = ref('')
const activeBg = ref('')

const activeSeasonStr = ref(null)
const seasonsData = computed(() => {
  if (!show.value) return []
  return uiStore.episodesCache[props.showId] || []
})

watch(seasonsData, (newVal) => {
  if (newVal && newVal.length > 0 && !activeSeasonStr.value) {
    activeSeasonStr.value = newVal[0].season_number
  }
}, { immediate: true })

const activeSeasonEpisodes = computed(() => {
  if (!activeSeasonStr.value || !seasonsData.value) return []
  const s = seasonsData.value.find(x => x.season_number === activeSeasonStr.value)
  return s ? s.episodes : []
})

const activeSeasonTotalDuration = computed(() => {
  if (!activeSeasonEpisodes.value.length) return ''
  const totalSec = activeSeasonEpisodes.value.reduce((sum, ep) => sum + (ep.duration || 0), 0)
  return formatEpisodeDuration(totalSec)
})

const formatEpisodeDuration = (sec) => {
  if (!sec) return ''
  const totalM = Math.floor(sec / 60)
  const h = Math.floor(totalM / 60)
  const remM = totalM % 60
  if (h > 0) {
      if (remM > 0) return `${h}ч ${remM}м`
      return `${h}ч`
  }
  return `${totalM}м`
}

const showWishlistGuide = computed(() => statsStore.currentStats && statsStore.currentStats.summary?.wishlist_added === 0 && !uiStore.dismissedHints['wishlist_guide'])
const showViewGuide = computed(() => statsStore.currentStats && statsStore.currentStats.summary?.total_views === 0 && !uiStore.dismissedHints['view_guide'])
const showRateGuide = computed(() => statsStore.currentStats && statsStore.currentStats.ratings?.total === 0 && !uiStore.dismissedHints['rate_guide'])

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

const isSeries = computed(() => {
  return show.value && ['Series', 'Documentary Series', 'TV Show'].includes(show.value.type)
})

const isSeasonFullyWatched = (s) => {
  return s.episodes && s.episodes.length > 0 && s.episodes.every(e => e.watched)
}

const getSeasonButtonStyle = (s) => {
  const isActive = activeSeasonStr.value === s.season_number
  const isWatched = isSeasonFullyWatched(s)

  if (isActive) {
    return 'background: var(--accent); color: white; border-color: var(--accent);'
  }
  if (isWatched) {
    return 'background: var(--accent-dim); color: var(--accent); border-color: var(--accent);'
  }
  return 'background: var(--bg-input); color: var(--text-secondary); border-color: var(--border);'
}

const isAllEpisodesWatched = computed(() => {
  if (!show.value) return false
  if (!isSeries.value) return !!lastViewDisplay.value
  if (!seasonsData.value || seasonsData.value.length === 0) return false
  return seasonsData.value.every(s => s.episodes && s.episodes.length > 0 && s.episodes.every(e => e.watched))
})

const isActiveSeasonFullyWatched = computed(() => {
  if (!activeSeasonStr.value || !seasonsData.value) return false
  const activeS = seasonsData.value.find(x => x.season_number === activeSeasonStr.value)
  return activeS ? isSeasonFullyWatched(activeS) : false
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

const lastViewDisplay = computed(() => {
  if (!show.value) return null
  
  if (statsStore.isShared) {
    const D = statsStore.currentStats
    if (!D) return null
    const pool = [...(D.history_movies || []), ...(D.history_episodes || [])]
    const showHistory = pool.filter(i => i.show_id === show.value.id).sort((a, b) => b.view_date.localeCompare(a.view_date))
    if (showHistory.length > 0) {
      const myLast = showHistory[0]
      let se_suffix = ''
      if (myLast.season_number > 0) {
        const epStr = myLast.episode_number < 10 ? `0${myLast.episode_number}` : myLast.episode_number
        se_suffix = ` (s${myLast.season_number}e${epStr})`
      }
      return `${myLast.view_date}${se_suffix}`
    }
    return null
  }
  
  return show.value.last_view?.display || null
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
    if (isSeries.value) {
        const res = await api.post('get_episodes/', { show_id: props.showId })
        uiStore.episodesCache[props.showId] = res.seasons || []
    }
  }
})

watch(() => uiStore.modals.addView.isOpen, async (newVal, oldVal) => {
  if (oldVal === true && newVal === false) {
    await loadShowData()
    if (isSeries.value) {
        const res = await api.post('get_episodes/', { show_id: props.showId })
        uiStore.episodesCache[props.showId] = res.seasons || []
    }
    statsStore.fetchStats(statsStore.currentYear, true, true)
    statsStore.fetchStats('all', true, true)
  }
})

const openEpisodeModal = (ep) => {
  uiStore.openModal('rateShow', {
      showId: show.value.id,
      title: show.value.title,
      initialValue: ep.rating || null,
      type: show.value.type,
      level: 'score',
      season: activeSeasonStr.value,
      episode: ep.episode_number
  })
}

const handleMovieBlockClick = () => {
  if (isAllEpisodesWatched.value) {
    openRating()
  } else {
    openAddView()
  }
}

const openWishlistModal = () => {
  uiStore.dismissHint('wishlist_guide')
  uiStore.openModal('wlFolder', { showId: show.value.id, title: show.value.title })
}

const openRating = () => {
  uiStore.dismissHint('rate_guide')
  uiStore.openModal('rateShow', {
    showId: show.value.id,
    title: show.value.title,
    initialValue: viewerRating.value,
    type: show.value.type
  })
}

const openAddView = (seasonNum = null, episodeNum = null) => {
  const s = typeof seasonNum === 'number' || typeof seasonNum === 'string' ? seasonNum : null
  const e = typeof episodeNum === 'number' || typeof episodeNum === 'string' ? episodeNum : null
  uiStore.dismissHint('view_guide')
  uiStore.openModal('addView', { 
    showId: show.value.id, 
    title: show.value.title, 
    type: show.value.type,
    season: s,
    episode: e
  })
}

const openShowHistory = () => {
  uiStore.openLayer('history', 'show_history', { show_id: show.value.id, title: 'История просмотров' })
}

const openRatingsDetails = (ratingType) => {
  uiStore.openModal('details', { showId: props.showId, ratingType })
}
</script>

<style scoped>
.ep-badge {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 8px 4px;
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow-sm);
    min-height: 48px;
}
.ep-badge:active {
    transform: scale(0.92);
}
.ep-badge.watched {
    background: var(--accent-dim);
    border-color: var(--accent);
}
.ep-num {
    font-size: 14px;
    font-weight: 900;
    color: var(--text-primary);
    line-height: 1;
    margin-bottom: 2px;
}
.ep-badge.watched .ep-num {
    color: var(--accent);
}
.ep-dur {
    font-size: 10px;
    color: var(--text-muted);
    font-weight: 700;
    line-height: 1;
}
.ep-rating {
    font-size: 10px;
    font-weight: 800;
    color: #f1c40f;
    display: flex;
    align-items: center;
    gap: 2px;
    background: rgba(0,0,0,0.3);
    padding: 2px 6px;
    border-radius: 6px;
}
.ep-rating svg {
    width: 10px; height: 10px;
}
.ep-grid-btn {
    min-height: 58px;
    height: auto;
    padding: 4px !important;
}
</style>