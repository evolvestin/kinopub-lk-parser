<template>
  <div class="view active-view" style="display: flex; flex-direction: column;">
    <div id="search-results" style="flex: 1; display: flex; flex-direction: column; overflow-y: auto; padding-bottom: 24px;">
      
      <div v-if="dataStore.isSearching" class="loader-inline">
        <div class="spinner" style="width: 32px; height: 32px; border-width: 3px;"></div>
      </div>

      <template v-else>
        <EmptyState 
          v-if="!dataStore.hasSearched" 
          icon="search" 
          text="Введите название для поиска" 
          style="flex: 1;" 
        />
        
        <EmptyState 
          v-else-if="isEmptyResult" 
          icon="dash" 
          text="Ничего не найдено" 
          style="flex: 1;" 
        />

        <template v-else>
          <div v-if="dataStore.searchResults.persons?.length">
            <div class="label">
              <div class="icon" style="color: #d29922;" v-html="icons.users"></div>
              Люди
            </div>
            <div class="h-scroll-container" style="padding-bottom: 16px;">
              <PersonPill 
                v-for="person in dataStore.searchResults.persons" 
                :key="person.id" 
                :person="person" 
              />
            </div>
          </div>

          <div v-if="dataStore.searchResults.shows?.length">
            <div class="label">
              <div class="icon" style="color: var(--info);" v-html="icons.film"></div>
              Контент
            </div>
            <div class="hist-grid" style="padding: 0 16px;">
              <ShowCard 
                v-for="show in dataStore.searchResults.shows" 
                :key="show.id" 
                :show="show" 
              />
            </div>
          </div>
        </template>
      </template>

    </div>

    <div class="search-container" style="display: flex; gap: 12px; align-items: center;">
      <input 
        type="text" 
        v-model="dataStore.searchQuery" 
        class="search-input" 
        style="flex: 1;" 
        placeholder="Фильмы, сериалы, актеры..."
      >
      <button class="theme-btn" @click="uiStore.toggleTheme">
        <span v-html="themeIcon"></span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useDataStore } from '../stores/useDataStore'
import { useUIStore } from '../stores/uiStore'
import { icons } from '../utils/icons'
import EmptyState from '../components/shared/EmptyState.vue'
import PersonPill from '../components/shared/PersonPill.vue'
import ShowCard from '../components/shared/ShowCard.vue'

const dataStore = useDataStore()
const uiStore = useUIStore()

const themeIcon = computed(() => uiStore.theme === 'dark' ? icons.moon : icons.sun)
const isEmptyResult = computed(() => {
  return dataStore.hasSearched && 
         !dataStore.searchResults.shows?.length && 
         !dataStore.searchResults.persons?.length
})

let searchTimeout = null

watch(() => dataStore.searchQuery, (newQuery) => {
  clearTimeout(searchTimeout)
  
  if (newQuery.length < 2) {
    dataStore.clearSearch()
    return
  }

  searchTimeout = setTimeout(() => {
    dataStore.performSearch(newQuery)
  }, 400)
})
</script>