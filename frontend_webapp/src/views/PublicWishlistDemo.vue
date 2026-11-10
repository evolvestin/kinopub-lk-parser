<template>
  <div class="public-demo-root" aria-label="Демонстрация избранного">
    <div class="header" style="padding-bottom: 8px;">
      <div class="header-name glow-text">Мои списки</div>
      <div class="top-controls">
        <button class="wl-edit-btn" aria-label="Рулетка">🎰</button>
        <button class="wl-edit-btn" aria-label="Порядок папок" v-html="icons.reorder"></button>
        <div class="view-toggle" style="margin: 0; padding: 2px; display: flex;"><button class="vt-btn active" aria-label="Сетка" v-html="icons.grid"></button><button class="vt-btn" aria-label="Список" v-html="icons.list"></button></div>
        <button class="theme-btn" aria-label="Тема" v-html="icons.moon"></button>
        <button class="share-btn" aria-label="Добавить папку" style="background:var(--accent);color:white;border-color:var(--accent)"><svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></button>
      </div>
    </div>
    <div class="wl-folders-grid"><FolderCard v-for="folder in folders" :key="folder.id" :folder="folder" :is-active="folder.id === 1" /></div>
    <div id="wl-active-folder-content"><div class="wl-active-header"><div id="wl-active-folder-title"><span style="color:#388bfd;display:inline-flex" v-html="icons.bookmark"></span><span class="wl-active-folder-name-text">Буду смотреть</span></div><button class="sort-trigger-btn"><span v-html="icons.reorder"></span><span>Порядок</span><span v-html="icons.chevron_down"></span></button><button class="wl-edit-btn" v-html="icons.gear" aria-label="Настройки"></button></div><div id="wl-items-container"><div class="hist-grid"><ShowCard v-for="item in folders[0].items" :key="item.id" :show="item" context="wishlist" /></div></div></div>
    <BottomNav />
  </div>
</template>
<script setup>
import { onMounted } from 'vue'
import FolderCard from '../components/wishlist/FolderCard.vue'
import ShowCard from '../components/shared/ShowCard.vue'
import BottomNav from '../components/layout/BottomNav.vue'
import { icons } from '../utils/icons'
import { useUIStore } from '../stores/uiStore'
const folders = [
  { id: 1, name: 'Буду смотреть', icon: 'bookmark', color: '#388bfd', items: [
    { id: 1, title: 'Дюна', year: 2021, poster_url: 'https://image.tmdb.org/t/p/w200/d5NXSklXo0qyIYkgV94XAgMIckC.jpg' },
    { id: 2, title: 'Во все тяжкие', year: 2008, poster_url: 'https://image.tmdb.org/t/p/w200/ggFHVNu6YYI5L9pCfOacjizRGt.jpg' }
  ] },
  { id: 2, name: 'Семья', icon: 'heart', color: '#e74c3c', items: [{ id: 3 }] }
]
const ui = useUIStore()
onMounted(() => { ui.activeView = 'wishlist' })
</script>
<style scoped>
.public-demo-root { position:relative; min-height:100vh; background:var(--bg-main); overflow:hidden; }
.public-demo-root .wl-folders-grid { padding:0 16px; }
.public-demo-root .bottom-nav { position:absolute; }
.public-demo-root #wl-items-container { padding-bottom:80px; }
.public-demo-root .top-controls { gap:4px; }
.public-demo-root .wl-edit-btn, .public-demo-root .theme-btn, .public-demo-root .share-btn { width:34px; height:34px; }
</style>
