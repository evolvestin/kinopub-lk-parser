<template>
  <div class="layer-content" v-if="show" ref="containerRef">
    <div class="layer-header" ref="headerRef">
       <button class="tab clickable" @click="goBack">
         <span v-html="icons.chevron_left"></span> Назад
       </button>
       <div class="layer-title-main">Уведомления</div>
    </div>

    <div class="unsub-content-wrap">
      <div class="hero-container unsub-hero-container" :style="{ height: posterHeight }">
        <div class="hero-bg" :style="{ backgroundImage: activeBg ? `url(${activeBg})` : 'none' }"></div>
        <div class="hero-gradient"></div>
        
        <div style="position: relative; z-index: 3; height: 95%; max-width: 85%; aspect-ratio: 2/3; display: flex; align-items: flex-end;">
          <img :src="activePoster" class="hero-poster" style="margin: 0; box-shadow: none;" alt="poster">
        </div>
      </div>

      <div class="show-info unsub-show-info" ref="infoRef">
        <div class="show-title">{{ show.title }}</div>
        <div class="show-orig" v-if="show.original_title !== show.title">{{ show.original_title }}</div>
      </div>

      <div class="card anim-item unsub-card" ref="card1Ref">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
          <span style="font-size: 18px;">🔔</span>
          <span style="font-weight: 800; font-size: 14px; color: var(--text-primary);">Почему вы получили это уведомление?</span>
        </div>
        <div style="font-size: 13px; color: var(--text-secondary); line-height: 1.4; font-weight: 500;">
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

      <div class="card anim-item unsub-card" ref="card2Ref" style="text-align: center;">
        <div style="font-size: 14px; font-weight: 800; color: var(--text-primary); margin-bottom: 10px;">
          Управление подпиской на новые серии
        </div>

        <div v-if="isMuted" class="anim-item">
          <div style="color: var(--danger); font-weight: 800; font-size: 13px; margin-bottom: 10px; display: flex; align-items: center; justify-content: center; gap: 6px;">
            <span>🔕</span> Уведомления отключены
          </div>
          <button class="btn-primary unsub-btn" :disabled="isToggling" @click="toggleMute(false)" style="background: var(--accent); box-shadow: var(--shadow-glow);">
            <div v-if="isToggling" class="spinner" style="width: 16px; height: 16px; border-color: rgba(255,255,255,0.3); border-top-color: #fff;"></div>
            <span v-else>🔔 Включить уведомления</span>
          </button>
        </div>

        <div v-else class="anim-item">
          <div style="color: var(--accent); font-weight: 800; font-size: 13px; margin-bottom: 10px; display: flex; align-items: center; justify-content: center; gap: 6px;">
            <span>🔔</span> Уведомления включены
          </div>
          <button class="btn-primary unsub-btn" :disabled="isToggling" @click="toggleMute(true)" style="background: var(--danger); box-shadow: 0 8px 24px rgba(231, 76, 60, 0.2);">
            <div v-if="isToggling" class="spinner" style="width: 16px; height: 16px; border-color: rgba(255,255,255,0.3); border-top-color: #fff;"></div>
            <span v-else>🔕 Отключить уведомления</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
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

const containerRef = ref(null)
const headerRef = ref(null)
const infoRef = ref(null)
const card1Ref = ref(null)
const card2Ref = ref(null)
const posterHeight = ref('180px')

const goBack = () => {
  uiStore.popLayer()
}

const calculatePosterHeight = () => {
  if (
    !containerRef.value ||
    !headerRef.value ||
    !infoRef.value ||
    !card1Ref.value ||
    !card2Ref.value
  ) {
    return
  }

  const containerHeight = containerRef.value.clientHeight

  const headerHeight = headerRef.value.offsetHeight
  const infoHeight = infoRef.value.offsetHeight
  const card1Height = card1Ref.value.offsetHeight
  const card2Height = card2Ref.value.offsetHeight

  const wrap = containerRef.value.querySelector('.unsub-content-wrap')
  const wrapStyle = getComputedStyle(wrap)

  const gap = parseFloat(wrapStyle.gap) || 0
  const paddingTop = parseFloat(wrapStyle.paddingTop) || 0
  const paddingBottom = parseFloat(wrapStyle.paddingBottom) || 0

  const nonPosterHeight =
    infoHeight +
    card1Height +
    card2Height +
    paddingTop +
    paddingBottom +
    gap * 3

  const available = containerHeight - headerHeight - nonPosterHeight

  const finalHeight = Math.max(140, available)

  posterHeight.value = `${finalHeight}px`

  console.log('calculate', {
    containerHeight,
    headerHeight,
    infoHeight,
    card1Height,
    card2Height,
    gap,
    paddingTop,
    paddingBottom,
    nonPosterHeight,
    available,
    finalHeight,
    scrollHeight: containerRef.value.scrollHeight,
    clientHeight: containerRef.value.clientHeight,
  })
}

requestAnimationFrame(() => {
  const elems = [
    ['header', headerRef.value],
    ['poster', containerRef.value.querySelector('.hero-container')],
    ['info', infoRef.value],
    ['card1', card1Ref.value],
    ['card2', card2Ref.value],
  ]

  let sum = 0

  elems.forEach(([name, el]) => {
    const h = el.getBoundingClientRect().height
    console.log(name, h)
    sum += h
  })

  const wrap = containerRef.value.querySelector('.unsub-content-wrap')
  const style = getComputedStyle(wrap)

  console.log('gap', style.gap)
  console.log('paddingTop', style.paddingTop)
  console.log('paddingBottom', style.paddingBottom)

  console.log('sum', sum)
  console.log('client', containerRef.value.clientHeight)
  console.log('scroll', containerRef.value.scrollHeight)
})

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

let resizeObserver = null

const setupObserver = () => {
  if (typeof ResizeObserver === 'undefined') return
  if (resizeObserver) resizeObserver.disconnect()

  resizeObserver = new ResizeObserver(() => {
    calculatePosterHeight()
  })

  if (infoRef.value) resizeObserver.observe(infoRef.value)
  if (card1Ref.value) resizeObserver.observe(card1Ref.value)
  if (card2Ref.value) resizeObserver.observe(card2Ref.value)
  if (headerRef.value) resizeObserver.observe(headerRef.value)
}

onMounted(() => {
  loadNotificationStatus()
  window.addEventListener('resize', calculatePosterHeight)
})

onUnmounted(() => {
  window.removeEventListener('resize', calculatePosterHeight)
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
})

watch(show, (newVal) => {
  if (newVal) {
    nextTick(() => {
      setupObserver()
      calculatePosterHeight()
    })
  }
})
</script>

<style scoped>
.unsub-content-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px !important;
  padding: 0 16px calc(16px + env(safe-area-inset-bottom)) !important;
  min-height: 0;
}

.unsub-hero-container {
  flex-shrink: 1;
  min-height: 0;
  overflow: hidden;
}

.unsub-show-info {
  margin: 0 !important;
}

.unsub-show-info .show-title {
  font-size: 20px !important;
  margin-bottom: 2px !important;
}

.unsub-show-info .show-orig {
  font-size: 13px !important;
  margin-bottom: 0 !important;
}

.unsub-card {
  margin: 0 !important;
  padding: clamp(16px, 4vw, 20px) !important;
  border-radius: var(--radius-lg) !important;
}

.unsub-btn {
  margin-top: 12px !important;
}

.hero-poster {
  max-height: 100%;
  max-width: 100%;
  object-fit: contain;
}
</style>