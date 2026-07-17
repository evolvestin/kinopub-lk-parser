<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useDataStore } from '../stores/useDataStore'
import { useUIStore } from '../stores/uiStore'
import { useStatsStore } from '../stores/useStatsStore'
import { icons } from '../utils/icons'
import EmptyState from '../components/shared/EmptyState.vue'
import PersonPill from '../components/shared/PersonPill.vue'
import ShowCard from '../components/shared/ShowCard.vue'

const dataStore = useDataStore()
const uiStore = useUIStore()
const statsStore = useStatsStore()
const query = ref(dataStore.searchQuery)
const isAnimated = ref(true)
let timer = null

const isEmpty = computed(() => !dataStore.searchResults.shows?.length && !dataStore.searchResults.persons?.length)
const themeIcon = computed(() => uiStore.theme === 'dark' ? icons.moon : icons.sun)

const handleInput = () => {
  clearTimeout(timer)
  timer = setTimeout(() => {
    dataStore.searchQuery = query.value
  }, 500)
}

const setQuery = (q) => {
  query.value = q
  dataStore.searchQuery = q
}

watch(() => dataStore.searchResults.persons, () => {
  isAnimated.value = true
})

watch(() => dataStore.searchQuery, (newVal) => {
  if (query.value !== newVal) {
    query.value = newVal
  }
})

const resultsContainerEl = ref(null)
const sentinelEl = ref(null)
let observer = null

onMounted(() => {
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && dataStore.hasMoreShows) {
      dataStore.loadMore()
    }
  }, {
    root: resultsContainerEl.value,
    rootMargin: '400px'
  })

  if (sentinelEl.value) {
    observer.observe(sentinelEl.value)
  }
})

watch(sentinelEl, (newEl, oldEl) => {
  if (oldEl && observer) {
    observer.unobserve(oldEl)
  }
  if (newEl && observer) {
    observer.observe(newEl)
  }
})

onUnmounted(() => {
  if (observer) {
    observer.disconnect()
  }
})
</script>

<template>
  <div class="view active-view" id="view-search">
    <div id="search-results" ref="resultsContainerEl">
      <div v-if="dataStore.isSearching && isEmpty" class="empty">
        <div class="spinner"></div>
      </div>

      <template v-else>
        <div v-if="!dataStore.hasSearched" class="welcome-container">
          <div class="icon-wrap">🍿</div>
          <h2>Что будем смотреть?</h2>
          <p>Начните вводить название фильма, сериала или <b>имя актёра и режиссёра</b>, чтобы найти их и добавить в свою статистику.</p>
          
          <div class="qs-label">Попробуйте найти:</div>
          <div class="qs-chips">
            <button class="qs-chip" @click="setQuery('Во все тяжкие')">Во все тяжкие</button>
            <button class="qs-chip" @click="setQuery('Интерстеллар')">Интерстеллар</button>
            <button class="qs-chip" @click="setQuery('Кристофер Нолан')">Кристофер Нолан</button>
            <button class="qs-chip" @click="setQuery('Леонардо ДиКаприо')">ДиКаприо</button>
            <button class="qs-chip" @click="setQuery('Симпсоны')">Симпсоны</button>
          </div>
        </div>

        <EmptyState v-else-if="isEmpty" icon="dash" text="Ничего не найдено" />

        <div v-else class="search-content">
          <div v-if="dataStore.hasSearched && !uiStore.dismissedHints['search_results'] && (statsStore.currentStats?.summary?.total_views === 0)" class="onboarding-inline-banner" style="margin-top: 16px;">
            <div class="o-icon">👇</div>
            <div class="o-content">
              <div class="o-title">Отлично, мы нашли контент!</div>
              <div class="o-text">Нажмите на карточку фильма или персоны, чтобы открыть подробную информацию и начать собирать статистику.</div>
            </div>
            <button class="o-close" @click="uiStore.dismissHint('search_results')">×</button>
          </div>

          <div v-if="dataStore.searchResults.persons?.length">
            <div class="label"><div class="icon" style="color:#d29922" v-html="icons.users"></div>Люди</div>
            <div class="h-scroll-container" :class="{ 'anim-active': isAnimated }" @animationend="isAnimated = false">
              <PersonPill v-for="p in dataStore.searchResults.persons" :key="p.id" :person="p" />
            </div>
          </div>

          <div v-if="dataStore.searchResults.shows?.length" style="padding-top: 10px;">
            <div class="label"><div class="icon" style="color:var(--info)" v-html="icons.film"></div>Контент</div>
            <div class="hist-grid" style="padding: 0 16px;">
              <ShowCard v-for="s in dataStore.searchResults.shows" :key="s.id" :show="s" />
            </div>
          </div>
        </div>
      </template>

      <div v-if="dataStore.hasSearched && !isEmpty" ref="sentinelEl" style="height: 100px; width: 100%; margin-top: -50px; pointer-events: none;"></div>
    </div>

    <div class="search-bar-fixed">
      <div style="display: flex; gap: 12px; align-items: center; width: 100%;">
        <div style="position: relative; flex: 1;">
            <input type="text" 
                   v-model="query" 
                   class="search-input" 
                   style="width: 100%; padding-right: 40px;"
                   placeholder="Фильмы, сериалы, актеры..."
                   @input="handleInput">
            <div v-if="dataStore.isSearching && !isEmpty" class="spinner" style="position: absolute; right: 12px; top: 50%; margin-top: -10px; width: 20px; height: 20px; border-width: 2px;"></div>
        </div>
        <button class="theme-btn js-theme-toggle" @click="uiStore.toggleTheme" v-html="themeIcon"></button>
      </div>
    </div>
  </div>
</template>

<style scoped>
#view-search {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  padding-bottom: 0;
}
#search-results {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}
.search-content {
  padding-bottom: 24px;
}
.search-bar-fixed {
  position: relative;
  z-index: 90;
  padding: 14px 16px calc(14px + 64px + env(safe-area-inset-bottom));
  background: rgba(20, 24, 31, 0.75);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-top: 1px solid var(--border);
  transition: background 0.3s ease;
}
.light .search-bar-fixed {
  background: rgba(246, 248, 250, 0.75);
}
</style>