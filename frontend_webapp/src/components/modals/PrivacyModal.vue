<template>
  <div class="modal-overlay show" @click.self="close(false)">
    <div class="modal-content" style="padding: 24px;">
      <div class="modal-header-container" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-shrink: 0; width: 100%;">
        <div class="modal-title" style="font-size: 20px; font-weight: 800; color: var(--text-primary);">Настройки приватности</div>
        <button class="modal-close" @click="close(false)">×</button>
      </div>
      <div style="font-size: 14px; color: var(--text-secondary); margin-bottom: 24px; line-height: 1.5;">
        Выберите, как другие пользователи будут видеть ваши оценки. Вы можете изменить это в любой момент в настройках.
      </div>
      <div style="display: flex; flex-direction: column; gap: 12px;">
        <label class="chk-row" style="width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 12px; background: var(--bg-input);">
          <input type="radio" name="privacy" :value="true" v-model="localAnon">
          <div class="chk-box" style="border-radius: 50%;"></div>
          <div style="display: flex; flex-direction: column; text-align: left;">
            <span class="chk-text">Анонимно (По умолчанию)</span>
            <span style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Ваше имя скрыто. Другие увидят "Анонимный зритель", а вы — "Вы".</span>
          </div>
        </label>
        <label class="chk-row" style="width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 12px; background: var(--bg-input);">
          <input type="radio" name="privacy" :value="false" v-model="localAnon">
          <div class="chk-box" style="border-radius: 50%;"></div>
          <div style="display: flex; flex-direction: column; text-align: left;">
            <span class="chk-text">Публично</span>
            <span style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Другие увидят ваше имя и юзернейм в списках оценивших.</span>
          </div>
        </label>
      </div>
      <button class="btn-primary" style="margin-top: 24px;" :disabled="isSaving" @click="save">
        <div v-if="isSaving" class="spinner" style="width:16px;height:16px; border-width: 2px; border-top-color: #fff;"></div>
        <span v-else>Сохранить</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useUIStore } from '../../stores/uiStore'
import { useUserStore } from '../../stores/userStore'
import { useApi } from '../../composables/useApi'

const uiStore = useUIStore()
const userStore = useUserStore()
const api = useApi()

const localAnon = ref(userStore.isAnonymous)
const isSaving = ref(false)

const close = (success) => {
  const ctx = uiStore.modals.privacy.context
  uiStore.closeModal('privacy')
  if (success && ctx?.onSuccess) {
    ctx.onSuccess()
  }
}

const save = async () => {
  isSaving.value = true
  try {
    await api.post('set_privacy/', { is_anonymous: localAnon.value })
    userStore.isAnonymous = localAnon.value
    userStore.privacyChoiceMade = true
    close(true)
  } catch (e) {
    uiStore.showToast('Ошибка сохранения')
  } finally {
    isSaving.value = false
  }
}
</script>

<style scoped>
.chk-row input[type="radio"]:checked + .chk-box {
  background: var(--accent);
  border-color: var(--accent);
}
.chk-row input[type="radio"]:checked + .chk-box::after {
  content: '';
  width: 10px;
  height: 10px;
  background: #fff;
  border-radius: 50%;
  border: none;
  margin: 0;
  transform: none;
}
</style>