<template>
  <div class="view active-view" id="view-search">
    <div id="search-results">
      <div v-if="dataStore.isSearching" class="loader-inline">
        <div class="spinner"></div>
      </div>

      <template v-else>
        <EmptyState v-if="!dataStore.hasSearched" icon="search" text="Введите название для поиска" />
        <EmptyState v-else-if="isEmpty" icon="dash" text="Ничего не найдено" />

        <div v-else class="search-content">
          <div v-if="dataStore.searchResults.persons?.length">
            <div class="label"><div class="icon" style="color:#d29922" v-html="icons.users"></div>Люди</div>
            <div class="h-scroll-container">
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
    </div>

    <div class="search-container">
      <div style="display: flex; gap: 12px; align-items: center; width: 100%;">
        <input type="text" 
               v-model="query" 
               class="search-input" 
               style="flex: 1;"
               placeholder="Фильмы, сериалы, актеры..."
               @input="handleInput">
        <button class="theme-btn js-theme-toggle" @click="uiStore.toggleTheme" v-html="themeIcon"></button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useDataStore } from '../stores/useDataStore'
import { useUIStore } from '../stores/uiStore'
import { icons } from '../utils/icons'
import EmptyState from '../components/shared/EmptyState.vue'
import PersonPill from '../components/shared/PersonPill.vue'
import ShowCard from '../components/shared/ShowCard.vue'

const dataStore = useDataStore()
const uiStore = useUIStore()
const query = ref(dataStore.searchQuery)
let timer = null

const isEmpty = computed(() => !dataStore.searchResults.shows?.length && !dataStore.searchResults.persons?.length)
const themeIcon = computed(() => uiStore.theme === 'dark' ? icons.moon : icons.sun)

const handleInput = () => {
  clearTimeout(timer)
  dataStore.searchQuery = query.value
  if (query.value.length < 2) {
    dataStore.clearSearch()
    return
  }
  timer = setTimeout(() => {
    dataStore.performSearch(query.value)
  }, 500)
}

watch(() => dataStore.searchQuery, (newVal) => {
  query.value = newVal
})
</script>

<style scoped>
#view-search {
  display: flex;
  flex-direction: column;
  height: 100%;
}
#search-results {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 20px;
}
.search-container {
  flex-shrink: 0;
}
</style>