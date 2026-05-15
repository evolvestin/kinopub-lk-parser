<template>
  <div class="card hoverable anim-item">
    <div class="label" style="justify-content: space-between; padding: 0 0 12px 0;">
      <div style="display: flex; align-items: center; gap: 8px;">
        <div class="icon" :style="{ color: iconColor }" v-html="icon"></div>{{ title }}
      </div>
      <div class="view-toggle" style="margin-bottom: 0; scale: 0.8; transform-origin: right;">
        <button class="vt-btn" :class="{ active: activeTab === 'series' }" @click="activeTab = 'series'">Сериалы</button>
        <button class="vt-btn" :class="{ active: activeTab === 'others' }" @click="activeTab = 'others'">Фильмы</button>
      </div>
    </div>

    <div v-if="currentItems.length">
      <div 
        v-for="(item, idx) in currentItems" 
        :key="item.id || idx" 
        class="li li-clickable clickable"
        @click="openItemHistory(item, idx)"
      >
        <div class="li-l">
          <span class="li-rank">{{ idx + 1 }}</span>
          
          <img 
            v-if="item.resolvedUrl" 
            :src="item.resolvedUrl" 
            class="person-avatar"
            style="object-fit: cover;"
          >
          <div v-else class="person-avatar is-placeholder" v-html="icons.person_placeholder"></div>

          <div style="min-width: 0;">
            <div class="li-name">{{ item.name }}</div>
            <div class="li-sub" v-if="item.sub">{{ item.sub }}</div>
          </div>
        </div>
        <span class="li-r" style="color: var(--info)">{{ item.count }} {{ plural(item.count, unitForms) }}</span>
      </div>
    </div>
    <div v-else class="empty" style="padding: 20px 0;"><div class="icon" v-html="icons.dash"></div>Нет данных</div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { icons } from '../../utils/icons'
import { plural } from '../../utils/helpers'
import { useUIStore } from '../../stores/uiStore'

const props = defineProps({
  category: { type: String, required: true },
  title: { type: String, required: true },
  icon: { type: String, required: true },
  iconColor: { type: String, default: 'var(--accent)' },
  data: { type: Object, required: true },
  unitForms: { type: Array, default: () => ['просмотр', 'просмотра', 'просмотров'] }
})

const uiStore = useUIStore()
const activeTab = ref('series')
const currentItems = computed(() => props.data[activeTab.value] || [])

const openItemHistory = (item, index) => {
    uiStore.openLayer('history', 'filter', {
        key: `${props.category}_${activeTab.value}`,
        idx: index,
        title: item.name
    })
}
</script>