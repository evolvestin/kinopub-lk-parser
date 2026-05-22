<template>
  <div class="modal-overlay show" @click.self="close">
    <div class="modal-content" style="text-align: center; padding: 40px 24px;">
      <div style="font-size: 64px; margin-bottom: 20px;">⚠️</div>
      <div style="font-size: 20px; font-weight: 900; color: var(--text-primary); margin-bottom: 12px; letter-spacing: -0.5px;">
        Лимит папок исчерпан
      </div>
      <div style="font-size: 15px; color: var(--text-secondary); line-height: 1.5; margin-bottom: 30px;">
        Вы можете создать не более <b style="color: var(--accent);">12 папок</b> в избранном.<br />Удалите ненужные списки, чтобы создать новые.
      </div>
      <button class="btn-primary" style="margin-top: 0;" @click="close">Хорошо</button>
    </div>
  </div>
</template>

<script setup>
import { useUIStore } from '../../stores/uiStore'

const uiStore = useUIStore()
const close = () => {
  uiStore.closeModal('wlLimit')
}
</script>