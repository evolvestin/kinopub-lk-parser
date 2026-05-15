<template>
  <div class="person-avatar" :class="{ 'is-placeholder': !currentUrl }">
    <img
      v-if="currentUrl"
      :src="currentUrl"
      @error="handleError"
      @load="handleLoad"
      :alt="name"
      loading="lazy"
    />
    <div v-else v-html="icons.person_placeholder"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { icons } from '../../utils/icons'

const props = defineProps({
  photoUrl: String,
  fallbackUrl: String,
  name: String
})

const currentUrl = ref(props.photoUrl || props.fallbackUrl)
const triedFallback = ref(false)

const handleLoad = (event) => {
  const img = event.target
  if (img.naturalWidth === 208 && img.naturalHeight === 304) {
    handleError()
  }
}

const handleError = () => {
  if (props.fallbackUrl && !triedFallback.value && currentUrl.value !== props.fallbackUrl) {
    triedFallback.value = true
    currentUrl.value = props.fallbackUrl
  } else {
    currentUrl.value = null
  }
}

watch(() => props.photoUrl, (newVal) => {
  currentUrl.value = newVal || props.fallbackUrl
  triedFallback.value = false
})

watch(() => props.fallbackUrl, (newVal) => {
  if (!currentUrl.value && !triedFallback.value) {
    currentUrl.value = newVal
  }
})
</script>