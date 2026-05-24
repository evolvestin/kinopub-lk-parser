<template>
  <div class="layer-content" @scroll="onScroll" ref="containerEl">
    <!-- Шапка слоя -->
    <div class="layer-header" id="layer-header-node" :class="{ 'has-group': showSticky }">
      <div style="flex-shrink: 0;">
        <button class="tab clickable header-back-btn" @click="uiStore.popLayer">
          <span v-html="icons.chevron_left"></span> Назад
        </button>
      </div>
      <div class="layer-header-center">
        <div class="layer-title-main" 
             :style="{ opacity: titleReady ? 1 : 0, transition: 'opacity 0.15s ease' }" 
             ref="titleEl">{{ displayTitle }}</div>
        <div class="layer-group-label" ref="stickyLabelEl" id="sticky-group-text">{{ stickyLabel }}</div>
      </div>
      <div style="display: flex; align-items: center; gap: 8px; flex-shrink: 0;">
         <button 
           v-if="canEdit"
           class="wl-edit-btn" 
           :style="uiStore.isHistoryEditMode ? 'background:var(--accent);color:#fff' : ''"
           @click="uiStore.isHistoryEditMode = !uiStore.isHistoryEditMode"
           v-html="icons.trash"
         ></button>

         <div class="view-toggle" style="margin: 0; padding: 2px;">
            <button class="vt-btn" :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'" v-html="icons.grid"></button>
            <button class="vt-btn" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'" v-html="icons.list"></button>
         </div>
      </div>
    </div>

    <!-- Карточка персоны (если открыто через фильтр по человеку) -->
    <div v-if="personInfo" 
         class="card anim-item clickable" 
         @click="uiStore.openLayer('person', personInfo.id)"
         style="display:flex; align-items:center; gap:16px; margin:12px 16px; padding:16px; border-radius:20px; position:relative;">
        <PersonAvatar 
          :photo-url="personInfo.photo_url" 
          :fallback-url="personInfo.fallback_photo_url"
          :name="personInfo.name"
          style="width:60px; height:60px;"
        />
        <div style="min-width:0; flex:1;">
            <div style="font-size:20px; font-weight:900; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; letter-spacing:-0.5px;">{{ personInfo.name }}</div>
            <div style="font-size:13px; color:var(--text-muted); font-weight:600; margin-top:4px; letter-spacing:0.3px;">{{ personInfo.professionLabel }}</div>
        </div>
        <div style="color:var(--text-muted); opacity:0.5;">
            <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none"><path d="M9 18l6-6-6-6"/></svg>
        </div>
    </div>

    <!-- Список элементов -->
    <div 
      class="hist-container" 
      :class="[viewMode === 'grid' ? 'hist-grid' : 'card-list-wrapper', { 'history-edit-mode': uiStore.isHistoryEditMode }]" 
      style="padding: 16px;" 
      id="layer-hist-container"
    >
      <template v-for="(item, idx) in visibleList" :key="item.id || `hist-${idx}`">
        <div 
          v-if="shouldShowDivider(item, idx)" 
          class="hist-group-divider anim-item js-group-divider" 
          :data-label="getGroupKey(item).toUpperCase()"
        >
           <span class="hist-group-divider-text">{{ getGroupKey(item) }}</span>
        </div>
        <ShowCard 
          :show="item" 
          :view-mode="viewMode" 
          context="history" 
          :history-id="props.historyId"
        />
      </template>
      
      <div ref="sentinelEl" id="layer-hist-sentinel" style="height: 100px; width: 100%; margin-top: -50px; pointer-events: none;"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useUIStore } from '../../stores/uiStore'
import { useStatsStore } from '../../stores/useStatsStore'
import { icons } from '../../utils/icons'
import ShowCard from '../shared/ShowCard.vue'
import PersonAvatar from '../shared/PersonAvatar.vue'

const props = defineProps(['historyId'])
const route = useRoute()
const uiStore = useUIStore()
const statsStore = useStatsStore()

const containerEl = ref(null)
const sentinelEl = ref(null)
const titleEl = ref(null)
const stickyLabelEl = ref(null)

const viewMode = ref(localStorage.getItem('kp_view_mode') || 'grid')
const offset = ref(80)
const stickyLabel = ref('')
const showSticky = ref(false)
const cachedOffsets = ref([])
const titleReady = ref(false)
let ticking = false

const isShared = computed(() => !!route.query.shared_id || window.location.hash.includes('shared_id'))
const canEdit = computed(() => !isShared.value && props.historyId !== 'ratings')

const personInfo = computed(() => {
  if (props.historyId !== 'filter' || !route.query.key || route.query.idx === null) return null
  const key = route.query.key
  const idx = parseInt(route.query.idx)
  const stats = statsStore.currentStats
  if (!stats) return null
  const keyParts = key.replace('group_', '').split('_')
  let personData = null
  if (keyParts.length === 2) personData = stats[keyParts[0]]?.[keyParts[1]]?.[idx]
  else personData = stats[keyParts[0]]?.[idx]
  if (!personData || !['actors', 'directors', 'writers'].some(p => key.includes(p))) return null
  let label = 'Профиль'; if (key.includes('actors')) label = 'Актёр'; else if (key.includes('directors')) label = 'Режиссёр'; else if (key.includes('writers')) label = 'Сценарист'
  return { ...personData, professionLabel: label }
})

const items = computed(() => {
  const params = { 
    date: route.query.date, 
    idx: route.query.idx ? parseInt(route.query.idx) : null, 
    key: route.query.key, 
    showId: route.query.show_id ? parseInt(route.query.show_id) : null 
  }
  return statsStore.getHistoryByType(props.historyId, params)
})

const displayTitle = computed(() => {
  if (route.query.title) return route.query.title
  const titles = { all: 'Вся история', movies: 'Фильмы', episodes: 'Эпизоды', ratings: 'Все оценки', wishlist_watched: 'Просмотрено из избранного', casino: 'История рулетки' }
  return titles[props.historyId] || 'История'
})

const visibleList = computed(() => items.value.slice(0, offset.value))

const RU_MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]

const getGroupKey = (item) => {
  const dateStr = item.view_date || item.date || ''
  if (!dateStr) return ''
  const dateObj = new Date(dateStr); if (isNaN(dateObj.getTime())) return ''
  if (items.value.length >= 300) return RU_MONTHS[dateObj.getMonth()] + ' ' + dateObj.getFullYear()
  return String(dateObj.getFullYear())
}

const shouldShowDivider = (item, idx) => {
  if (idx === 0) return true
  const currentKey = getGroupKey(item)
  const prevKey = getGroupKey(visibleList.value[idx - 1])
  return currentKey !== prevKey
}

const cacheDividerOffsets = () => {
  const container = containerEl.value
  if (!container) return
  
  requestAnimationFrame(() => {
    const dividers = container.querySelectorAll('.js-group-divider')
    const offsets = []
    dividers.forEach(div => {
      offsets.push({
        top: div.offsetTop,
        label: div.dataset.label
      })
    })
    cachedOffsets.value = offsets
    updateStickyState()
  })
}

const updateStickyState = () => {
  const container = containerEl.value
  if (!container) return

  const scrollTop = container.scrollTop
  const headerHeight = 64 

  let activeDivider = null
  const offsets = cachedOffsets.value

  for (let i = 0; i < offsets.length; i++) {
    if (offsets[i].top <= scrollTop + headerHeight + 5) {
      activeDivider = offsets[i]
    } else {
      break
    }
  }

  if (activeDivider) {
    const label = activeDivider.label
    if (stickyLabel.value !== label) {
      stickyLabel.value = label
    }
    showSticky.value = true
  } else {
    showSticky.value = false
  }
  
  ticking = false
}

const onScroll = () => {
  if (!ticking) {
    requestAnimationFrame(updateStickyState)
    ticking = true
  }
}

const checkAndFetchAdditionalData = async () => {
  if (props.historyId === 'casino') {
    uiStore.setLoading(true)
    await statsStore.fetchCasinoHistory()
    uiStore.setLoading(false)
    nextTick(() => {
      cacheDividerOffsets()
    })
  }
}

let observer = null

onMounted(() => {
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && offset.value < items.value.length) {
      offset.value += 40
    }
  }, { rootMargin: '1000px' })
  
  if (sentinelEl.value) observer.observe(sentinelEl.value)
  
  nextTick(() => {
    if (titleEl.value) uiStore.fitText(titleEl.value)
    titleReady.value = true
    cacheDividerOffsets()
  })
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})

watch([viewMode, visibleList], () => {
  cacheDividerOffsets()
})

watch(
  [() => statsStore.currentStats, () => props.historyId],
  async ([newStats]) => {
    if (newStats) {
      await checkAndFetchAdditionalData()
    }
  },
  { immediate: true }
)
</script>