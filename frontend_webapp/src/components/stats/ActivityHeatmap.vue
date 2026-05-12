<script setup>
import { computed } from 'vue'
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
  const dateStr = date.toISOString().split('T')[0]
  emit('cell-click', { date: dateStr, value })
}
</script>

<template>
  <div class="card hoverable anim-item">
    <div class="label more-pad">
      <div class="icon" style="color: #f85149;" v-html="icons.flame"></div>
      Интенсивность
    </div>

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
        ></div>
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