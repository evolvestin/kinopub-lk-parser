<template>
  <div
    v-if="isBroken"
    v-bind="attrs"
    class="poster-placeholder"
    role="img"
    :aria-label="alt || 'Постер отсутствует'"
  >
    <span v-html="placeholder"></span>
  </div>
  <img
    v-else
    v-bind="attrs"
    :src="currentSrc"
    :alt="alt"
    @load="validateImage"
    @error="handleError"
  >
</template>

<script setup>
import { ref, useAttrs, watch } from 'vue'
import { icons } from '../../utils/icons'
import { isImageBroken, markImageAsBroken } from '../../utils/helpers'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  src: { type: String, default: '' },
  alt: { type: String, default: '' },
  placeholder: { type: String, default: icons.film }
})

const attrs = useAttrs()
const currentSrc = ref('')
const isBroken = ref(false)

const reset = () => {
  currentSrc.value = props.src || ''
  isBroken.value = !currentSrc.value || isImageBroken(currentSrc.value)
}

reset()
watch(() => props.src, reset)

const handleError = () => {
  if (currentSrc.value) markImageAsBroken(currentSrc.value)
  isBroken.value = true
}

const validateImage = (event) => {
  if (event.target.naturalWidth === 208 && event.target.naturalHeight === 304) {
    handleError()
  }
}
</script>

<style scoped>
.poster-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  background: var(--bg-input, var(--bg-main));
}

.poster-placeholder span {
  display: inline-flex;
  opacity: 0.55;
}

.poster-placeholder span :deep(svg) {
  width: 60%;
  height: 60%;
}
</style>
