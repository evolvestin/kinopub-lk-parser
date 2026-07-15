<script setup>
import { ref, computed, onMounted, watch, onUnmounted, nextTick } from 'vue'
import { useWishlistStore } from '../stores/wishlistStore'
import { useUIStore } from '../stores/uiStore'
import { icons } from '../utils/icons'
import FolderCard from '../components/wishlist/FolderCard.vue'
import ShowCard from '../components/shared/ShowCard.vue'
import Sortable from 'sortablejs'

const wishlistStore = useWishlistStore()
const uiStore = useUIStore()

const isInitialLoading = ref(!wishlistStore.isLoaded)
const isSortMenuOpen = ref(false)
const mainHeaderReady = ref(false)
const activeFolderTitleReady = ref(false)
const themeIcon = computed(() => uiStore.theme === 'dark' ? icons.moon : icons.sun)

const foldersGridRef = ref(null)
const itemsGridRef = ref(null)
const mainHeaderRef = ref(null)
const activeFolderTitleRef = ref(null)

let foldersSortable = null
let itemsSortable = null

const sortLabel = computed(() => {
  if (wishlistStore.sortMode.startsWith('added')) return 'По дате'
  if (wishlistStore.sortMode.startsWith('year')) return 'По году'
  return 'Порядок'
})

const sortIcon = computed(() => {
  if (wishlistStore.sortMode === 'default') return icons.reorder
  return icons.sort_arrow
})

const arrowClass = computed(() => {
  if (wishlistStore.sortMode.endsWith('asc')) return 'rotate-180'
  return ''
})

const toggleSortDropdown = () => {
  isSortMenuOpen.value = !isSortMenuOpen.value
}

const setSort = (mode) => {
  let newMode = 'default'
  if (mode === 'added') {
    newMode = wishlistStore.sortMode === 'added_desc' ? 'added_asc' : 'added_desc'
  } else if (mode === 'year') {
    newMode = wishlistStore.sortMode === 'year_desc' ? 'year_asc' : 'year_desc'
  }
  wishlistStore.setSortMode(newMode)
  isSortMenuOpen.value = false
}

const adjustMainHeaderFont = () => {
  mainHeaderReady.value = false
  nextTick(() => {
    setTimeout(() => {
      if (mainHeaderRef.value) {
        uiStore.fitText(mainHeaderRef.value)
      }
      mainHeaderReady.value = true
    }, 50)
  })
}

const adjustActiveFolderFont = () => {
  activeFolderTitleReady.value = false
  nextTick(() => {
    setTimeout(() => {
      if (activeFolderTitleRef.value) {
        uiStore.fitText(activeFolderTitleRef.value)
      }
      activeFolderTitleReady.value = true
    }, 50)
  })
}

const adjustHeaderFonts = () => {
  adjustMainHeaderFont()
  adjustActiveFolderFont()
}

const initSortable = () => {
  nextTick(() => {
    if (foldersGridRef.value && !foldersSortable) {
      foldersSortable = new Sortable(foldersGridRef.value, {
        animation: 350,
        disabled: !wishlistStore.isReorderFoldersMode,
        forceFallback: true,
        onEnd: (evt) => {
          const order = Array.from(foldersGridRef.value.children).map(el => parseInt(el.dataset.id))
          wishlistStore.reorderFolders(order)
        }
      })
    }

    if (itemsGridRef.value && !itemsSortable) {
      const el = itemsGridRef.value.querySelector('.hist-grid, .card')
      if (el) {
        itemsSortable = new Sortable(el, {
          animation: 350,
          disabled: !wishlistStore.isReorderItemsMode,
          forceFallback: true,
          onEnd: (evt) => {
            const order = Array.from(el.children).map(el => parseInt(el.dataset.id))
            wishlistStore.reorderItems(wishlistStore.activeFolderId, order)
          }
        })
      }
    }
  })
}

onMounted(async () => {
  if (!wishlistStore.isLoaded) {
    isInitialLoading.value = true
  }
  await wishlistStore.fetchWishlist()
  isInitialLoading.value = false
  initSortable()
  adjustHeaderFonts()
})

onUnmounted(() => {
  if (foldersSortable) foldersSortable.destroy()
  if (itemsSortable) itemsSortable.destroy()
})

watch(() => wishlistStore.isReorderFoldersMode, (val) => {
  if (foldersSortable) foldersSortable.option('disabled', !val)
})

watch(() => wishlistStore.isReorderItemsMode, (val) => {
  if (itemsSortable) {
    itemsSortable.option('disabled', !val)
  }
})

watch(foldersGridRef, (newVal) => {
  if (newVal) {
    initSortable()
  } else if (foldersSortable) {
    foldersSortable.destroy()
    foldersSortable = null
  }
})

watch(itemsGridRef, (newVal) => {
  if (newVal) {
    initSortable()
  } else if (itemsSortable) {
    itemsSortable.destroy()
    itemsSortable = null
  }
})

watch(() => wishlistStore.activeFolderId, () => {
  if (itemsSortable) {
    itemsSortable.destroy()
    itemsSortable = null
  }
  initSortable()
  if (wishlistStore.folders.length > 1) {
    adjustActiveFolderFont()
  } else {
    adjustMainHeaderFont()
  }
})

watch(() => wishlistStore.folders.length, () => {
  adjustHeaderFonts()
})

watch(() => wishlistStore.activeFolder?.name, () => {
  if (wishlistStore.folders.length === 1) {
    adjustMainHeaderFont()
  } else {
    adjustActiveFolderFont()
  }
})

const handleEditFolder = (folderId) => {
  uiStore.openModal('wlEdit', { isEdit: true, folderId })
}

const handleDeleteFolder = async (folderId) => {
  if (confirm('Удалить папку и всё её содержимое?')) {
    await wishlistStore.deleteFolder(folderId)
  }
}

const handleCreateFolder = () => {
  if (wishlistStore.folders.length >= 12) {
    uiStore.openModal('wlLimit')
    return
  }
  uiStore.openModal('wlEdit', { isEdit: false })
}
</script>

<template>
  <div class="view active-view" id="view-wishlist">
    <div class="header" style="padding-bottom: 8px;">
      <div class="header-name glow-text" 
           :class="{ 'single-folder': wishlistStore.folders.length === 1 && wishlistStore.activeFolder }" 
           :style="{ opacity: mainHeaderReady ? 1 : 0, transition: 'opacity 0.15s ease' }"
           id="wl-main-header" 
           ref="mainHeaderRef">
        <template v-if="wishlistStore.folders.length === 1 && wishlistStore.activeFolder">
           <span :style="{ color: wishlistStore.activeFolder.color, marginRight: '10px' }" 
                 v-html="icons[wishlistStore.activeFolder.icon] || icons.folder"></span>
           {{ wishlistStore.activeFolder.name }}
        </template>
        <template v-else>Мои списки</template>
      </div>
      
      <div class="top-controls">
        <button class="wl-edit-btn" id="wl-casino-btn" @click="uiStore.openModal('casino')">🎰</button>
        <button v-if="wishlistStore.folders.length > 1"
          class="wl-edit-btn" 
          :style="{ background: wishlistStore.isReorderFoldersMode ? 'var(--accent)' : '' }"
          @click="wishlistStore.isReorderFoldersMode = !wishlistStore.isReorderFoldersMode"
          v-html="icons.reorder"
        ></button>
        
        <div v-if="wishlistStore.activeFolder" class="view-toggle" style="margin: 0; padding: 2px; display: flex;">
          <button class="vt-btn" :class="{ active: wishlistStore.viewMode === 'grid' }" @click="wishlistStore.setViewMode('grid')" v-html="icons.grid"></button>
          <button class="vt-btn" :class="{ active: wishlistStore.viewMode === 'list' }" @click="wishlistStore.setViewMode('list')" v-html="icons.list"></button>
        </div>
        
        <button class="theme-btn" @click="uiStore.toggleTheme" v-html="themeIcon"></button>
        <button class="share-btn" style="background: var(--accent); color: white; border-color: var(--accent);" @click="handleCreateFolder">
          <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        </button>
      </div>
    </div>

    <div v-if="isInitialLoading" class="loader-inline">
      <div class="spinner"></div>
    </div>

    <template v-else>
      <div v-if="wishlistStore.folders.length > 1" style="padding: 10px 16px;" id="wl-folders-wrapper">
        <div ref="foldersGridRef" class="wl-folders-grid" :class="{ 'reorder-mode': wishlistStore.isReorderFoldersMode }">
          <FolderCard 
            v-for="folder in wishlistStore.folders" 
            :key="folder.id"
            :folder="folder"
            :is-active="wishlistStore.activeFolderId === folder.id"
            :is-reorder-mode="wishlistStore.isReorderFoldersMode"
            @select="wishlistStore.activeFolderId = $event"
            @edit="handleEditFolder"
            @delete="handleDeleteFolder"
          />
        </div>
      </div>

      <div v-if="wishlistStore.activeFolder" id="wl-active-folder-content">
        <div class="wl-active-header">
          <div id="wl-active-folder-title" 
               v-if="wishlistStore.folders.length > 1" 
               :style="{ opacity: activeFolderTitleReady ? 1 : 0, transition: 'opacity 0.15s ease' }"
               ref="activeFolderTitleRef">
            <span :style="{ color: wishlistStore.activeFolder.color, marginRight: '8px' }" v-html="icons[wishlistStore.activeFolder.icon] || icons.folder" style="display: inline-flex; align-items: center;"></span>
            <span class="wl-active-folder-name-text">{{ wishlistStore.activeFolder.name }}</span>
          </div>
          <div style="display: flex; gap: 8px; align-items: center; margin-left: auto; flex-shrink: 0;">
            <div class="sort-dropdown-container">
              <button type="button" class="sort-trigger-btn" @click="toggleSortDropdown">
                <span class="sort-icon-main" :class="arrowClass" v-html="sortIcon"></span>
                <span class="sort-text-label">{{ sortLabel }}</span>
                <span class="sort-chevron" v-html="icons.chevron_down"></span>
              </button>
              <div class="sort-dropdown-menu" :class="{ show: isSortMenuOpen }">
                <div class="sort-item" :class="{ active: wishlistStore.sortMode === 'default' }" @click="setSort('default')">
                  <span class="icon-box" v-html="icons.reorder"></span>
                  <span>Порядок</span>
                </div>
                <div class="sort-item" :class="{ active: wishlistStore.sortMode.startsWith('added') }" @click="setSort('added')">
                  <span class="sort-arrow-icon" :class="{ 'rotate-180': wishlistStore.sortMode === 'added_asc' }" v-html="icons.sort_arrow"></span>
                  <span>Дата</span>
                </div>
                <div class="sort-item" :class="{ active: wishlistStore.sortMode.startsWith('year') }" @click="setSort('year')">
                  <span class="sort-arrow-icon" :class="{ 'rotate-180': wishlistStore.sortMode === 'year_asc' }" v-html="icons.sort_arrow"></span>
                  <span>Год</span>
                </div>
              </div>
            </div>

            <button class="wl-edit-btn" :style="{ background: wishlistStore.isReorderItemsMode ? 'var(--accent)' : '' }" @click="wishlistStore.isReorderItemsMode = !wishlistStore.isReorderItemsMode" v-html="icons.reorder"></button>
            <button class="wl-edit-btn" @click="handleEditFolder(wishlistStore.activeFolderId)" v-html="icons.gear"></button>
          </div>
        </div>

        <div ref="itemsGridRef" id="wl-items-container" :class="{ 'reorder-items-mode': wishlistStore.isReorderItemsMode }" style="padding: 0 16px 24px;">
          <div v-if="!wishlistStore.activeFolder.items.length" class="empty">
            <div class="icon" v-html="icons.film"></div> Папка пуста
          </div>
          
          <div v-else :class="wishlistStore.viewMode === 'list' ? 'card-list-wrapper' : 'hist-grid'">
            <ShowCard 
              v-for="item in wishlistStore.sortedItems" 
              :key="item.id" 
              :show="item"
              :view-mode="wishlistStore.viewMode"
              context="wishlist"
            />
          </div>
        </div>
      </div>
      
      <div v-if="!wishlistStore.folders.length" class="empty">
          <div class="icon" v-html="icons.bookmark"></div> Избранное пусто
      </div>
    </template>
  </div>
</template>