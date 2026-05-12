<template>
  <div 
    class="wl-folder-card" 
    :class="{ active: isActive && !isReorderMode }"
    :data-id="folder.id"
    @pointerdown="handlePointerDown"
    @pointerup="handlePointerUp"
    @click="handleClick"
  >
    <div v-if="isReorderMode" class="wl-delete-badge" @click.stop="emit('delete', folder.id)">
      <span v-html="icons.minus"></span>
    </div>
    
    <div class="wl-folder-inner">
      <div class="wl-folder-icon" :style="{ background: `${folder.color}20`, color: folder.color }">
        <span v-html="folderIcon"></span>
      </div>
      <div class="wl-folder-info">
        <div class="wl-folder-name">{{ folder.name }}</div>
        <div class="wl-folder-count">
          {{ folder.items.length }} {{ plural(folder.items.length, ['шоу', 'шоу', 'шоу']) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { icons } from '../../utils/icons'
import { plural } from '../../utils/helpers'

const props = defineProps({
  folder: { type: Object, required: true },
  isActive: { type: Boolean, default: false },
  isReorderMode: { type: Boolean, default: false }
})

const emit = defineEmits(['select', 'edit', 'delete'])

const folderIcon = computed(() => icons[props.folder.icon] || icons.folder)

let longPressTimer = null
const isLongPress = ref(false)

const handlePointerDown = () => {
  if (props.isReorderMode) return
  isLongPress.value = false
  longPressTimer = setTimeout(() => {
    isLongPress.value = true
    emit('edit', props.folder.id)
    if (window.navigator.vibrate) window.navigator.vibrate(50)
  }, 600)
}

const handlePointerUp = () => {
  clearTimeout(longPressTimer)
}

const handleClick = () => {
  if (!isLongPress.value && !props.isReorderMode) {
    emit('select', props.folder.id)
  }
}
</script>