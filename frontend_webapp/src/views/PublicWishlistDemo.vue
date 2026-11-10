<template>
  <template v-if="statsExample">
    <StatsView :demo-mode="true" />
    <PrivacyModal v-if="ui.modals.privacy.isOpen" :demo="true" />
  </template>
  <div v-else class="public-demo-root" aria-label="Интерактивный пример избранного">
    <template v-if="ui.activeView === 'wishlist'">
    <div class="header public-demo-header">
      <div class="header-name glow-text">Мои списки</div>
      <div class="top-controls">
        <button class="wl-edit-btn" aria-label="Рулетка" @click="rouletteOpen = true">🎰</button>
        <button class="wl-edit-btn" :class="{ active: reorderMode }" aria-label="Порядок папок" @click="reorderMode = !reorderMode" v-html="icons.reorder"></button>
        <div class="view-toggle" style="margin:0;padding:2px;display:flex">
          <button class="vt-btn" :class="{ active: viewMode === 'grid' }" aria-label="Сетка" @click="viewMode = 'grid'" v-html="icons.grid"></button>
          <button class="vt-btn" :class="{ active: viewMode === 'list' }" aria-label="Список" @click="viewMode = 'list'" v-html="icons.list"></button>
        </div>
        <button class="theme-btn" aria-label="Тема" @click="ui.toggleTheme" v-html="ui.theme === 'dark' ? icons.moon : icons.sun"></button>
        <button class="share-btn" aria-label="Добавить папку" @click="folderDialogOpen = true"><svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></button>
      </div>
    </div>
    <div class="wl-folders-grid">
      <FolderCard v-for="folder in folders" :key="folder.id" :folder="folder" :is-active="folder.id === activeFolderId" :is-reorder-mode="reorderMode" @select="selectFolder" />
    </div>
    <div id="wl-active-folder-content">
      <div class="wl-active-header">
        <div id="wl-active-folder-title"><span :style="{color:activeFolder.color,display:'inline-flex'}" v-html="icons[activeFolder.icon] || icons.bookmark"></span><span class="wl-active-folder-name-text">{{ activeFolder.name }}</span></div>
        <div class="public-demo-sort-wrap"><button class="sort-trigger-btn" @click="sortMenuOpen = !sortMenuOpen"><span v-html="icons.reorder"></span><span>{{ sortLabel }}</span><span v-html="icons.chevron_down"></span></button><div v-if="sortMenuOpen" class="public-demo-sort-menu"><button v-for="item in sortOptions" :key="item.key" @click="applySort(item.key)">{{ item.label }}<span v-if="sortMode === item.key">✓</span></button></div></div>
        <button class="wl-edit-btn" aria-label="Настройки папки" @click="folderDialogOpen = true" v-html="icons.gear"></button>
      </div>
      <div id="wl-items-container">
        <div class="hist-grid" :class="{'public-demo-list':viewMode==='list'}">
          <ShowCard v-for="item in activeFolder.items" :key="item.id" :show="item" :view-mode="viewMode" context="wishlist" :demo-mode="true" />
        </div>
        <div v-if="activeFolder.items.length === 0" class="public-demo-empty">Здесь появятся фильмы и сериалы, которые вы добавите в эту папку.</div>
      </div>
    </div>
    <BottomNav />

    <div v-if="folderDialogOpen" class="public-demo-overlay" @click.self="closeFolderDialog">
      <section class="public-demo-dialog" role="dialog" aria-modal="true" aria-labelledby="demo-folder-title">
        <button class="public-demo-close" aria-label="Закрыть" @click="closeFolderDialog">×</button>
        <div class="modal-title" id="demo-folder-title">Новая папка</div>
        <p>Соберите фильмы и сериалы в отдельный список.</p>
        <label for="demo-folder-name">Название папки</label>
        <input id="demo-folder-name" v-model="folderName" maxlength="32" placeholder="Например, Текущие сериалы" @keydown.enter="createFolder" autofocus>
        <div class="public-demo-color-label">Цвет и значок можно изменить позже в настройках.</div>
        <button class="btn-primary" :disabled="!folderName.trim()" @click="createFolder">Создать папку</button>
      </section>
    </div>

    <CasinoModal v-if="rouletteOpen" :demo-folders="folders" @close="rouletteOpen = false" />
    </template>
    <SearchView v-else-if="ui.activeView === 'search'" :demo-mode="true" />
    <PublicStatsPreview v-else />
    <div id="dynamic-layers">
      <div v-for="(layer, index) in ui.layerStack" :key="layer.key" class="layer" :style="{zIndex:1000 + index,display:index === ui.layerStack.length - 1 ? 'block' : 'none'}">
        <ShowDetailsLayer v-if="layer.type === 'show'" :show-id="layer.props.showId" :demo-mode="true" />
      </div>
    </div>
    <WlFolderModal v-if="ui.modals.wlFolder.isOpen" :demo-mode="Boolean(ui.modals.wlFolder.context?.demoMode)" />
    <AddViewModal v-if="ui.modals.addView.isOpen" v-bind="ui.modals.addView.context" />
    <RatingModal v-if="ui.modals.rateShow.isOpen" v-bind="ui.modals.rateShow.context" />
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, onMounted, ref, watch } from 'vue'
import FolderCard from '../components/wishlist/FolderCard.vue'
import ShowCard from '../components/shared/ShowCard.vue'
import BottomNav from '../components/layout/BottomNav.vue'
import SearchView from './SearchView.vue'
import PublicStatsPreview from './PublicStatsPreview.vue'
import ShowDetailsLayer from '../components/layers/ShowDetailsLayer.vue'
import WlFolderModal from '../components/modals/WlFolderModal.vue'
import AddViewModal from '../components/modals/AddViewModal.vue'
import RatingModal from '../components/modals/RatingModal.vue'
import CasinoModal from '../components/modals/CasinoModal.vue'
import PrivacyModal from '../components/modals/PrivacyModal.vue'
import { icons } from '../utils/icons'
import { useUIStore } from '../stores/uiStore'

const StatsView = defineAsyncComponent(() => import('./StatsView.vue'))
const demoRatings = JSON.parse(document.getElementById('public-demo-ratings')?.textContent || '{}')
const folders = ref([
  { id: 1, name: 'Буду смотреть', icon: 'bookmark', color: '#388bfd', items: [
    { id: 10001, show_id: 74959, title: 'Дюна', year: 2021, type: 'Movie', user_rating: demoRatings[74959], poster_url: 'https://image.tmdb.org/t/p/w500/d5NXSklXo0qyIYkgV94XAgMIckC.jpg' },
    { id: 10002, show_id: 8739, title: 'Во все тяжкие', year: 2008, type: 'Series', user_rating: demoRatings[8739], poster_url: 'https://image.tmdb.org/t/p/w500/ggFHVNu6YYI5L9pCfOacjizRGt.jpg' }
  ] },
  { id: 2, name: 'Семья', icon: 'heart', color: '#e74c3c', items: [
    { id: 10003, show_id: 8613, title: 'Интерстеллар', year: 2014, poster_url: 'https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg' }
  ] }
])
const activeFolderId = ref(1)
const viewMode = ref('grid')
const sortMode = ref('default')
const reorderMode = ref(false)
const sortMenuOpen = ref(false)
const folderDialogOpen = ref(false)
const rouletteOpen = ref(false)
const folderName = ref('')
const sortOptions = [
  { key: 'default', label: 'Порядок' },
  { key: 'added_desc', label: 'Сначала добавленные' },
  { key: 'year_desc', label: 'Сначала новые' },
  { key: 'year_asc', label: 'Сначала старые' }
]
const activeFolder = computed(() => folders.value.find(folder => folder.id === activeFolderId.value) || folders.value[0])
const sortLabel = computed(() => sortOptions.find(option => option.key === sortMode.value)?.label || 'Порядок')
const ui = useUIStore()
watch(() => ui.theme, theme => document.body.classList.toggle('light', theme === 'light'), { immediate: true })
const statsExample = new URLSearchParams(window.location.search).has('stats-example')
onMounted(() => { ui.activeView = 'wishlist' })

function selectFolder(id) {
  if (!reorderMode.value) activeFolderId.value = id
}
function applySort(mode) {
  sortMode.value = mode
  const folder = activeFolder.value
  if (mode === 'year_desc') folder.items.sort((a, b) => (b.year || 0) - (a.year || 0))
  if (mode === 'year_asc') folder.items.sort((a, b) => (a.year || 0) - (b.year || 0))
  if (mode === 'default') folder.items.reverse()
  sortMenuOpen.value = false
}
function closeFolderDialog() {
  folderDialogOpen.value = false
  folderName.value = ''
}
function createFolder() {
  const name = folderName.value.trim()
  if (!name) return
  const id = Math.max(...folders.value.map(folder => folder.id)) + 1
  folders.value.push({ id, name, icon: 'folder', color: '#2ecc71', items: [] })
  activeFolderId.value = id
  closeFolderDialog()
}
</script>

<style scoped>
.public-demo-header .header-name{font-size:19px;white-space:nowrap;overflow-wrap:normal;word-break:normal}
.public-demo-root .top-controls{gap:3px}
.public-demo-root .top-controls .wl-edit-btn,.public-demo-root .top-controls .theme-btn,.public-demo-root .top-controls .share-btn{width:32px;height:32px}
.public-demo-root .top-controls .vt-btn{padding:5px}
@media(max-width:360px){.public-demo-header .header-name{font-size:16px}.public-demo-root .top-controls .wl-edit-btn,.public-demo-root .top-controls .theme-btn,.public-demo-root .top-controls .share-btn{width:29px;height:29px}.public-demo-root .top-controls .vt-btn{padding:3px}}
.public-demo-root{position:relative;min-height:100vh;background:var(--bg-main);overflow:hidden}.public-demo-header{padding:16px 16px 12px}.public-demo-root .wl-folders-grid{padding:0 16px}.public-demo-root .bottom-nav{position:absolute}.public-demo-root #wl-items-container{padding:0 16px 80px}.public-demo-root .top-controls{gap:4px}.public-demo-root .wl-edit-btn,.public-demo-root .theme-btn,.public-demo-root .share-btn{width:38px;height:38px}.public-demo-root .hist-grid{display:grid}.public-demo-root .public-demo-list{display:flex;flex-direction:column;gap:10px}.public-demo-sort-wrap{position:relative}.public-demo-sort-menu{position:absolute;right:0;top:calc(100% + 7px);z-index:8;min-width:230px;padding:6px;border:1px solid var(--border-color);border-radius:14px;background:var(--bg-card);box-shadow:0 15px 42px #0008}.public-demo-sort-menu button{width:100%;display:flex;justify-content:space-between;padding:11px 12px;border:0;border-radius:9px;background:none;color:var(--text-primary);font:inherit;text-align:left;cursor:pointer}.public-demo-sort-menu button:hover{background:var(--bg-hover)}.public-demo-empty{margin:24px 4px;color:var(--text-muted);font-size:14px}.public-demo-overlay{position:fixed;inset:0;z-index:40;display:grid;place-items:center;padding:24px;background:#0009;backdrop-filter:blur(8px)}.public-demo-dialog{position:relative;width:min(100%,430px);padding:28px;border:1px solid var(--border-color);border-radius:24px;background:var(--bg-card);box-shadow:0 24px 80px #000a;animation:demo-in .3s cubic-bezier(.2,.8,.2,1) both}.public-demo-dialog .modal-title{margin:0 0 10px;color:var(--text-primary);font-size:23px;font-weight:800}.public-demo-dialog p{margin:0 0 22px;color:var(--text-muted);line-height:1.6}.public-demo-dialog label{display:block;margin:0 0 8px;color:var(--text-primary);font-size:13px;font-weight:700}.public-demo-dialog input{width:100%;padding:14px 15px;border:1px solid var(--border-color);border-radius:13px;background:var(--bg-main);color:var(--text-primary);font:inherit}.public-demo-color-label{margin:13px 0 18px;color:var(--text-muted);font-size:12px}.public-demo-dialog .btn-primary{width:100%;min-height:48px;border:0;border-radius:14px;font:inherit;font-weight:800;cursor:pointer}.public-demo-dialog .btn-primary:disabled{opacity:.45;cursor:not-allowed}.public-demo-close{position:absolute;top:13px;right:15px;width:36px;height:36px;border:0;border-radius:50%;background:var(--bg-hover);color:var(--text-primary);font-size:25px;cursor:pointer}.public-demo-pick{margin:18px 0;padding:24px;border:1px solid var(--border-color);border-radius:17px;background:var(--bg-main);color:var(--accent);font-size:25px;font-weight:800;text-align:center}@keyframes demo-in{from{opacity:0;transform:translateY(12px) scale(.98)}to{opacity:1;transform:none}}
</style>
