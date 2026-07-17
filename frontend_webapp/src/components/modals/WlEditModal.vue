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
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUIStore } from '../../stores/uiStore'
import { useWishlistStore } from '../../stores/wishlistStore'
import { icons } from '../../utils/icons'

const uiStore = useUIStore()
const wishlistStore = useWishlistStore()
const router = useRouter()

const context = computed(() => uiStore.modals.wlEdit.context || {})
const isEdit = computed(() => context.value.isEdit === true)
const folderId = computed(() => context.value.folderId)

const folder = computed(() => {
  if (!isEdit.value || !folderId.value) return null
  return wishlistStore.folders.find(f => f.id === folderId.value) || null
})

const updateQueryParams = (params) => {
  const query = { ...router.currentRoute.value.query }
  Object.keys(params).forEach(key => {
    const val = params[key]
    if (val === null || val === undefined || val === '') {
      delete query[`modal_${key}`]
    } else {
      query[`modal_${key}`] = String(val)
    }
  })
  router.replace({ query }).catch(() => {})
}

const name = computed({
  get: () => {
    if (router.currentRoute.value.query.modal_name !== undefined) {
      return router.currentRoute.value.query.modal_name
    }
    return folder.value ? folder.value.name : ''
  },
  set: (val) => updateQueryParams({ name: val })
})

const selectedColor = computed({
  get: () => {
    if (router.currentRoute.value.query.modal_color !== undefined) {
      return router.currentRoute.value.query.modal_color
    }
    return folder.value ? folder.value.color : wishlistStore.FOLDER_COLORS[0]
  },
  set: (val) => updateQueryParams({ color: val })
})

const selectedIcon = computed({
  get: () => {
    if (router.currentRoute.value.query.modal_icon !== undefined) {
      return router.currentRoute.value.query.modal_icon
    }
    return folder.value ? folder.value.icon : wishlistStore.FOLDER_ICONS[0]
  },
  set: (val) => updateQueryParams({ icon: val })
})

const close = () => {
  uiStore.closeModal('wlEdit')
}

const save = async () => {
  const trimmedName = name.value?.trim() || ''
  if (trimmedName.length > 100) {
    uiStore.showToast('Название папки не должно превышать 100 символов')
    return
  }

  if (isEdit.value) {
    await wishlistStore.editFolder(folderId.value, trimmedName, selectedIcon.value, selectedColor.value)
  } else {
    await wishlistStore.createFolder(trimmedName, selectedIcon.value, selectedColor.value)
  }
  close()
}

const deleteFolder = async () => {
  if (confirm('Удалить папку и всё её содержимое?')) {
    await wishlistStore.deleteFolder(folderId.value)
    close()
  }
}
</script>