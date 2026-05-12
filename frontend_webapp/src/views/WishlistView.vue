<template>
  <div class="view active-view" id="view-wishlist">
    <div class="header" style="padding-bottom: 8px;">
      <div class="header-name glow-text">
        <template v-if="wishlistStore.folders.length === 1 && wishlistStore.activeFolder">
           <span :style="{ color: wishlistStore.activeFolder.color, marginRight: '10px' }" 
                 v-html="icons[wishlistStore.activeFolder.icon] || icons.folder"></span>
           {{ wishlistStore.activeFolder.name }}
        </template>
        <template v-else>Мои списки</template>
      </div>
      
      <div class="top-controls">
        <button 
          v-if="wishlistStore.folders.length > 1"
          class="wl-edit-btn" 
          :style="{ background: wishlistStore.isReorderFoldersMode ? 'var(--accent)' : '' }"
          @click="wishlistStore.isReorderFoldersMode = !wishlistStore.isReorderFoldersMode"
          v-html="icons.reorder"
        ></button>
        
        <div v-if="wishlistStore.activeFolder" class="view-toggle" style="margin: 0; padding: 2px;">
          <button 
            class="vt-btn" 
            :class="{ active: wishlistStore.viewMode === 'grid' }" 
            @click="wishlistStore.setViewMode('grid')"
            v-html="icons.grid"
          ></button>
          <button 
            class="vt-btn" 
            :class="{ active: wishlistStore.viewMode === 'list' }" 
            @click="wishlistStore.setViewMode('list')"
            v-html="icons.list"
          ></button>
        </div>
        
        <button class="theme-btn" @click="uiStore.toggleTheme" v-html="themeIcon"></button>
        
        <button class="share-btn" @click="openCreateModal" style="background: var(--accent); color: white;">
          <span v-html="icons.plus"></span>
        </button>
      </div>
    </div>

    <div style="padding: 10px 16px;" id="wl-folders-wrapper">
      <div 
        ref="foldersGridRef" 
        class="wl-folders-grid" 
        :class="{ 'reorder-mode': wishlistStore.isReorderFoldersMode }"
      >
        <FolderCard 
          v-for="folder in wishlistStore.folders" 
          :key="folder.id"
          :folder="folder"
          :is-active="wishlistStore.activeFolderId === folder.id"
          :is-reorder-mode="wishlistStore.isReorderFoldersMode"
          @select="wishlistStore.activeFolderId = $event"
          @edit="openEditModal"
          @delete="handleDeleteFolder"
        />
      </div>
    </div>

    <div v-if="wishlistStore.activeFolder" id="wl-active-folder-content">
      <div class="wl-active-header">
        <div id="wl-active-folder-title" v-if="wishlistStore.folders.length > 1">
          <span :style="{ color: wishlistStore.activeFolder.color }" 
                v-html="icons[wishlistStore.activeFolder.icon] || icons.folder"></span>
          {{ wishlistStore.activeFolder.name }}
        </div>
        
        <div style="display: flex; gap: 8px; align-items: center; margin-left: auto;">
          <div class="sort-dropdown-container">
             <button class="sort-trigger-btn" @click="wishlistStore.isSortMenuOpen = !wishlistStore.isSortMenuOpen">
               <span class="sort-icon-main" v-html="icons.reorder"></span>
               {{ sortLabel }}
             </button>
             <div class="sort-dropdown-menu" :class="{ show: wishlistStore.isSortMenuOpen }">
               <div class="sort-item" @click="setSort('default')">Порядок</div>
               <div class="sort-item" @click="setSort('added_desc')">Сначала новые</div>
               <div class="sort-item" @click="setSort('year_desc')">По году (новые)</div>
             </div>
          </div>

          <button 
            v-if="wishlistStore.activeFolder.items.length > 1"
            class="wl-edit-btn" 
            :style="{ background: wishlistStore.isReorderItemsMode ? 'var(--accent)' : '' }"
            @click="wishlistStore.isReorderItemsMode = !wishlistStore.isReorderItemsMode"
            v-html="icons.reorder"
          ></button>
          
          <button class="wl-edit-btn" @click="openEditModal(wishlistStore.activeFolderId)" v-html="icons.gear"></button>
        </div>
      </div>

      <div 
        ref="itemsContainerRef" 
        id="wl-items-container" 
        style="padding: 0 16px 24px;"
        :class="{ 'reorder-items-mode': wishlistStore.isReorderItemsMode }"
      >
        <div v-if="!wishlistStore.activeFolder.items.length" class="empty">
          <div class="icon" v-html="icons.film"></div> Папка пуста
        </div>
        
        <div v-else :class="wishlistStore.viewMode === 'list' ? 'card-list-wrapper' : 'hist-grid'">
          <div 
            v-for="item in wishlistStore.sortedItems" 
            :key="item.id"
            :data-id="item.id"
            :class="wishlistStore.viewMode === 'list' ? 'hist-item clickable' : 'grid-item-wrap'"
            @click="handleItemClick(item)"
          >
            <div v-if="wishlistStore.isReorderItemsMode" class="wl-delete-badge" @click.stop="confirmDeleteItem(item)">
              <span v-html="icons.minus"></span>
            </div>

            <template v-if="wishlistStore.viewMode === 'grid'">
              <div class="grid-item">
                <img :src="item.poster_url" class="grid-poster" loading="lazy">
                <div v-if="item.user_rating" class="grid-badges">
                  <span class="rating-badge" style="background:rgba(0,0,0,0.6);border:none;">
                    <span v-html="icons.star"></span>{{ item.user_rating }}
                  </span>
                </div>
                <div v-if="item.year" class="grid-year">{{ item.year }}</div>
                <div class="grid-overlay">
                  <div class="grid-date" style="color: var(--text-muted);">{{ item.added_at }}</div>
                </div>
              </div>
              <div class="grid-below-title">{{ item.title }}</div>
            </template>

            <template v-else>
              <img :src="item.poster_url" class="hist-poster" loading="lazy">
              <div class="hist-info">
                <div class="hist-title">{{ item.title }}</div>
                <div class="hist-meta">
                  <span v-if="item.year">{{ item.year }}</span>
                  <span v-if="item.user_rating" class="rating-badge">
                    <span v-html="icons.star"></span>{{ item.user_rating }}
                  </span>
                  <span style="opacity: 0.6;">· {{ item.added_at }}</span>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch, computed, nextTick } from 'vue'
import Sortable from 'sortablejs'
import { useWishlistStore } from '../stores/wishlistStore'
import { useUIStore } from '../stores/uiStore'
import { useTelegram } from '../composables/useTelegram'
import { icons } from '../utils/icons'
import FolderCard from '../components/wishlist/FolderCard.vue'

const wishlistStore = useWishlistStore()
const uiStore = useUIStore()
const { showConfirm } = useTelegram()

const foldersGridRef = ref(null)
const itemsContainerRef = ref(null)

const themeIcon = computed(() => uiStore.theme === 'dark' ? icons.moon : icons.sun)
const sortLabel = computed(() => {
  if (wishlistStore.sortMode === 'added_desc') return 'Новые'
  if (wishlistStore.sortMode === 'year_desc') return 'По году'
  return 'Порядок'
})

let foldersSortable = null
let itemsSortable = null

const initSortables = () => {
  if (foldersGridRef.value) {
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

  const itemsTarget = itemsContainerRef.value?.querySelector('.hist-grid, .card-list-wrapper')
  if (itemsTarget) {
    itemsSortable = new Sortable(itemsTarget, {
      animation: 350,
      disabled: !wishlistStore.isReorderItemsMode,
      forceFallback: true,
      onEnd: (evt) => {
        const order = Array.from(itemsTarget.children).map(el => parseInt(el.dataset.id))
        wishlistStore.reorderItems(wishlistStore.activeFolderId, order)
      }
    })
  }
}

const setSort = (mode) => {
  wishlistStore.sortMode = mode
  wishlistStore.isSortMenuOpen = false
}

const handleItemClick = (item) => {
  if (wishlistStore.isReorderItemsMode) return
  console.log('Open show', item.show_id)
}

const openCreateModal = () => uiStore.showToast('Создание папок будет в 7 итерации')
const openEditModal = (id) => uiStore.showToast('Редактирование будет в 7 итерации')

const handleDeleteFolder = (id) => {
  showConfirm('Удалить папку и всё содержимое?', (ok) => {
    if (confirmed) wishlistStore.toggleFolderDelete(id)
  })
}

const confirmDeleteItem = (item) => {
  showConfirm(`Удалить «${item.title}»?`, (ok) => {
    if (ok) wishlistStore.deleteItem(item.id)
  })
}

watch(() => wishlistStore.isReorderFoldersMode, (val) => foldersSortable?.option('disabled', !val))
watch(() => wishlistStore.isReorderItemsMode, (val) => itemsSortable?.option('disabled', !val))
watch(() => wishlistStore.activeFolderId, () => {
  nextTick(() => initSortables())
})

onMounted(async () => {
  uiStore.setLoading(true)
  await wishlistStore.fetchWishlist()
  uiStore.setLoading(false)
  initSortables()
})
</script>

<style scoped>
.reorder-mode .wl-folder-card,
.reorder-items-mode .grid-item-wrap,
.reorder-items-mode .hist-item {
  animation: iosWiggle 0.55s infinite ease-in-out;
}

@keyframes iosWiggle {
  0% { transform: rotate(-1.2deg); }
  50% { transform: rotate(1.2deg); }
  100% { transform: rotate(-1.2deg); }
}

.card-list-wrapper {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
}
</style>