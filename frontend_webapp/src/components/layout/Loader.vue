<template>
  <div v-if="isLoading" class="loader" id="loader">
    <div class="spinner"></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useUIStore } from '../../stores/uiStore'

const uiStore = useUIStore()
const isLoading = computed(() => uiStore.isLoading)
</script>