<template>
  <div class="modal-overlay show" @click.self="close">
    <div class="modal-content" style="padding: 24px; position: relative;">
      <div class="modal-title" style="font-size: 14px; opacity: 0.7; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; text-align: center; margin-bottom: 8px;">
        Отметить просмотр
      </div>
      <div style="font-size: clamp(18px, 5vw, 22px); font-weight: 900; color: var(--accent); margin-bottom: 24px; line-height: 1.2; text-align: center; letter-spacing: -0.5px;">
        {{ context.title }}
      </div>

      <div v-if="isSeries" style="display: flex; gap: 12px; margin-bottom: 20px;">
        <div style="flex: 1;">
          <div style="font-size: 12px; color: var(--text-muted); font-weight: 700; margin-bottom: 6px; text-transform: uppercase;">Сезон</div>
          <input type="number" v-model="season" class="search-input" placeholder="1" min="1" />
        </div>
        <div style="flex: 1;">
          <div style="font-size: 12px; color: var(--text-muted); font-weight: 700; margin-bottom: 6px; text-transform: uppercase;">Эпизод</div>
          <input type="number" v-model="episode" class="search-input" placeholder="1" min="1" />
        </div>
      </div>

      <div style="font-size: 12px; color: var(--text-muted); font-weight: 700; margin-bottom: 8px; text-transform: uppercase;">Когда смотрели?</div>
      <div class="view-toggle" style="margin-bottom: 16px; padding: 3px; background: var(--bg-input);">
        <button class="vt-btn" :class="{ active: dateMode === 'exact' }" @click="dateMode = 'exact'">Точная дата</button>
        <button class="vt-btn" :class="{ active: dateMode === 'month' }" @click="dateMode = 'month'">Месяц</button>
        <button class="vt-btn" :class="{ active: dateMode === 'year' }" @click="dateMode = 'year'">Год</button>
        <button class="vt-btn" :class="{ active: dateMode === 'unknown' }" @click="dateMode = 'unknown'">Не помню</button>
      </div>

      <div style="margin-bottom: 24px;">
        <input v-if="dateMode === 'exact'" type="date" v-model="exactDate" class="search-input" style="width: 100%;" />
        <input v-if="dateMode === 'month'" type="month" v-model="monthDate" class="search-input" style="width: 100%;" />
        <input v-if="dateMode === 'year'" type="number" v-model="yearDate" class="search-input" placeholder="YYYY" style="width: 100%;" min="1900" max="2100" />
        <div v-if="dateMode === 'unknown'" style="font-size: 13px; color: var(--text-secondary); text-align: center; padding: 10px; background: var(--bg-input); border-radius: 12px; border: 1px dashed var(--border);">
          Просмотр будет учтен в статистике "Всё время" и закреплен в самом низу истории.
        </div>
      </div>

      <div style="display: flex; gap: 12px;">
        <button class="btn-primary" style="margin-top: 0; background: var(--bg-input); color: var(--text-primary); box-shadow: none; flex: 1;" @click="close">
          Отмена
        </button>
        <button class="btn-primary" style="margin-top: 0; flex: 2;" :disabled="isSaving" @click="save">
          <div v-if="isSaving" class="spinner" style="width: 16px; height: 16px;"></div>
          <span v-else>Сохранить</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useUIStore } from '../../stores/uiStore'
import { useApi } from '../../composables/useApi'

const uiStore = useUIStore()
const api = useApi()

const context = computed(() => uiStore.modals.addView.context || {})
const isSeries = computed(() => ['Series', 'Documentary Series', 'TV Show'].includes(context.value.type))

const season = ref(1)
const episode = ref(1)
const dateMode = ref('exact')
const exactDate = ref(new Date().toISOString().split('T')[0])
const monthDate = ref(new Date().toISOString().substring(0, 7))
const yearDate = ref(new Date().getFullYear())
const isSaving = ref(false)

const close = () => {
  uiStore.closeModal('addView')
}

const save = async () => {
  if (isSeries.value && (!season.value || !episode.value)) {
    uiStore.showToast('Укажите сезон и эпизод')
    return
  }

  let dateVal = null
  if (dateMode.value === 'exact') dateVal = exactDate.value
  if (dateMode.value === 'month') dateVal = monthDate.value
  if (dateMode.value === 'year') dateVal = yearDate.value

  isSaving.value = true
  try {
    await api.post('add_view/', {
      show_id: context.value.showId,
      season: isSeries.value ? season.value : 0,
      episode: isSeries.value ? episode.value : 0,
      date_mode: dateMode.value,
      date_val: dateVal
    })
    uiStore.showToast('Просмотр добавлен!')
    close()
  } catch (e) {
    uiStore.showToast('Ошибка сохранения')
  } finally {
    isSaving.value = false
  }
}
</script>