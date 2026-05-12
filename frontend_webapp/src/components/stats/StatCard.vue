<template>
  <div class="stat anim-item" :class="{ 'clickable': clickable }" @click="handleClick">
    <div class="stat-icon" v-html="icon"></div>
    <div class="stat-val">{{ value }}</div>
    <div class="stat-lbl">{{ label }}</div>
    <div v-if="subValue" class="stat-sub" :style="subStyles">
      {{ subValue }} {{ subLabel }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  icon: { type: String, required: true },
  value: { type: [String, Number], required: true },
  label: { type: String, required: true },
  subValue: { type: [String, Number], default: '' },
  subLabel: { type: String, default: '' },
  subColorClass: { type: String, default: '' },
  clickable: { type: Boolean, default: false }
})

const emit = defineEmits(['click'])

const subStyles = computed(() => {
  if (props.subColorClass === 'info') return 'background: var(--info-dim); color: var(--info);'
  if (props.subColorClass === 'purple') return 'background: rgba(163, 113, 247, 0.15); color: #a371f7;'
  if (props.subColorClass === 'orange') return 'background: rgba(210, 153, 34, 0.15); color: #d29922;'
  return ''
})

const handleClick = () => {
  if (props.clickable) {
    emit('click')
  }
}
</script>