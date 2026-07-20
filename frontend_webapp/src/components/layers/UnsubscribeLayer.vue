<template>
  <div class="layer-content" v-if="show">
    <div class="layer-header">
       <button class="tab clickable" @click="goBack">
         <span v-html="icons.chevron_left"></span> Назад
       </button>
       <div class="layer-title-main">Уведомления</div>
    </div>

    <div class="hero-container">
      <div class="hero-bg" :style="{ backgroundImage: activeBg ? `url(${activeBg})` : 'none' }"></div>
      <div class="hero-gradient"></div>
      
      <div style="position: relative; z-index: 3; height: 95%; max-width: 85%; aspect-ratio: 2/3; display: flex; align-items: flex-end;">
        <img :src="activePoster" class="hero-poster" style="margin: 0; box-shadow: none;" alt="poster">
      </div>
    </div>

    <div class="show-info" style="margin-top: 20px;">
      <div class="show-title">{{ show.title }}</div>
      <div class="show-orig" v-if="show.original_title !== show.title">{{ show.original_title }}</div>
    </div>

    <div class="card anim-item" style="margin: 20px 16px; padding: 16px; border-radius: 20px;">
      <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
        <span style="font-size: 20px;">🔔</span>
        <span style="font-weight: 800; font-size: 15px; color: var(--text-primary);">Почему вы получили это уведомление?</span>
      </div>
      <div style="font-size: 14px; color: var(--text-secondary); line-height: 1.5; font-weight: 500;">
        <template v-if="show.reasons.includes('history') && show.reasons.includes('wishlist')">
          Это шоу находится в вашем <b>Избранном</b> и вы уже <b>смотрели его ранее</b>.
        </template>
        <template v-else-if="show.reasons.includes('wishlist')">
          Это шоу добавлено в ваши папки <b>Избранного</b>.
        </template>
        <template v-else-if="show.reasons.includes('history')">
          Вы ранее <b>отмечали просмотр</b> этого шоу в истории.
        </template>
        <template v-else>
          Вы подписаны на получение обновлений по этому шоу.
        </template>
      </div>
    </div>

    <div class="card anim-item" style="margin: 0 16px 20px; padding: 20px; border-radius: 20px; text-align: center;">
      <div style="font-size: 15px; font-weight: 700; color: var(--text-primary); margin-bottom: 16px;">
        Управление подпиской на новые серии
      </div>

      <div v-if="isMuted" class="anim-item">
        <div style="color: var(--danger); font-weight: 800; font-size: 14px; margin-bottom: 16px; display: flex; align-items: center; justify-content: center; gap: 8px;">
          <span>🔕</span> Уведомления отключены
        </div>
        <button class="btn-primary" :disabled="isToggling" @click="toggleMute(false)" style="margin-top: 0; background: var(--accent); box-shadow: var(--shadow-glow);">
          <div v-if="isToggling" class="spinner" style="width: 16px; height: 16px; border-color: rgba(255,255,255,0.3); border-top-color: #fff;"></div>
          <span v-else>🔔 Включить уведомления</span>
        </button>
      </div>

      <div v-else class="anim-item">
        <div style="color: var(--accent); font-weight: 800; font-size: 14px; margin-bottom: 16px; display: flex; align-items: center; justify-content: center; gap: 8px;">
          <span>🔔</span> Уведомления включены
        </div>
        <button class="btn-primary" :disabled="isToggling" @click="toggleMute(true)" style="margin-top: 0; background: var(--danger); box-shadow: 0 8px 24px rgba(231, 76, 60, 0.2);">
          <div v-if="isToggling" class="spinner" style="width: 16px; height: 16px; border-color: rgba(255,255,255,0.3); border-top-color: #fff;"></div>
          <span v-else>🔕 Отключить уведомления</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '../../composables/useApi'
import { useUIStore } from '../../stores/uiStore'
import { icons } from '../../utils/icons'
import { preloadImage } from '../../utils/helpers'

const props = defineProps({
  showId: {
    type: [String, Number],
    required: true
  }
})

const api = useApi()
const uiStore = useUIStore()
const router = useRouter()

const show = ref(null)
const activePoster = ref('')
const activeBg = ref('')
const isMuted = ref(false)
const isToggling = ref(false)

const goBack = () => {
  uiStore.popLayer()
}

const loadNotificationStatus = async () => {
  uiStore.setLoading(true)
  try {
    const data = await api.get(`show/${props.showId}/notification_status/`)
    show.value = data
    isMuted.value = data.is_muted

    activePoster.value = data.poster_medium || ''
    activeBg.value = data.poster_medium || ''

    if (data.title) {
      const query = { ...router.currentRoute.value.query }
      if (!query.q) {
        query.q = data.title
        router.replace({ query }).catch(() => {})
      }
    }

    if (data.poster_large) {
      preloadImage(data.poster_large).then(success => {
        if (success) {
          activePoster.value = data.poster_large
          activeBg.value = data.poster_large
        }
      })
    }
  } catch (e) {
    console.error('[UnsubscribeLayer] Error loading status:', e)
    uiStore.showToast('Ошибка загрузки данных')
    uiStore.popLayer()
  } finally {
    uiStore.setLoading(false)
  }
}

const toggleMute = async (muteValue) => {
  if (isToggling.value) return
  isToggling.value = true
  
  if (window.navigator.vibrate) {
    window.navigator.vibrate(10)
  }

  try {
    const data = await api.post('toggle_mute_notification/', {
      show_id: props.showId,
      mute: muteValue
    })
    isMuted.value = data.is_muted
    uiStore.showToast(data.message)
    delete uiStore.showsCache[props.showId]
  } catch (e) {
    console.error('[UnsubscribeLayer] Toggle mute error:', e)
    uiStore.showToast('Не удалось обновить статус подписки')
  } finally {
    isToggling.value = false
  }
}

onMounted(loadNotificationStatus)
</script>