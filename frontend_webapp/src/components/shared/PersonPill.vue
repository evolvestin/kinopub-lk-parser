<template>
  <div class="person-pill" @click="openPerson">
    <PersonAvatar 
      :photo-url="person.photo_url" 
      :fallback-url="person.fallback_photo_url"
      :name="person.name"
    />
    <div class="person-name">{{ person.name }}</div>
  </div>
</template>

<script setup>
import { useUIStore } from '../../stores/uiStore'
import PersonAvatar from './PersonAvatar.vue'

const props = defineProps({
  person: { type: Object, required: true }
})

const uiStore = useUIStore()
const openPerson = () => uiStore.openLayer('person', props.person.id)
</script>