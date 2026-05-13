<template>
  <div class="stat anim-item" :class="{ 'clickable': clickable }" @click="handleClick">
    <div class="stat-icon" v-html="icon"></div>
    <div class="stat-val">{{ value }}</div>
    <div class="stat-lbl">{{ label }}</div>
    <div v-if="subValue !== undefined" class="stat-sub" :class="subColorClass">
      {{ subValue }} {{ subLabel }}
    </div>
  </div>
</template>

<script setup>
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
const handleClick = () => props.clickable && emit('click')
</script>

<style scoped>
.stat-sub.info { background: var(--info-dim); color: var(--info); }
.stat-sub.purple { background: rgba(163, 113, 247, 0.15); color: #a371f7; }
.stat-sub.orange { background: rgba(210, 153, 34, 0.15); color: #d29922; }
</style>