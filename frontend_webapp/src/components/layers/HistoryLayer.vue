<template>
  <div class="layer-content">
    <div class="layer-header" :class="{ 'has-group': isSticky }">
      <div>
        <button class="tab clickable" @click="uiStore.popLayer">
          <span v-html="icons.chevron_left"></span> Назад
        </button>
      </div>
      <div class="layer-header-center">
        <div class="layer-title-main">{{ title }}</div>
        <div class="layer-group-label">{{ stickyLabel }}</div>
      </div>
      <div class="view-toggle">
         <button class="vt-btn" :class="{ active: mode === 'grid' }" @click="mode = 'grid'" v-html="icons.grid"></button>
         <button class="vt-btn" :class="{ active: mode === 'list' }" @click="mode = 'list'" v-html="icons.list"></button>
      </div>
    </div>

    <div class="hist-container" :class="mode === 'grid' ? 'hist-grid' : 'card-list-wrapper'">
      <template v-for="(item, idx) in visibleList" :key="item.id">
        <div v-if="shouldShowDivider(item, idx)" class="hist-group-divider">
           <span class="hist-group-divider-text">{{ getGroupKey(item) }}</span>
        </div>
        <ShowCard :show="item" :view-mode="mode" />
      </template>
      <div ref="sentinel" style="height: 20px;"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useUIStore } from '../../stores/uiStore'
import { icons } from '../../utils/icons'
import ShowCard from '../shared/ShowCard.vue'

const props = defineProps(['title', 'items'])
const uiStore = useUIStore()
const mode = ref('grid')
const offset = ref(50)
const sentinel = ref(null)

const visibleList = computed(() => props.items.slice(0, offset.value))

const getGroupKey = (item) => {
  const d = new Date(item.view_date)
  return `${d.getFullYear()}`
}

const shouldShowDivider = (item, idx) => {
  if (idx === 0) return true
  return getGroupKey(item) !== getGroupKey(props.items[idx - 1])
}

onMounted(() => {
  const obs = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) offset.value += 50
  })
  if (sentinel.value) obs.observe(sentinel.value)
})
</script>