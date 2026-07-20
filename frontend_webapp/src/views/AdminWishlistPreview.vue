<template>
  <div v-if="loading" class="loader-inline">
    <div class="spinner"></div>
  </div>

  <div v-else-if="error" class="empty">
    <div class="icon" v-html="icons.frown"></div>
    {{ error }}
  </div>

  <div v-else-if="folder" id="wl-active-folder-content">
    <div class="wl-active-header">
      <div id="wl-active-folder-title">
        <span :style="{ color: folder.color, marginRight: '8px' }" v-html="icons[folder.icon] || icons.folder" style="display: inline-flex; align-items: center;"></span>
        <span class="wl-active-folder-name-text">{{ folder.name }}</span>
      </div>
      
      <div style="display: flex; gap: 6px; align-items: center; margin-left: auto; flex-shrink: 0;">
        <div class="sort-dropdown-container">
          <button type="button" class="sort-trigger-btn" @click="toggleSortDropdown">
            <span class="sort-icon-main" :class="arrowClass" v-html="sortIcon"></span>
            <span class="sort-text-label">{{ sortLabel }}</span>
            <span class="sort-chevron" v-html="icons.chevron_down"></span>
          </button>
          <div class="sort-dropdown-menu" :class="{ show: isSortMenuOpen }">
            <div class="sort-item" :class="{ active: sortMode === 'default' }" @click="setSort('default')">
              <span class="icon-box" v-html="icons.reorder"></span>
              <span>Порядок</span>
            </div>
            <div class="sort-item" :class="{ active: sortMode.startsWith('added') }" @click="setSort('added')">
              <span class="sort-arrow-icon" :class="{ 'rotate-180': sortMode === 'added_asc' }" v-html="icons.sort_arrow"></span>
              <span>Добавлен</span>
            </div>
            <div class="sort-item" :class="{ active: sortMode.startsWith('year') }" @click="setSort('year')">
              <span class="sort-arrow-icon" :class="{ 'rotate-180': sortMode === 'year_asc' }" v-html="icons.sort_arrow"></span>
              <span>Год</span>
            </div>
          </div>
        </div>

        <div class="view-toggle" style="margin: 0; padding: 2px; display: flex; background: var(--bg-input);">
          <button type="button" class="vt-btn" :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'" v-html="icons.grid"></button>
          <button type="button" class="vt-btn" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'" v-html="icons.list"></button>
        </div>
      </div>
    </div>

    <div id="wl-items-container" style="padding: 16px;">
      <div v-if="!folder.items || !folder.items.length" class="empty">
        <div class="icon" v-html="icons.film"></div> Папка пуста
      </div>
      <div v-else :class="viewMode === 'list' ? 'card-list-wrapper' : 'hist-grid'">
        <ShowCard 
          v-for="item in sortedItems" 
          :key="item.id" 
          :show="item"
          :view-mode="viewMode"
          context="wishlist"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { icons } from '../utils/icons'
import ShowCard from '../components/shared/ShowCard.vue'

const folderId = window.FOLDER_ID || null
const folder = ref(null)
const loading = ref(true)
const error = ref(null)

const viewMode = ref('grid')
const sortMode = ref('default')
const isSortMenuOpen = ref(false)

const sortLabel = computed(() => {
  if (sortMode.value.startsWith('added')) return 'По дате'
  if (sortMode.value.startsWith('year')) return 'По году'
  return 'Порядок'
})

const sortIcon = computed(() => {
  if (sortMode.value === 'default') return icons.reorder
  return icons.sort_arrow
})

const arrowClass = computed(() => {
  if (sortMode.value.endsWith('asc')) return 'rotate-180'
  return ''
})

const sortedItems = computed(() => {
  if (!folder.value || !folder.value.items) return []
  const itemsCopy = [...folder.value.items]
  if (sortMode.value === 'added_desc') {
    return itemsCopy.sort((a, b) => new Date(b.added_at) - new Date(a.added_at) || b.id - a.id)
  } else if (sortMode.value === 'added_asc') {
    return itemsCopy.sort((a, b) => new Date(a.added_at) - new Date(b.added_at) || a.id - b.id)
  } else if (sortMode.value === 'year_desc') {
    return itemsCopy.sort((a, b) => (b.year || 0) - (a.year || 0) || b.id - a.id)
  } else if (sortMode.value === 'year_asc') {
    return itemsCopy.sort((a, b) => (a.year || 0) - (b.year || 0) || a.id - b.id)
  }
  return itemsCopy
})

const toggleSortDropdown = () => {
  isSortMenuOpen.value = !isSortMenuOpen.value
}

const setSort = (mode) => {
  if (mode === 'added') {
    sortMode.value = sortMode.value === 'added_desc' ? 'added_asc' : 'added_desc'
  } else if (mode === 'year') {
    sortMode.value = sortMode.value === 'year_desc' ? 'year_asc' : 'year_desc'
  } else {
    sortMode.value = 'default'
  }
  isSortMenuOpen.value = false
}

onMounted(async () => {
  if (!folderId) {
    error.value = 'ID списка не обнаружен'
    loading.value = false
    return
  }
  try {
    const response = await fetch(`/api/admin/wishlist/folder/${folderId}/`)
    if (!response.ok) throw new Error()
    folder.value = await response.json()
  } catch (e) {
    error.value = 'Не удалось загрузить данные списка'
  } finally {
    loading.value = false
  }
})
</script>