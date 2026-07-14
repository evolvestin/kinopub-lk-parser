<template>
  <div class="modal-overlay show" @click.self="close">
    <div class="modal-content" style="padding: 24px;">
      <div class="modal-header-container" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-shrink: 0; width: 100%;">
        <div class="modal-title" style="font-size: 20px; font-weight: 800; color: var(--text-primary);">{{ isEdit ? 'Настройки папки' : 'Новая папка' }}</div>
        <button class="modal-close" @click="close">×</button>
      </div>
      
      <input type="text" 
             v-model="name" 
             class="search-input" 
             placeholder="Название папки" 
             style="margin-bottom: 20px;" />
             
      <div class="share-section-title" style="margin-top: 0;">Цвет</div>
      <div class="wl-color-picker">
        <div v-for="c in wishlistStore.FOLDER_COLORS" 
             :key="c" 
             class="wl-color-btn" 
             :class="{ active: selectedColor === c }"
             :style="{ backgroundColor: c }"
             @click="selectedColor = c">
        </div>
      </div>
      
      <div class="share-section-title">Иконка</div>
      <div class="wl-icon-picker">
        <div v-for="ico in wishlistStore.FOLDER_ICONS" 
             :key="ico" 
             class="wl-icon-btn" 
             :class="{ active: selectedIcon === ico }"
             @click="selectedIcon = ico"
             v-html="icons[ico] || icons.folder">
        </div>
      </div>
      
      <div style="display: flex; gap: 12px; margin-top: 30px; align-items: center;">
        <button class="btn-primary" style="margin-top: 0; flex: 1;" @click="save">Сохранить</button>
        <button v-if="isEdit" 
                class="btn-primary" 
                style="background: var(--bg-input); color: var(--danger); border: 1px solid var(--border); margin-top: 0; width: 56px; height: 56px; padding: 0; flex-shrink: 0;" 
                @click="deleteFolder">
          <span v-html="icons.trash" style="display: block; margin: auto;"></span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUIStore } from '../../stores/uiStore'
import { useWishlistStore } from '../../stores/wishlistStore'
import { icons } from '../../utils/icons'

const uiStore = useUIStore()
const wishlistStore = useWishlistStore()
const router = useRouter()

const context = computed(() => uiStore.modals.wlDelete.context || {})
const showInformer = ref(false)

const keepStats = computed({
  get: () => router.currentRoute.value.query.modal_keepStats !== 'false',
  set: (val) => {
    const query = { ...router.currentRoute.value.query }
    query.modal_keepStats = String(val)
    router.replace({ query }).catch(() => {})
  }
})

const close = () => {
  uiStore.closeModal('wlDelete')
}

const confirmDelete = async () => {
  await wishlistStore.removeItem(context.value.id, keepStats.value)
  close()
}
</script>