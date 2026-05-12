<template>
  <div class="toast" :class="{ 'show': toastData.visible }">
    {{ toastData.text }}
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useUIStore } from '../../stores/uiStore'

const uiStore = useUIStore()
const toastData = computed(() => uiStore.toast)
</script>