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
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUIStore } from '../../stores/uiStore'
import { useStatsStore } from '../../stores/useStatsStore'
import { useApi } from '../../composables/useApi'
import { icons } from '../../utils/icons'

const uiStore = useUIStore()
const statsStore = useStatsStore()
const api = useApi()
const router = useRouter()

const isBaking = ref(false)

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

const selectedYears = computed({
  get: () => {
    const y = router.currentRoute.value.query.modal_years
    return y ? y.split(',') : ['all']
  },
  set: (val) => updateQueryParams({ years: val.join(',') })
})

const config = computed(() => {
  const query = router.currentRoute.value.query
  return {
    get anon_user() { return query.modal_anon_user === 'true' },
    set anon_user(val) { updateQueryParams({ anon_user: val }) },
    get include_group() { return query.modal_include_group !== 'false' },
    set include_group(val) { updateQueryParams({ include_group: val }) },
    get anon_group() { return query.modal_anon_group === 'true' },
    set anon_group(val) { updateQueryParams({ anon_group: val }) }
  }
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
      tg.switchInlineQuery('share_' + res.id, ['users', 'groups', 'channels'])
    }
  } catch (e) {
    uiStore.showToast('Ошибка создания слепка')
  } finally {
    isBaking.value = false
  }
}
</script>