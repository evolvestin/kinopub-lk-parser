<script setup>
import { onMounted, ref, watch, onUnmounted } from 'vue'
import { Chart, registerables } from 'chart.js'
import { icons } from '../../utils/icons'

Chart.register(...registerables)

const props = defineProps({
  genres: { type: Array, required: true },
  totalMinutes: { type: Number, default: 0 },
  isDark: { type: Boolean, default: true }
})

const canvasRef = ref(null)
let chartInstance = null

const palette = ['#2ea043', '#388bfd', '#f85149', '#d29922', '#a371f7', '#1abc9c', '#e67e22', '#9b59b6', '#00d2ff', '#16a085']

const centerTextPlugin = {
  id: 'centerText',
  afterDraw: (chart) => {
    const { ctx, chartArea: { top, height, left, width } } = chart
    ctx.save()
    const centerX = left + width / 2
    const centerY = top + height / 2
    const totalHours = Math.floor(props.totalMinutes / 60)
    
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.font = '900 30px system-ui'
    ctx.fillStyle = props.isDark ? '#e5e7eb' : '#1f2328'
    ctx.fillText(totalHours, centerX, centerY - 8)
    
    ctx.font = 'bold 10px system-ui'
    ctx.fillStyle = '#6e7681'
    ctx.letterSpacing = '1px'
    ctx.fillText('ЧАСОВ ВСЕГО', centerX, centerY + 22)
    ctx.restore()
  }
}

const renderChart = () => {
  if (chartInstance) chartInstance.destroy()
  if (!canvasRef.value) return

  const data = props.genres.slice(0, 10)
  
  chartInstance = new Chart(canvasRef.value, {
    type: 'doughnut',
    plugins: [centerTextPlugin],
    data: {
      labels: data.map(g => g.name),
      datasets: [{
        data: data.map(g => g.minutes),
        backgroundColor: data.map((_, i) => palette[i % palette.length]),
        borderWidth: 0,
        hoverOffset: 15,
        borderRadius: 6,
        spacing: data.length === 1 ? 0 : 3
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      layout: { padding: 15 },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const h = Math.floor(ctx.parsed / 60)
              const m = ctx.parsed % 60
              return ` ${h}ч ${m}м`
            }
          }
        }
      }
    }
  })
}

onMounted(renderChart)
watch(() => props.genres, renderChart, { deep: true })
onUnmounted(() => chartInstance?.destroy())
</script>

<template>
  <div class="card hoverable anim-item">
    <div class="label">
      <div class="icon" v-html="icons.masks"></div>
      Жанры
    </div>
    <div class="chart-box" style="height: 320px;">
      <canvas ref="canvasRef"></canvas>
    </div>
    <div class="legend-grid">
      <div 
        v-for="(g, i) in genres.slice(0, 10)" 
        :key="g.name" 
        class="legend-item"
      >
        <div class="legend-dot" :style="{ background: palette[i % palette.length] }"></div>
        <div class="legend-name">{{ g.name }}</div>
        <div class="legend-val">{{ Math.floor(g.minutes / 60) }}ч</div>
      </div>
    </div>
  </div>
</template>