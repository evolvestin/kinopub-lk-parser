<template>
  <div class="modal-overlay show" @click.self="uiStore.modals.casino.isOpen = false">
    <div class="modal-content casino-modal-content">
      <canvas ref="canvasRef" id="casino-canvas" style="position:absolute; inset:0; pointer-events:none; z-index:100;"></canvas>
      <div class="modal-header">
        <div class="modal-title" style="color:var(--accent); display:flex; align-items:center; gap:8px;">
          <span>🎰</span> Рулетка
        </div>
        <button class="modal-close" @click="uiStore.modals.casino.isOpen = false">×</button>
      </div>

      <div id="casino-body" style="padding:10px 0 20px; text-align:center; position:relative; z-index:10;">
        <template v-if="state === 'idle'">
          <div style="color:var(--accent); font-weight:800; font-size:14px; margin-bottom:15px;">РУЛЕТКА ГОТОВА</div>
          <button class="btn-primary" @click="startSpin">Запустить</button>
        </template>

        <div v-if="state !== 'idle'" id="cas-container" class="casino-slot-container active">
          <div class="casino-slot-window" :class="{ 'casino-win-glow': state === 'result' }">
            <img v-if="currentPoster" :src="currentPoster" style="width:100%; height:100%; object-fit:cover;">
            <div v-else style="display:flex; align-items:center; justify-content:center; height:100%; font-size:100px; font-weight:900; color:var(--accent);">?</div>
          </div>
          <div class="casino-info-container">
            <div class="casino-title">{{ state === 'spinning' ? 'КРУТИМ...' : winner?.title }}</div>
            <div v-if="state === 'result'" class="casino-controls-reveal active">
              <button class="btn-primary" @click="openWinner">Подробнее</button>
              <div class="casino-timer-wrap">
                <div style="font-size:10px; color:var(--accent); font-weight:800;">СЛЕДУЮЩИЙ ШАНС ЧЕРЕЗ 24Ч</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useUIStore } from '../../stores/uiStore'
import { useApi } from '../../composables/useApi'
import { useWishlistStore } from '../../stores/wishlistStore'

const uiStore = useUIStore()
const wishlistStore = useWishlistStore()
const api = useApi()
const canvasRef = ref(null)
const state = ref('idle')
const currentPoster = ref('')
const winner = ref(null)

let engine = null

class Fireworks {
  constructor(canvas) {
    this.canvas = canvas
    this.ctx = canvas.getContext('2d')
    this.particles = []
  }
  launch() {
    for (let i = 0; i < 30; i++) {
      this.particles.push({
        x: this.canvas.width / 2,
        y: this.canvas.height / 2,
        vx: (Math.random() - 0.5) * 10,
        vy: (Math.random() - 0.5) * 10,
        alpha: 1,
        color: `hsl(${Math.random() * 360}, 100%, 50%)`
      })
    }
  }
  update() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height)
    this.particles.forEach((p, i) => {
      p.x += p.vx; p.y += p.vy; p.alpha -= 0.02
      if (p.alpha <= 0) this.particles.splice(i, 1)
      this.ctx.fillStyle = p.color
      this.ctx.globalAlpha = p.alpha
      this.ctx.beginPath(); this.ctx.arc(p.x, p.y, 2, 0, Math.PI * 2); this.ctx.fill()
    })
    if (this.particles.length) requestAnimationFrame(() => this.update())
  }
}

const startSpin = async () => {
  state.value = 'spinning'
  try {
    const data = await api.post('casino/', { action: 'spin', folder_id: 'all' })
    winner.value = data.show
    const pool = wishlistStore.folders.flatMap(f => f.items)
    
    let ticks = 0
    const interval = setInterval(() => {
      currentPoster.value = pool[Math.floor(Math.random() * pool.length)].poster_url
      if (ticks++ > 20) {
        clearInterval(interval)
        currentPoster.value = winner.value.poster_url
        state.value = 'result'
        engine.launch()
        engine.update()
      }
    }, 100)
  } catch (e) { uiStore.showToast('Ошибка') }
}

const openWinner = () => {
  uiStore.modals.casino.isOpen = false
  uiStore.openLayer('show', { showId: winner.value.show_id })
}

onMounted(() => {
  if (canvasRef.value) {
    canvasRef.value.width = canvasRef.value.offsetWidth
    canvasRef.value.height = canvasRef.value.offsetHeight
    engine = new Fireworks(canvasRef.value)
  }
})
</script>

<style scoped>
@import '../../../../kinopub_parser/static/css/casino.css';
</style>