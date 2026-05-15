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
import { ref, watch, onBeforeMount } from 'vue'
import { icons } from '../../utils/icons'
import { isImageBroken, markImageAsBroken } from '../../utils/helpers'

const props = defineProps({
  photoUrl: String,
  fallbackUrl: String,
  name: String
})

const currentUrl = ref(null)
const triedFallback = ref(false)

const initUrl = () => {
  // Если основная ссылка уже помечена как битая, сразу берем fallback
  if (props.photoUrl && !isImageBroken(props.photoUrl)) {
    currentUrl.value = props.photoUrl
    triedFallback.value = false
  } else if (props.fallbackUrl && !isImageBroken(props.fallbackUrl)) {
    currentUrl.value = props.fallbackUrl
    triedFallback.value = true
  } else {
    currentUrl.value = null
  }
}

onBeforeMount(initUrl)

const handleLoad = (event) => {
  const img = event.target
  // Проверка на фейковую заглушку Кинопоиска
  if (img.naturalWidth === 208 && img.naturalHeight === 304) {
    handleError()
  }
}

const handleError = () => {
  if (currentUrl.value) {
    markImageAsBroken(currentUrl.value)
  }

  if (props.fallbackUrl && !triedFallback.value && currentUrl.value !== props.fallbackUrl) {
    triedFallback.value = true
    if (!isImageBroken(props.fallbackUrl)) {
      currentUrl.value = props.fallbackUrl
    } else {
      currentUrl.value = null
    }
  } else {
    currentUrl.value = null
  }
}

watch(() => props.photoUrl, initUrl)
</script>