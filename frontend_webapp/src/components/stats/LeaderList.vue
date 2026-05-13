<script setup>
import { ref, computed } from 'vue'
import { icons } from '../../utils/icons'
import { plural } from '../../utils/helpers'

const props = defineProps({
  title: { type: String, required: true },
  icon: { type: String, required: true },
  iconColor: { type: String, default: 'var(--accent)' },
  data: { type: Object, required: true },
  unitForms: { type: Array, default: () => ['просмотр', 'просмотра', 'просмотров'] }
})

const activeTab = ref('series')
const currentItems = computed(() => props.data[activeTab.value] || [])
</script>

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
      <div v-for="(item, idx) in currentItems" :key="item.id" class="li li-clickable clickable">
        <div class="li-l">
          <span class="li-rank">{{ idx + 1 }}</span>
          <img v-if="item.photo_url" :src="item.photo_url" class="person-avatar" style="width:32px; height:32px;">
          <div v-else class="person-avatar" style="width:32px; height:32px; font-size:12px;">{{ item.name.charAt(0) }}</div>
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