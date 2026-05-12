<template>
  <div class="empty">
    <div class="icon" style="font-size: 48px; opacity: 0.3; margin-bottom: 16px;" v-html="iconHtml"></div>
    {{ text }}
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { icons } from '../../utils/icons'

const props = defineProps({
  icon: {
    type: String,
    required: true
  },
  text: {
    type: String,
    required: true
  }
})

const iconHtml = computed(() => icons[props.icon] || '')
</script>