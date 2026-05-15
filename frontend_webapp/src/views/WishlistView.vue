<template>
  <div class="view active-view" id="view-wishlist">
    <div class="header" style="padding-bottom: 8px;">
      <div class="header-name glow-text" id="wl-main-header">
        <template v-if="wishlistStore.folders.length === 1 && wishlistStore.activeFolder">
           <span :style="{ color: wishlistStore.activeFolder.color, marginRight: '10px' }" 
                 v-html="icons[wishlistStore.activeFolder.icon] || icons.folder"></span>
           {{ wishlistStore.activeFolder.name }}
        </template>
        <template v-else>Мои списки</template>
      </div>
      
      <div class="top-controls">
        <button v-if="wishlistStore.folders.length > 1"
          class="wl-edit-btn" 
          :style="{ background: wishlistStore.isReorderFoldersMode ? 'var(--accent)' : '' }"
          @click="wishlistStore.isReorderFoldersMode = !wishlistStore.isReorderFoldersMode"
          v-html="icons.reorder"
        ></button>
        
        <div v-if="wishlistStore.activeFolder" class="view-toggle" style="margin: 0; padding: 2px;">
          <button class="vt-btn" :class="{ active: wishlistStore.viewMode === 'grid' }" @click="wishlistStore.setViewMode('grid')" v-html="icons.grid"></button>
          <button class="vt-btn" :class="{ active: wishlistStore.viewMode === 'list' }" @click="wishlistStore.setViewMode('list')" v-html="icons.list"></button>
        </div>
        
        <button class="theme-btn" @click="uiStore.toggleTheme" v-html="themeIcon"></button>
      </div>
    </div>

    <div v-if="wishlistStore.folders.length > 1" style="padding: 10px 16px;" id="wl-folders-wrapper">
      <div class="wl-folders-grid" :class="{ 'reorder-mode': wishlistStore.isReorderFoldersMode }">
        <FolderCard 
          v-for="folder in wishlistStore.folders" 
          :key="folder.id"
          :folder="folder"
          :is-active="wishlistStore.activeFolderId === folder.id"
          :is-reorder-mode="wishlistStore.isReorderFoldersMode"
          @select="wishlistStore.activeFolderId = $event"
        />
      </div>
    </div>

    <div v-if="wishlistStore.activeFolder" id="wl-active-folder-content">
      <div class="wl-active-header" v-if="wishlistStore.folders.length > 1">
        <div id="wl-active-folder-title" style="display:flex; align-items:center;">
          <span :style="{ color: wishlistStore.activeFolder.color, marginRight: '8px' }" v-html="icons[wishlistStore.activeFolder.icon] || icons.folder"></span>
          {{ wishlistStore.activeFolder.name }}
        </div>
      </div>

      <div id="wl-items-container" style="padding: 0 16px 24px;">
        <div v-if="!wishlistStore.activeFolder.items.length" class="empty">
          <div class="icon" v-html="icons.film"></div> Папка пуста
        </div>
        
        <div v-else :class="wishlistStore.viewMode === 'list' ? 'card-list-wrapper' : 'hist-grid'">
          <!-- Используем context="wishlist" чтобы не показывать оверлеи истории -->
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
    
    <div v-if="!wishlistStore.folders.length && !uiStore.isLoading" class="empty">
        <div class="icon" v-html="icons.bookmark"></div> Избранное пусто
    </div>
  </div>
</template>