<template>
  <div class="layer-content" ref="containerEl">
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

    <div v-if="loading && items.length === 0" class="loader-inline">
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

      <div v-if="loadingMore" class="loader-inline" style="padding: 20px;">
        <div class="spinner" style="width: 24px; height: 24px;"></div>
      </div>

      <div ref="sentinelEl" style="height: 40px; width: 100%; pointer-events: none;"></div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
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
const loadingMore = ref(false)
const hasMore = ref(true)
const offset = ref(0)
const limit = 50

const containerEl = ref(null)
const sentinelEl = ref(null)
let observer = null

const loadData = async (isLoadMore = false) => {
  if (isLoadMore) {
    loadingMore.value = true
  } else {
    loading.value = true
    offset.value = 0
    items.value = []
    hasMore.value = true
  }

  try {
    const data = await api.get(`collection/${props.type}/${props.itemId}/?offset=${offset.value}&limit=${limit}`)
    title.value = data.title
    personInfo.value = data.person_info
    hasMore.value = data.has_more

    const newItems = data.items || []
    if (isLoadMore) {
      items.value.push(...newItems)
    } else {
      items.value = newItems
    }

    if (newItems.length) {
      newItems.forEach(item => {
        if (item.poster_url) preloadImage(item.poster_url)
      })
    }
  } catch (e) {
    console.error('[CollectionLayer] Failed to load collection:', e)
    uiStore.showToast('Ошибка загрузки коллекции')
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

const loadMore = async () => {
  if (loading.value || loadingMore.value || !hasMore.value) return
  offset.value += limit
  await loadData(true)
}

const setupObserver = () => {
  if (observer) observer.disconnect()
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore.value && !loading.value && !loadingMore.value) {
      loadMore()
    }
  }, {
    root: containerEl.value,
    rootMargin: '400px'
  })

  if (sentinelEl.value) {
    observer.observe(sentinelEl.value)
  }
}

onMounted(async () => {
  await loadData()
  nextTick(setupObserver)
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})

watch(() => props.itemId, async () => {
  await loadData()
  nextTick(setupObserver)
})
</script>