<template>
  <div class="modal-overlay show" @click.self="close">
    <div class="modal-content" style="padding: 24px;">
      <div class="modal-header-container" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-shrink: 0; width: 100%;">
        <div class="modal-title" style="font-size: 20px; font-weight: 800; color: var(--text-primary);">Поделиться статистикой</div>
        <button class="modal-close" @click="close">×</button>
      </div>
      
      <div class="share-section-title" style="margin-top: 0;">Годы для экспорта</div>
      <div class="years-grid">
        <label v-for="y in statsStore.availableYears" :key="y">
            <input type="checkbox" v-model="selectedYears" :value="y" class="yr-chk-input">
            <div class="yr-chk-btn">{{ y === 'all' ? 'Всё время' : y }}</div>
        </label>
      </div>

      <div class="share-section-title">Конфиденциальность</div>
      <div class="share-opts">
        <label class="chk-row">
            <input type="checkbox" v-model="config.anon_user">
            <div class="chk-box"></div>
            <span class="chk-text">Скрыть мой профиль (Аноним)</span>
        </label>
        <label class="chk-row" v-if="statsStore.hasGroup">
            <input type="checkbox" v-model="config.include_group">
            <div class="chk-box"></div>
            <span class="chk-text">Включить вкладку "Группа"</span>
        </label>
        <label class="chk-row" v-if="config.include_group" style="padding-left:34px;">
            <input type="checkbox" v-model="config.anon_group">
            <div class="chk-box"></div>
            <span class="chk-text">Скрыть имена участников</span>
        </label>
      </div>

      <button class="btn-primary" :disabled="isBaking" @click="submit">
        <div v-if="isBaking" class="spinner" style="width:20px;height:20px;border-width:2px;margin:0;"></div>
        <template v-else>
            <span v-html="icons.share" style="margin-right: 8px;"></span>
            Создать ссылку
        </template>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useUIStore } from '../../stores/uiStore'
import { useStatsStore } from '../../stores/useStatsStore'
import { useApi } from '../../composables/useApi'
import { icons } from '../../utils/icons'

const uiStore = useUIStore()
const statsStore = useStatsStore()
const api = useApi()

const isBaking = ref(false)
const selectedYears = ref(['all'])
const config = ref({
    anon_user: false,
    include_group: true,
    anon_group: false
})

const close = () => {
  uiStore.closeModal('share')
}

async function submit() {
    if (!selectedYears.value.length) return uiStore.showToast('Выберите период')
    isBaking.value = true
    try {
        const res = await api.post('bake_stats/', {
            config: {
                years: selectedYears.value,
                ...config.value
            }
        })
        close()
        const tg = window.Telegram?.WebApp
        if (tg) {
            tg.switchInlineQuery("share_" + res.id, ["users", "groups", "channels"])
        }
    } catch (e) {
        uiStore.showToast('Ошибка создания слепка')
    } finally { isBaking.value = false }
}
</script>