<template>
  <div class="person-pill" @click="openPerson">
    <img 
      v-if="person.resolvedUrl" 
      :src="person.resolvedUrl" 
      class="person-avatar" 
      style="object-fit: cover;"
    >
    <div v-else class="person-avatar is-placeholder" v-html="icons.person_placeholder"></div>
    <div class="person-name">{{ person.name }}</div>
  </div>
</template>

<script setup>
import { icons } from '../../utils/icons'
import { useUIStore } from '../../stores/uiStore'

const props = defineProps({
  person: { type: Object, required: true }
})

const uiStore = useUIStore()
const openPerson = () => uiStore.openLayer('person', props.person.id)
</script>