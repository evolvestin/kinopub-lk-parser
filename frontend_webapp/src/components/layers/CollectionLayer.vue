<template>
  <div class="layer-content">
    <div class="layer-header">
      <div style="flex-shrink: 0;">
        <button class="tab clickable" @click="uiStore.popLayer">
          <span v-html="icons.chevron_left"></span> Назад
        </button>
      </div>
      <div class="layer-header-center">
        <div class="layer-title-main">{{ title }}</div>
      </div>
      <div style="flex-shrink: 0; width: 80px;"></div>
    </div>

    <div v-if="loading" class="loader-inline">
      <div class="spinner"></div>
    </div>

    <div v-else class="hist-grid" style="padding: 0 16px;">
      <ShowCard v-for="item in items" :key="item.id" :show="item" />
      <div v-if="!items.length" class="empty">Пусто</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useUIStore } from '../../stores/uiStore'
import { useApi } from '../../composables/useApi'
import { icons } from '../../utils/icons'
import ShowCard from '../shared/ShowCard.vue'

const props = defineProps(['type', 'itemId'])
const uiStore = useUIStore()
const api = useApi()

const title = ref('Загрузка...')
const items = ref([])
const loading = ref(true)

const loadData = async () => {
  loading.value = true
  try {
    const data = await api.get(`collection/${props.type}/${props.itemId}/`)
    title.value = data.title
    items.value = data.items
  } catch (e) {
    uiStore.showToast('Ошибка загрузки коллекции')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
watch(() => props.itemId, loadData)
</script>