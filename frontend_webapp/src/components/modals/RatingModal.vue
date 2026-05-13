<template>
  <div class="modal-overlay show" @click.self="emit('close')">
    <div class="modal-content" :class="scoreColorClass">
      <div id="rate-nav-bar">
        <div id="rate-breadcrumb">Оценка контента</div>
      </div>

      <div class="show-title" style="margin: 12px 0; font-size: 20px;">{{ title }}</div>
      
      <div class="rate-container">
        <div class="rate-score-display">
          <div class="rate-score-huge">{{ displayValue }}<span>/ 10</span></div>
        </div>
        
        <div class="rate-slider-wrap" ref="sliderRef" @pointerdown="startDrag">
          <div class="rate-slider-track">
            <div class="rate-slider-fill" :style="{ width: percent + '%' }"></div>
            <div class="rate-slider-handle" :style="{ left: percent + '%' }"></div>
          </div>
          <div class="rate-scale-labels">
            <span v-for="n in 10" :key="n">{{ n }}</span>
          </div>
        </div>
      </div>

      <div style="display: flex; gap: 12px; margin-top: 20px;">
        <button class="btn-primary" style="background: var(--bg-input); color: var(--danger); flex: 1;" @click="deleteRating">Удалить</button>
        <button class="btn-primary" style="flex: 2;" :disabled="isSaving" @click="saveRating">
          <div v-if="isSaving" class="spinner" style="width:16px;height:16px;"></div>
          <span v-else>Сохранить</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useApi } from '../../composables/useApi'
import { useUIStore } from '../../stores/uiStore'

const props = defineProps(['showId', 'title', 'initialValue', 'type'])
const emit = defineEmits(['close', 'saved'])
const api = useApi()
const uiStore = useUIStore()

const val = ref(parseFloat(props.initialValue) || 5.0)
const isSaving = ref(false)
const sliderRef = ref(null)

const percent = computed(() => ((val.value - 1) / 9) * 100)
const displayValue = computed(() => val.value.toFixed(val.value % 1 === 0 ? 0 : 1))

const scoreColorClass = computed(() => {
  if (val.value < 5) return 'score-low'
  if (val.value < 8) return 'score-mid'
  return 'score-high'
})

const startDrag = (e) => {
  const move = (event) => {
    const rect = sliderRef.value.getBoundingClientRect()
    const clientX = event.clientX || (event.touches ? event.touches[0].clientX : 0)
    let p = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
    let newVal = Math.round((1 + (p * 9)) * 2) / 2
    if (newVal !== val.value) {
      if (window.navigator.vibrate) window.navigator.vibrate(5)
      val.value = newVal
    }
  }
  const stop = () => {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', stop)
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', stop)
  move(e)
}

async function saveRating() {
  isSaving.value = true
  try {
    await api.post('rate/', { show_id: props.showId, rating: val.value })
    uiStore.showToast('Оценка сохранена')
    emit('saved')
    emit('close')
  } catch (e) { uiStore.showToast('Ошибка API') }
  finally { isSaving.value = false }
}

async function deleteRating() {
  if (!confirm('Удалить оценку?')) return
  try {
    await api.post('delete_rating/', { show_id: props.showId })
    emit('saved')
    emit('close')
  } catch (e) { uiStore.showToast('Ошибка удаления') }
}
</script>

<style scoped>
@import '../../../../kinopub_parser/static/css/rating.css';
</style>