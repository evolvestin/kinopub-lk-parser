<template>
  <div class="modal-overlay show" @click.self="close">
    <div class="modal-content">
      <div class="modal-header">
        <div class="modal-title">{{ isEdit ? 'Настройки папки' : 'Новая папка' }}</div>
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
import { ref, computed, onMounted } from 'vue'
import { useUIStore } from '../../stores/uiStore'
import { useWishlistStore } from '../../stores/wishlistStore'
import { icons } from '../../utils/icons'

const uiStore = useUIStore()
const wishlistStore = useWishlistStore()

const context = computed(() => uiStore.modals.wlEdit.context || {})
const isEdit = computed(() => !!context.value?.isEdit)

const name = ref('')
const selectedColor = ref(wishlistStore.FOLDER_COLORS[0])
const selectedIcon = ref(wishlistStore.FOLDER_ICONS[0])

onMounted(() => {
  if (isEdit.value) {
    const folder = wishlistStore.folders.find(f => f.id === wishlistStore.activeFolderId)
    if (folder) {
      name.value = folder.name
      selectedColor.value = folder.color
      selectedIcon.value = folder.icon
    }
  }
})

const close = () => {
  uiStore.closeModal('wlEdit')
}

const save = async () => {
  if (isEdit.value) {
    await wishlistStore.editFolder(wishlistStore.activeFolderId, name.value, selectedIcon.value, selectedColor.value)
  } else {
    await wishlistStore.createFolder(name.value, selectedIcon.value, selectedColor.value)
  }
  close()
}

const deleteFolder = async () => {
  if (confirm('Удалить папку и всё её содержимое?')) {
    await wishlistStore.deleteFolder(wishlistStore.activeFolderId)
    close()
  }
}
</script>