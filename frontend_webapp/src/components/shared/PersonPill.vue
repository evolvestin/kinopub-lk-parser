<template>
  <div class="person-pill" @click="openPerson">
    <img 
      v-if="currentPhoto" 
      :src="currentPhoto" 
      class="person-avatar" 
      style="object-fit: cover;" 
      @error="handleError"
      @load="handleLoad"
    >
    <div v-else class="person-avatar is-placeholder" v-html="icons.person_placeholder"></div>
    <div class="person-name">{{ person.name }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { icons } from '../../utils/icons'
import { useUIStore } from '../../stores/uiStore'

const props = defineProps({
  person: {
    type: Object,
    required: true
  }
})

const uiStore = useUIStore()
const currentPhoto = ref(null)
const hasFailedFallback = ref(false)

const updatePhoto = () => {
  currentPhoto.value = props.person.photo_url
  hasFailedFallback.value = false
}

onMounted(updatePhoto)
watch(() => props.person.photo_url, updatePhoto)

const handleLoad = (e) => {
  const img = e.target
  if (img.naturalWidth === 208 && img.naturalHeight === 304) {
    currentPhoto.value = null
  }
}

const handleError = () => {
  if (props.person.fallback_photo_url && !hasFailedFallback.value) {
    hasFailedFallback.value = true
    currentPhoto.value = props.person.fallback_photo_url
  } else {
    currentPhoto.value = null
  }
}

const openPerson = () => {
  uiStore.openLayer('person', props.person.id)
}
</script>