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

    <template v-else>
      <!-- КАРТОЧКА ПЕРСОНЫ В КОЛЛЕКЦИИ -->
      <div v-if="personInfo" 
           class="card anim-item" 
           style="display:flex; align-items:center; gap:16px; margin:12px 16px; padding:16px; border-radius:20px;">
          <PersonAvatar 
            :photo-url="personInfo.photo_url" 
            :fallback-url="personInfo.fallback_photo_url"
            :name="title"
            style="width:60px; height:60px;"
          />
          <div style="min-width:0; flex:1;">
              <div style="font-size:20px; font-weight:900; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; letter-spacing:-0.5px;">{{ title }}</div>
              <div v-if="personInfo.professions?.length" style="font-size:13px; color:var(--text-muted); font-weight:600; margin-top:4px; letter-spacing:0.3px;">
                  {{ personInfo.professions.join(' · ') }}
              </div>
          </div>
      </div>

      <div class="hist-grid" style="padding: 0 16px;">
        <ShowCard v-for="item in items" :key="item.id" :show="item" />
        <div v-if="!items.length" class="empty">Пусто</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useUIStore } from '../../stores/uiStore'
import { useApi } from '../../composables/useApi'
import { icons } from '../../utils/icons'
import { preloadImage } from '../../utils/helpers'
import ShowCard from '../shared/ShowCard.vue'
import PersonAvatar from '../shared/PersonAvatar.vue'

const props = defineProps(['type', 'itemId'])
const uiStore = useUIStore()
const api = useApi()

const title = ref('Загрузка...')
const items = ref([])
const personInfo = ref(null)
const loading = ref(true)

const loadData = async () => {
  loading.value = true
  try {
    const data = await api.get(`collection/${props.type}/${props.itemId}/`)
    title.value = data.title
    items.value = data.items
    personInfo.value = data.person_info

    if (data.items) {
      data.items.forEach(item => {
        if (item.poster_url) preloadImage(item.poster_url)
      })
    }
  } catch (e) {
    console.error('[CollectionLayer] Failed to load collection:', e)
    uiStore.showToast('Ошибка загрузки коллекции')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
watch(() => props.itemId, loadData)
</script>