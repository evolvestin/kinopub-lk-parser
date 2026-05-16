<template>
  <div class="bouncy-chart-container">
    <div class="bars-wrapper">
      <div 
        v-for="(val, idx) in data" 
        :key="idx" 
        class="bar-item-wrap"
        :class="{ 'is-empty': val === 0 }"
        @click="handleClick(idx)"
      >
        <div class="bar-touch-area">
          <div 
            class="bar-fill" 
            :style="{ 
              height: val > 0 ? ((val / maxValue) * 100) + '%' : '0%',
              minHeight: val > 0 ? '22px' : '0',
              background: getGradient(idx)
            }"
          >
            <span v-if="val > 0" class="bar-value">{{ val }}</span>
          </div>
        </div>
        <span class="bar-label">{{ labels[idx] }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  labels: { type: Array, required: true },
  data: { type: Array, required: true },
  palette: { type: [Array, String], default: 'var(--accent)' },
  showValues: { type: Boolean, default: true }
})

const emit = defineEmits(['node-click'])

const maxValue = computed(() => Math.max(...props.data, 1))

const getGradient = (idx) => {
  const baseColor = Array.isArray(props.palette) 
    ? props.palette[idx % props.palette.length] 
    : props.palette
  return `linear-gradient(to top, ${baseColor}, ${baseColor}dd)`
}

const handleClick = (idx) => {
  if (props.data[idx] > 0) {
    if (window.navigator.vibrate) window.navigator.vibrate(8)
    emit('node-click', idx)
  }
}
</script>

<style scoped>
.bouncy-chart-container {
  width: 100%;
  height: 220px;
  padding: 20px 4px 10px;
  display: flex;
  flex-direction: column;
}

.bars-wrapper {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  height: 100%;
  gap: clamp(4px, 2vw, 10px);
  padding-bottom: 28px;
}

.bar-item-wrap {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  cursor: pointer;
  min-width: 0;
  transition: transform 0.2s ease;
}

.bar-item-wrap.is-empty {
  cursor: default;
  pointer-events: none;
  opacity: 0.3;
}

.bar-touch-area {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.bar-fill {
  width: 100%;
  max-width: 36px;
  border-radius: 8px 8px 4px 4px;
  position: relative;
  transition: height 0.8s cubic-bezier(0.16, 1, 0.3, 1);
  will-change: height;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.bar-item-wrap:active:not(.is-empty) {
  transform: scale(0.94);
}

.bar-item-wrap:active:not(.is-empty) .bar-fill {
  filter: brightness(1.2);
}

.bar-label {
  position: absolute;
  bottom: -24px;
  font-size: 11px;
  font-weight: 800;
  color: var(--text-primary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  transition: color 0.2s ease;
}

.bar-value {
  font-size: 10px;
  font-weight: 900;
  color: var(--text-secondary);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
  pointer-events: none;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.2px;
  line-height: 1;
}
</style>