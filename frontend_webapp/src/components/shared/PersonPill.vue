<template>
  <div class="person-pill" @click="openPerson">
    <img 
      v-if="currentPhoto" 
      :src="currentPhoto" 
      class="person-avatar" 
      style="object-fit: cover;" 
      @error="handleError"
    >
    <div v-else class="person-avatar is-placeholder" v-html="icons.person_placeholder"></div>
    <div class="person-name">{{ person.name }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { icons } from '../../utils/icons'

const props = defineProps({
  person: {
    type: Object,
    required: true
  }
})

const currentPhoto = ref(null)
const hasFailedFallback = ref(false)

onMounted(() => {
  currentPhoto.value = props.person.photo_url
})

const handleError = (e) => {
  if (props.person.fallback_photo_url && !hasFailedFallback.value) {
    hasFailedFallback.value = true
    currentPhoto.value = props.person.fallback_photo_url
  } else {
    currentPhoto.value = null
  }
}

const openPerson = () => {
  console.log('Open person layer', props.person.id)
}
</script>