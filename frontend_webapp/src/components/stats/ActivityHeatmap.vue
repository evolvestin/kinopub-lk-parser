<template>
  <div class="card hoverable anim-item">
    <div class="label more-pad">
      <div class="icon" style="color: #f85149;" v-html="icons.flame"></div>
      Интенсивность
    </div>

    <div 
      class="hm-viewport" 
      ref="viewportRef" 
      :style="{ touchAction: touchActionStyle }"
      @touchstart="handleTouchStart" 
      @touchmove="handleTouchMove" 
      @touchend="handleTouchEnd"
    >
      <div class="hm-zoom-content" :style="zoomStyle">
        <div class="hm-wrapper" v-for="item in yearsData" :key="item.year">
          <div v-if="yearsData.length > 1" class="li-sub" style="margin-bottom: 8px; font-weight: 800;">
            {{ item.year }}
          </div>
          
          <div class="hm" :style="{ gridTemplateColumns: `max-content repeat(${Math.ceil((getYearMeta(item.year).offset + item.data.length) / 7)}, 1fr)` }">
            <div v-for="lbl in dayLabels" :key="lbl" class="hc-label">{{ lbl }}</div>
            
            <div 
              v-for="n in getYearMeta(item.year).offset" 
              :key="'off-' + n" 
              class="hc" 
              style="opacity: 0; pointer-events: none;"
            ></div>

            <div 
              v-for="(val, idx) in item.data" 
              :key="idx"
              class="hc clickable"
              :class="getIntensityClass(val)"
              :title="formatTitleDate(item.year, idx)"
              @click="handleCellClick(item.year, idx, val)"
              @touchstart="handleCellTouchStart"
              @touchend.prevent="handleCellTouchEnd($event, item.year, idx, val)"
            ></div>
          </div>
        </div>
      </div>
    </div>

    <div class="hm-leg">
      <span>Меньше</span>
      <div class="hc"></div>
      <div class="hc hm-l1"></div>
      <div class="hc hm-l2"></div>
      <div class="hc hm-l3"></div>
      <div class="hc hm-l4"></div>
      <span>Больше</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { icons } from '../../utils/icons'

const props = defineProps({
  yearsData: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['cell-click'])

const dayLabels = ['Пн', '', 'Ср', '', 'Пт', '', 'Вс']

const getIntensityClass = (value) => {
  if (!value) return ''
  return `hm-l${value}`
}

const formatTitleDate = (year, dayIndex) => {
  const date = new Date(year, 0, 1)
  date.setDate(date.getDate() + dayIndex)
  return date.toLocaleDateString('ru-RU')
}

const getYearMeta = (year) => {
  const firstDay = new Date(year, 0, 1).getDay()
  const offset = (firstDay + 6) % 7
  return { offset }
}

const handleCellClick = (year, dayIndex, value) => {
  const date = new Date(year, 0, 1)
  date.setDate(date.getDate() + dayIndex)
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const dateStr = `${y}-${m}-${d}`
  emit('cell-click', { date: dateStr, value })
}

const viewportRef = ref(null)
const scale = ref(1)
const translateX = ref(0)
const translateY = ref(0)

const isZooming = ref(false)
const isPanning = ref(false)

let startDist = 0
let startScale = 1
let startMidX = 0
let startMidY = 0
let startTranslateX = 0
let startTranslateY = 0

let cellTouchStartX = 0
let cellTouchStartY = 0

const handleCellTouchStart = (e) => {
  const touch = e.touches[0]
  cellTouchStartX = touch.clientX
  cellTouchStartY = touch.clientY
}

const handleCellTouchEnd = (e, year, dayIndex, value) => {
  const touch = e.changedTouches[0]
  const distX = Math.abs(touch.clientX - cellTouchStartX)
  const distY = Math.abs(touch.clientY - cellTouchStartY)
  
  if (distX < 10 && distY < 10) {
    handleCellClick(year, dayIndex, value)
  }
}

const touchActionStyle = computed(() => {
  return scale.value > 1.05 ? 'none' : 'pan-y'
})

const zoomStyle = computed(() => ({
  transform: `translate3d(${translateX.value}px, ${translateY.value}px, 0) scale(${scale.value})`,
  transformOrigin: '0 0',
  transition: isZooming.value || isPanning.value ? 'none' : 'transform 0.25s cubic-bezier(0.2, 0.8, 0.2, 1)'
}))

const handleTouchStart = (e) => {
  const t = e.touches
  if (t.length === 1) {
    if (scale.value > 1.05) {
      isPanning.value = true
      isZooming.value = false
      startMidX = t[0].clientX
      startMidY = t[0].clientY
      startTranslateX = translateX.value
      startTranslateY = translateY.value
    }
  } else if (t.length === 2) {
    isZooming.value = true
    isPanning.value = false
    startDist = Math.hypot(t[1].clientX - t[0].clientX, t[1].clientY - t[0].clientY)
    startScale = scale.value
    startMidX = (t[0].clientX + t[1].clientX) / 2
    startMidY = (t[0].clientY + t[1].clientY) / 2
    startTranslateX = translateX.value
    startTranslateY = translateY.value
  }
}

const handleTouchMove = (e) => {
  const t = e.touches
  const rect = viewportRef.value ? viewportRef.value.getBoundingClientRect() : null
  if (!rect) return

  if (isZooming.value && t.length === 2) {
    e.preventDefault()
    const currentDist = Math.hypot(t[1].clientX - t[0].clientX, t[1].clientY - t[0].clientY)
    const newScale = Math.min(Math.max(1, (currentDist / startDist) * startScale), 4)
    const currentMidX = (t[0].clientX + t[1].clientX) / 2
    const currentMidY = (t[0].clientY + t[1].clientY) / 2
    const mouseX = startMidX - rect.left
    const mouseY = startMidY - rect.top
    const scaleRatio = newScale / startScale
    
    translateX.value = currentMidX - rect.left - (mouseX - startTranslateX) * scaleRatio
    translateY.value = currentMidY - rect.top - (mouseY - startTranslateY) * scaleRatio
    scale.value = newScale
  } else if (isPanning.value && t.length === 1 && scale.value > 1.05) {
    e.preventDefault()
    const deltaX = t[0].clientX - startMidX
    const deltaY = t[0].clientY - startMidY
    let targetX = startTranslateX + deltaX
    let targetY = startTranslateY + deltaY

    const contentWidth = viewportRef.value.offsetWidth
    const contentHeight = viewportRef.value.offsetHeight
    const minX = rect.width - (contentWidth * scale.value)
    const minY = rect.height - (contentHeight * scale.value)
    
    translateX.value = Math.min(0, Math.max(minX, targetX))
    translateY.value = Math.min(0, Math.max(minY, targetY))
  }
}

const handleTouchEnd = (e) => {
  if (e.touches.length === 0) {
    isZooming.value = false
    isPanning.value = false
    if (scale.value < 1.05) {
      scale.value = 1
      translateX.value = 0
      translateY.value = 0
    }
  } else if (e.touches.length === 1) {
    isZooming.value = false
    if (scale.value > 1.05) {
      isPanning.value = true
      startMidX = e.touches[0].clientX
      startMidY = e.touches[0].clientY
      startTranslateX = translateX.value
      startTranslateY = translateY.value
    }
  }
}
</script>

<style scoped>
.hm-viewport {
  width: 100%;
  overflow: hidden;
  position: relative;
}
.hm-zoom-content {
  width: 100%;
  will-change: transform;
}
</style>