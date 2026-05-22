<template>
  <div class="modal-overlay show" @click.self="close">
    <div class="modal-content" style="text-align: center; padding: 24px; position: relative;">
      <div class="modal-title" style="margin-bottom: 16px; font-size: 18px; font-weight: 800;">
        Удаление из избранного
      </div>
      <div style="font-size: 15px; color: var(--text-secondary); margin-bottom: 20px; line-height: 1.4;">
        Вы уверены, что хотите удалить <b style="color:var(--text-primary)">«{{ context.title }}»</b> из списка?
      </div>
      <div style="position: relative; margin-bottom: 24px;">
        <div class="wl-help-popover" :class="{ show: showInformer }">
          Если галочка стоит, удаляемый фильм всё равно будет учитываться в общем счетчике <b>«Добавлено в избранное»</b> вашей статистики. Если её убрать — счетчик уменьшится.
        </div>
        <div style="display: flex; align-items: center; justify-content: center; gap: 8px;">
          <label class="chk-row" style="margin: 0;">
            <input type="checkbox" v-model="keepStats" />
            <div class="chk-box"></div>
            <span class="chk-text">Учитывать в статистике</span>
          </label>
          <div class="help-icon-trigger" 
               @click.stop="showInformer = !showInformer" 
               v-html="icons.help" 
               style="display: flex; color: var(--text-muted); cursor: pointer; width: 18px; height: 18px;">
          </div>
        </div>
      </div>
      <div style="display: flex; gap: 12px;">
        <button class="btn-primary" style="margin-top: 0; background: var(--bg-input); color: var(--text-primary); box-shadow: none; flex: 1;" @click="close">
          Отмена
        </button>
        <button class="btn-primary" style="margin-top: 0; background: var(--danger); box-shadow: 0 8px 24px rgba(231, 76, 60, 0.2); flex: 1;" @click="confirmDelete">
          Удалить
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useUIStore } from '../../stores/uiStore'
import { useWishlistStore } from '../../stores/wishlistStore'
import { icons } from '../../utils/icons'

const uiStore = useUIStore()
const wishlistStore = useWishlistStore()

const context = computed(() => uiStore.modals.wlDelete.context || {})
const keepStats = ref(true)
const showInformer = ref(false)

const close = () => {
  uiStore.closeModal('wlDelete')
}

const confirmDelete = async () => {
  await wishlistStore.removeItem(context.value.id, keepStats.value)
  close()
}
</script>