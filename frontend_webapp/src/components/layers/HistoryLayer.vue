<template>
  <div class="layer-content" @scroll="handleScroll">
    <div class="layer-header" id="layer-header-node" :class="{ 'has-group': !!stickyLabel }">
      <div style="flex-shrink: 0;">
        <button class="tab clickable header-back-btn" @click="uiStore.popLayer">
          <span v-html="icons.chevron_left"></span> Назад
        </button>
      </div>
      <div class="layer-header-center">
        <div class="layer-title-main" ref="titleEl">{{ displayTitle }}</div>
        <div class="layer-group-label" id="sticky-group-text">{{ stickyLabel }}</div>
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

    <div 
      class="hist-container" 
      :class="[viewMode === 'grid' ? 'hist-grid' : 'card-list-wrapper', { 'history-edit-mode': uiStore.isHistoryEditMode }]" 
      style="padding: 16px;" 
      id="layer-hist-container"
    >
      <template v-for="(item, idx) in visibleList" :key="item.id || `hist-${idx}`">
        <div v-if="shouldShowDivider(item, idx)" class="hist-group-divider anim-item" :data-label="getGroupKey(item)">
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
      
      <div v-if="!items.length && !statsStore.isLoading" class="empty" style="grid-column: 1 / -1;">
        <div class="icon" v-html="icons.dash"></div> Нет данных
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useUIStore } from '../../stores/uiStore'
import { useStatsStore } from '../../stores/useStatsStore'
import { icons } from '../../utils/icons'
import ShowCard from '../shared/ShowCard.vue'

const props = defineProps(['historyId'])
const route = useRoute()
const uiStore = useUIStore()
const statsStore = useStatsStore()

const viewMode = ref(localStorage.getItem('kp_view_mode') || 'grid')
const offset = ref(80)
const sentinelEl = ref(null)
const titleEl = ref(null)
const stickyLabel = ref('')

const isShared = computed(() => !!route.query.shared_id || window.location.hash.includes('shared_id'))
const canEdit = computed(() => !isShared.value && props.historyId !== 'ratings')

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
  const titles = { 
    all: 'Вся история', 
    movies: 'Фильмы', 
    episodes: 'Эпизоды', 
    ratings: 'Все оценки', 
    wishlist_watched: 'Из избранного',
    casino: 'История рулетки'
  }
  return titles[props.historyId] || 'История'
})

const visibleList = computed(() => items.value.slice(0, offset.value))

const RU_MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]

const getGroupKey = (item) => {
  const dateStr = item.view_date || item.date || ''
  if (!dateStr) return ''
  const dateObj = new Date(dateStr)
  if (isNaN(dateObj.getTime())) return ''
  
  if (items.value.length >= 300) {
    return RU_MONTHS[dateObj.getMonth()] + ' ' + dateObj.getFullYear()
  }
  return String(dateObj.getFullYear())
}

const shouldShowDivider = (item, idx) => {
  if (idx === 0) return true
  const currentKey = getGroupKey(item)
  const prevKey = getGroupKey(visibleList.value[idx - 1])
  return currentKey !== prevKey
}

const handleScroll = (e) => {
    const dividers = Array.from(e.target.querySelectorAll('.hist-group-divider'))
    const headerHeight = 64
    const scrollTop = e.target.scrollTop
    let activeDivider = null

    for (let i = dividers.length - 1; i >= 0; i--) {
        if (dividers[i].offsetTop <= scrollTop + headerHeight + 5) {
            activeDivider = dividers[i]
            break
        }
    }
    stickyLabel.value = activeDivider ? activeDivider.dataset.label : ''
}

onMounted(() => {
  const obs = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && offset.value < items.value.length) {
      offset.value += 40
    }
  }, { rootMargin: '1000px' })
  
  if (sentinelEl.value) obs.observe(sentinelEl.value)
  
  nextTick(() => {
    if (titleEl.value) uiStore.fitText(titleEl.value)
  })
})

watch(viewMode, (val) => localStorage.setItem('kp_view_mode', val))

watch(() => items.value.length, () => {
    nextTick(() => {
        const container = document.getElementById('layer-hist-container')
        if (container) uiStore.fitAll('.grid-below-title', container)
    })
})
</script>

<style scoped>
.header-back-btn {
    background: var(--bg-input) !important;
    color: var(--text-primary) !important;
    border: none !important;
    padding: 8px 12px !important;
}
.card-list-wrapper {
    display: flex;
    flex-direction: column;
    gap: 0;
    background: var(--bg-card);
    border-radius: var(--radius-lg);
    border: 1px solid var(--border);
    overflow: hidden;
}
</style>