<template>
  <div class="modal-overlay show" @click.self="close">
    <div class="modal-content" style="padding: 24px;">
      <div class="modal-header-container" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-shrink: 0; width: 100%;">
        <div class="modal-title" style="font-size: 12px; opacity: 0.5; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;">
          Добавить в список
        </div>
        <button class="modal-close" @click="close">×</button>
      </div>
      <div style="font-size: 22px; font-weight: 900; color: var(--text-primary); margin-bottom: 24px; line-height: 1.1; letter-spacing: -0.5px; padding-right: 20px;">
        {{ context.title }}
      </div>

      <div v-if="statsStore.isShared" style="margin-bottom: 16px; padding: 10px; background: rgba(231, 76, 60, 0.1); border: 1px solid rgba(231, 76, 60, 0.2); border-radius: 10px; font-size: 11px; color: var(--text-secondary); line-height: 1.3; text-align: center;">
        ⚠️ Добавление произойдет в ваши <strong style="color: var(--text-primary);">личные папки</strong> избранного.
      </div>

      <div style="font-size: 13px; font-weight: 800; color: var(--accent); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
        Выберите папку
      </div>
      <div id="wl-modal-folders">
        <div v-for="f in wishlistStore.folders" 
             :key="f.id" 
             class="wl-folder-card" 
             :style="hasShow(f) ? { borderColor: 'var(--accent)', background: 'var(--accent-dim)' } : {}"
             @click="addToFolder(f.id)">
          <div class="wl-folder-icon" :style="{ color: f.color }">
            <span v-html="icons[f.icon] || icons.folder"></span>
          </div>
          <div class="wl-folder-info" style="display: flex; align-items: center; justify-content: space-between; width: 100%; min-width: 0; gap: 8px;">
            <div style="min-width: 0; flex: 1;">
              <div class="wl-folder-name">{{ f.name }}</div>
              <div class="wl-folder-count">
                {{ f.items.length }} {{ plural(f.items.length, ['элемент', 'элемента', 'элементов']) }}
              </div>
            </div>
            <div v-if="hasShow(f)" style="color: var(--accent); display: flex; align-items: center; flex-shrink: 0;" v-html="icons.check"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useUIStore } from '../../stores/uiStore'
import { useWishlistStore } from '../../stores/wishlistStore'
import { useStatsStore } from '../../stores/useStatsStore'
import { icons } from '../../utils/icons'
import { plural } from '../../utils/helpers'

const uiStore = useUIStore()
const wishlistStore = useWishlistStore()
const statsStore = useStatsStore()

const context = computed(() => uiStore.modals.wlFolder.context || {})

const hasShow = (folder) => {
  return folder.items && folder.items.some(item => item.show_id === context.value.showId)
}

const close = () => {
  uiStore.closeModal('wlFolder')
}

const addToFolder = async (folderId) => {
  await wishlistStore.addItemToFolder(folderId, context.value.showId)
  close()
}
</script>