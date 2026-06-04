<template>
  <div class="modal-overlay show" @click.self="close">
    <div class="modal-content casino-modal-content" :class="{ 'app-shake-active': isShaking }">
      <canvas ref="canvasRef" id="casino-canvas" style="position:absolute; inset:0; pointer-events:none; z-index:100;"></canvas>
      
      <button v-if="isDebug" class="casino-debug-reset" @click="resetCooldown">
        DEBUG: RESET
      </button>

      <div class="modal-header" style="position: relative; z-index: 101;">
        <div class="modal-title" style="color:var(--accent); display:flex; align-items:center; gap:8px;">
          <span>🎰</span> Рулетка
        </div>
        <button class="modal-close" @click="close">×</button>
      </div>

      <div id="casino-body" style="padding:10px 0 20px; text-align:center; position:relative; z-index:10; flex-grow: 1; display: flex; flex-direction: column; justify-content: center;">
        
        <!-- Загрузка -->
        <div v-if="state === 'loading'" class="loader-inline">
          <div class="spinner"></div>
        </div>

        <!-- Выбор папки / Главное меню -->
        <div v-else-if="state === 'menu'" class="casino-slot-container active">
          <div style="color:var(--accent); font-weight:800; font-size:14px; margin-bottom:15px; text-transform:uppercase; letter-spacing:0.5px;">
            ✅ Рулетка готова
          </div>
          <button class="btn-primary" style="margin-bottom:15px;" @click="selectFolder('all')">
            Весь каталог
          </button>
          
          <div v-if="validFolders.length > 1" class="folders-choice-list" style="max-height: 240px; overflow-y: auto; padding: 4px; display: flex; flex-direction: column; gap: 8px; margin-bottom: 15px;">
            <button v-for="f in validFolders" :key="f.id" class="btn-primary casino-btn-choice" @click="selectFolder(f.id)">
              <span :style="{ color: f.color, marginRight: '10px' }" v-html="icons[f.icon] || icons.folder"></span>
              <span style="flex:1; color: var(--text-primary); text-align: left;">{{ f.name }}</span>
              <span style="opacity:0.6; font-size:12px; color: var(--text-muted);">{{ f.items.length }}</span>
            </button>
          </div>

          <button class="btn-primary" style="background:var(--bg-input); color:var(--text-primary); border:1px solid var(--border);" @click="loadHistory">
            История
          </button>
        </div>

        <!-- Кулдаун (активный результат) -->
        <div v-else-if="state === 'cooldown' && activeSpin" class="casino-slot-container active">
          <div class="casino-slot-window">
            <img :src="activeSpin.show.poster_url" alt="" @error="handleImgFallback" />
            <div v-if="activeSpin.show.user_rating" class="grid-badges">
              <span class="rating-badge" style="background:rgba(0,0,0,0.6); border:none;">
                <span v-html="icons.star"></span>{{ activeSpin.show.user_rating }}
              </span>
            </div>
          </div>
          <div class="casino-info-container">
            <div class="casino-title">{{ activeSpin.show.title }}</div>
            <div class="casino-meta-info">
              {{ activeSpin.show.year }} · {{ showTypeRu(activeSpin.show.type) }}
            </div>
            <div class="casino-controls-reveal active" style="width: 100%;">
              <div style="display: flex; gap: 10px; width: 100%;">
                <button class="btn-primary" style="margin-top:0; flex: 1;" @click="goToWinner(activeSpin.show.show_id)">Подробнее</button>
                <button class="btn-primary" style="margin-top:0; flex: 1; background:var(--bg-input); color:var(--text-primary); border:1px solid var(--border);" @click="loadHistory">История</button>
              </div>
              <div class="casino-timer-wrap" style="width: 100%;">
                <div style="font-size:10px; color:var(--accent); font-weight:800; margin-bottom:4px;" v-html="isExpired ? '✅ РУЛЕТКА ГОТОВА' : 'СЛЕДУЮЩИЙ ШАНС'"></div>
                <div v-if="!isExpired" class="casino-timer-clock">{{ formattedCountdown }}</div>
                <button v-else class="btn-primary" style="margin-top: 10px; padding: 10px; font-size: 14px; width: 100%;" @click="resetToMenu">Крутить снова</button>
              </div>
            </div>
          </div>
        </div>

        <!-- Анимация вращения / Фаза интриги / Результат вращения -->
        <div v-else-if="['spinning', 'mystery', 'reveal'].includes(state)" class="casino-slot-container active">
          <div class="casino-slot-window" :class="{ 'casino-win-glow': state === 'reveal' }">
            <img v-if="state !== 'mystery' && currentPoster" :src="currentPoster" alt="" />
            <div v-else-if="state === 'mystery'" style="display:flex; align-items:center; justify-content:center; height:100%; font-size:100px; font-weight:900; color:var(--accent);">?</div>
            <div v-if="state === 'reveal' && winner?.user_rating" class="grid-badges">
              <span class="rating-badge" style="background:rgba(0,0,0,0.6); border:none;">
                <span v-html="icons.star"></span>{{ winner.user_rating }}
              </span>
            </div>
          </div>
          <div class="casino-info-container">
            <div class="casino-title">{{ statusTitle }}</div>
            <div v-if="state === 'reveal' && winner" class="casino-meta-info">
              {{ winner.year }} · {{ showTypeRu(winner.type) }}
            </div>
            
            <div class="casino-controls-reveal" :class="{ active: state === 'reveal' }" style="width: 100%;">
              <div style="display: flex; gap: 10px; width: 100%;">
                <button class="btn-primary" style="margin-top:0; flex: 1;" @click="goToWinner(winner.show_id)">Подробнее</button>
                <button class="btn-primary" style="margin-top:0; flex: 1; background:var(--bg-input); color:var(--text-primary); border:1px solid var(--border);" @click="loadHistory">История</button>
              </div>
              <div class="casino-timer-wrap" style="width: 100%;">
                <div style="font-size:10px; color:var(--accent); font-weight:800; margin-bottom:4px;">СЛЕДУЮЩИЙ ШАНС</div>
                <div class="casino-timer-clock">{{ formattedCountdown }}</div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
    
    <!-- Глобальное затемнение для эффекта саспенса -->
    <div class="casino-dimmed" :class="{ active: state === 'spinning' || state === 'mystery' }" :style="{ opacity: dimOpacity }"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useUIStore } from '../../stores/uiStore'
import { useWishlistStore } from '../../stores/wishlistStore'
import { useStatsStore } from '../../stores/useStatsStore'
import { useApi } from '../../composables/useApi'
import { icons } from '../../utils/icons'

const uiStore = useUIStore()
const wishlistStore = useWishlistStore()
const statsStore = useStatsStore()
const api = useApi()

const state = ref('loading')
const activeSpin = ref(null)
const winner = ref(null)
const currentPoster = ref('')
const isShaking = ref(false)
const dimOpacity = ref(0)
const countdownLeft = ref(0)

const canvasRef = ref(null)
let ctx = null
let animationId = null
const rockets = []
const particles = []
const canvasActive = ref(false)
let countdownInterval = null

const isDebug = computed(() => window.IS_DEBUG)
const validFolders = computed(() => wishlistStore.folders.filter(f => f.items && f.items.length > 0))

const isExpired = computed(() => countdownLeft.value <= 0)

const formattedCountdown = computed(() => {
  if (countdownLeft.value <= 0) return '00:00:00'
  const h = Math.floor(countdownLeft.value / 3600)
  const m = Math.floor((countdownLeft.value % 3600) / 60)
  const s = countdownLeft.value % 60
  return [h, m, s].map(v => String(v).padStart(2, '0')).join(':')
})

const statusTitle = computed(() => {
  if (state.value === 'spinning') return 'КРУТИМ...'
  if (state.value === 'mystery') return 'КТО ЖЕ ТАМ...'
  if (state.value === 'reveal' && winner.value) return winner.value.title
  return ''
})

class Particle {
  constructor(x, y, hue) {
    this.x = x
    this.y = y
    const angle = Math.random() * Math.PI * 2
    const speed = Math.random() * 6 + 2
    this.vx = Math.cos(angle) * speed
    this.vy = Math.sin(angle) * speed
    this.hue = hue + (Math.random() * 40 - 20)
    this.brightness = 50 + Math.random() * 30
    this.alpha = 1
    this.decay = Math.random() * 0.015 + 0.007
    this.size = Math.random() * 1.5 + 1
    this.friction = 0.95 + Math.random() * 0.03
    this.gravity = 0.12
    this.twinkle = Math.random() > 0.4
  }
  update() {
    this.vx *= this.friction
    this.vy *= this.friction
    this.vy += this.gravity
    this.x += this.vx
    this.y += this.vy
    this.alpha -= this.decay
  }
}

class Rocket {
  constructor(startX, startY, targetX, targetY, hue) {
    this.x = startX
    this.y = startY
    this.vx = (targetX - startX) / 45
    this.vy = (targetY - startY) / 45
    this.targetY = targetY
    this.hue = hue
    this.alpha = 1
    this.history = []
  }
  update() {
    this.history.push({ x: this.x, y: this.y })
    if (this.history.length > 5) this.history.shift()
    this.x += this.vx
    this.y += this.vy
    this.vy += 0.05
  }
}

const initCanvas = () => {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.closest('.modal-content').getBoundingClientRect()
  canvas.width = rect.width
  canvas.height = rect.height
  ctx = canvas.getContext('2d', { alpha: true })
}

const launchRocket = () => {
  if (!canvasActive.value) {
    canvasActive.value = true
    nextTick(() => {
      initCanvas()
      draw()
    });
  }
  const canvas = canvasRef.value
  if (!canvas) return

  const startX = canvas.width / 2 + (Math.random() * 100 - 50)
  const startY = canvas.height
  const targetX = Math.random() * canvas.width * 0.8 + (canvas.width * 0.1)
  const targetY = Math.random() * canvas.height * 0.4 + 50
  const hue = Math.floor(Math.random() * 360)

  rockets.push(new Rocket(startX, startY, targetX, targetY, hue))
}

const explode = (x, y, hue) => {
  const count = 120
  for (let i = 0; i < count; i++) {
    particles.push(new Particle(x, y, hue))
  }
}

const draw = () => {
  if (!canvasActive.value || !ctx) return

  ctx.globalCompositeOperation = 'destination-out'
  ctx.fillStyle = 'rgba(0, 0, 0, 0.2)'
  ctx.fillRect(0, 0, canvasRef.value.width, canvasRef.value.height)

  ctx.globalCompositeOperation = 'lighter'

  for (let i = rockets.length - 1; i >= 0; i--) {
    const r = rockets[i]
    r.update()

    ctx.beginPath()
    ctx.strokeStyle = `hsla(${r.hue}, 100%, 70%, ${r.alpha})`
    ctx.lineWidth = 2
    if (r.history.length > 1) {
      ctx.moveTo(r.history[0].x, r.history[0].y)
      ctx.lineTo(r.x, r.y)
    }
    ctx.stroke()

    if (r.vy >= 0 || r.y <= r.targetY) {
      explode(r.x, r.y, r.hue)
      rockets.splice(i, 1)
    }
  }

  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i]
    p.update()

    if (p.alpha <= 0) {
      particles.splice(i, 1)
      continue
    }

    let b = p.brightness
    if (p.twinkle && Math.random() > 0.8) b += 30

    ctx.fillStyle = `hsla(${p.hue}, 100%, ${b}%, ${p.alpha})`
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.size * (0.5 + p.alpha * 0.5), 0, Math.PI * 2)
    ctx.fill()
  }

  if (rockets.length > 0 || particles.length > 0) {
    animationId = requestAnimationFrame(draw)
  } else {
    ctx.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height)
    canvasActive.value = false
  }
}

const launchSalvos = (count = 8, delay = 250) => {
  for (let i = 0; i < count; i++) {
    setTimeout(() => {
      if (uiStore.modals.casino.isOpen) {
        launchRocket()
        launchRocket()
      }
    }, i * delay)
  }
}

const startCountdown = (expiresMs) => {
  if (countdownInterval) clearInterval(countdownInterval)
  
  const tick = () => {
    const diff = Math.floor((expiresMs - Date.now()) / 1000)
    countdownLeft.value = diff
    if (diff <= 0) {
      clearInterval(countdownInterval)
    }
  }
  tick()
  countdownInterval = setInterval(tick, 1000)
}

const checkStatus = async () => {
  state.value = 'loading'
  try {
    const data = await api.post('casino/', { action: 'status' })
    if (data.active_spin) {
      activeSpin.value = data.active_spin
      state.value = 'cooldown'
      startCountdown(data.active_spin.expires)
    } else {
      state.value = 'menu'
    }
  } catch (e) {
    uiStore.showToast('Ошибка при загрузке статуса')
    close()
  }
}

const selectFolder = async (folderId) => {
  state.value = 'spinning'
  
  let pool = []
  if (folderId === 'all') {
    let map = new Map()
    wishlistStore.folders.forEach(f => f.items.forEach(i => map.set(i.show_id, i)))
    pool = Array.from(map.values())
  } else {
    const f = wishlistStore.folders.find(x => x.id === folderId)
    if (f) pool = f.items
  }

  try {
    const data = await api.post('casino/', { action: 'spin', folder_id: folderId })
    if (data.error) {
      uiStore.showToast('Ошибка: ' + data.error)
      state.value = 'menu'
      return
    }

    winner.value = data.show
    if (!pool.length) pool = [data.show]

    let elapsed = 0
    const duration = 4000
    let delay = 50

    const tick = () => {
      const rnd = pool[Math.floor(Math.random() * pool.length)]
      currentPoster.value = rnd.poster_url?.replace('/small/', '/medium/') || ''
      
      const progress = elapsed / duration
      dimOpacity.value = progress * 0.7

      if (elapsed % 200 === 0 && progress < 0.8) {
        launchRocket()
      }

      if (window.navigator.vibrate) window.navigator.vibrate(10)

      elapsed += delay
      if (elapsed < duration) {
        delay = 50 + (Math.pow(progress, 3) * 400)
        setTimeout(tick, delay)
      } else {
        runMysteryPhase(data.expires)
      }
    }
    tick()

  } catch (e) {
    uiStore.showToast('Ошибка запуска рулетки')
    state.value = 'menu'
  }
}

const runMysteryPhase = (expiresMs) => {
  state.value = 'mystery'
  dimOpacity.value = 0.8

  let count = 0
  const timer = setInterval(() => {
    if (state.value !== 'mystery' || count >= 4) {
      clearInterval(timer)
      return
    }
    launchRocket()
    count++
  }, 400)

  setTimeout(() => {
    clearInterval(timer)
    runReveal(expiresMs)
  }, 1600)
}

const runReveal = (expiresMs) => {
  state.value = 'reveal'
  dimOpacity.value = 0
  isShaking.value = true

  setTimeout(() => {
    isShaking.value = false
  }, 500)

  launchSalvos(12, 200)

  if (window.navigator.vibrate) {
    window.navigator.vibrate([100, 50, 100, 50, 500])
  }

  startCountdown(expiresMs)
}

const loadHistory = async () => {
  close()
  uiStore.setLoading(true)
  try {
    const data = await api.post('casino/', { action: 'history' })
    if (statsStore.currentStats) {
      statsStore.currentStats.casino_history = data.history || []
    }
    uiStore.openLayer('history', 'casino', { title: 'История рулетки' })
  } catch (e) {
    uiStore.showToast('Ошибка загрузки истории')
  } finally {
    uiStore.setLoading(false)
  }
}

const resetCooldown = async () => {
  try {
    await api.post('casino/', { action: 'reset' })
    uiStore.showToast('Кулдаун сброшен')
    state.value = 'menu'
  } catch (e) {
    uiStore.showToast('Ошибка сброса')
  }
}

const resetToMenu = () => {
  state.value = 'menu'
}

const close = () => {
  uiStore.closeModal('casino')
}

const goToWinner = (showId) => {
  close()
  uiStore.openLayer('show', showId)
}

const handleImgFallback = (e) => {
  e.target.style.display = 'none'
}

const showTypeRu = (type) => {
  const mapping = {
    'Series': 'Сериал', 'Movie': 'Фильм', 'Concert': 'Концерт',
    'Documentary Movie': 'Док. фильм', 'Documentary Series': 'Док. сериал',
    'TV Show': 'ТВ-шоу', '3D Movie': '3D фильм'
  }
  return mapping[type] || type || ''
}

onMounted(() => {
  checkStatus()
  window.addEventListener('resize', initCanvas)
})

onUnmounted(() => {
  window.removeEventListener('resize', initCanvas)
  if (animationId) cancelAnimationFrame(animationId)
  if (countdownInterval) clearInterval(countdownInterval)
})
</script>

<style scoped>
@import '../../../../kinopub_parser/static/css/casino.css';

.folders-choice-list {
  scrollbar-width: none;
}
.folders-choice-list::-webkit-scrollbar {
  display: none;
}
</style>