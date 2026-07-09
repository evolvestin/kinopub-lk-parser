<template>
  <div class="card hoverable anim-item">
    <div class="label">
      <div class="icon" v-html="icons.masks"></div>
      ЖАНРЫ
    </div>
    <div class="chart-box" style="height: 320px;">
      <canvas ref="canvasRef"></canvas>
    </div>
    <div class="legend-grid" id="legend-genre">
      <div 
        v-for="(g, i) in processedGenres" 
        :key="g.name" 
        class="legend-item"
        @click="handleGenreClick(g, i)"
        @mouseenter="highlightSegment(i, true)"
        @mouseleave="highlightSegment(i, false)"
      >
        <div class="legend-dot" :style="{ background: palette[i % palette.length] }"></div>
        <div class="legend-name">{{ g.name }}</div>
        <div class="legend-val">
          {{ formatTime(g.minutes) }} ({{ g.percent }}%)
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { Chart, registerables } from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'
import { icons } from '../../utils/icons'
import { useUIStore } from '../../stores/uiStore'

const props = defineProps({
  genres: { type: Array, required: true },
  totalMinutes: { type: Number, default: 0 },
  isDark: { type: Boolean, default: true },
  dataKey: { type: String, default: 'genres_top' }
})

const uiStore = useUIStore()
const canvasRef = ref(null)
let chartInstance = null

const palette = ['#2ea043', '#388bfd', '#f85149', '#d29922', '#a371f7', '#1abc9c', '#e67e22', '#9b59b6', '#00d2ff', '#16a085']

const processedGenres = computed(() => {
  if (!props.genres?.length) return []
  
  const sorted = [...props.genres].sort((a, b) => b.minutes - a.minutes)
  
  let top = sorted.slice(0, 10)
  const totalMinutesSum = sorted.reduce((acc, g) => acc + g.minutes, 0)
  const topMinutes = top.reduce((acc, g) => acc + g.minutes, 0)

  if (totalMinutesSum > topMinutes) {
    const others = sorted.slice(10)
    top.push({
      name: 'Другие',
      minutes: totalMinutesSum - topMinutes,
      show_ids: [...new Set(others.flatMap(g => g.show_ids || []))]
    })
  }

  return top.map(g => ({
    ...g,
    percent: totalMinutesSum > 0 ? Math.round((g.minutes / totalMinutesSum) * 100) : 0
  }))
})

const formatTime = (totalMin) => {
  const h = Math.floor(totalMin / 60)
  const m = totalMin % 60
  return h > 0 ? `${h}ч ${m}м` : `${m}м`
}

const highlightSegment = (index, active) => {
  if (!chartInstance) return
  if (active) {
    chartInstance.setActiveElements([{ datasetIndex: 0, index }])
    chartInstance.tooltip.setActiveElements([{ datasetIndex: 0, index }], { x: 0, y: 0 })
  } else {
    chartInstance.setActiveElements([])
    chartInstance.tooltip.setActiveElements([], { x: 0, y: 0 })
  }
  chartInstance.update()
}

const handleGenreClick = (genre, index) => {
  uiStore.openLayer('history', 'filter', {
    key: props.dataKey,
    idx: index,
    title: genre.name
  })
}

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
    ctx.font = '900 34px system-ui'
    ctx.fillStyle = props.isDark ? '#e5e7eb' : '#1f2328'
    ctx.fillText(totalHours, centerX, centerY - 8)
    
    ctx.font = 'bold 10px system-ui'
    ctx.fillStyle = props.isDark ? '#6e7681' : '#8c959f'
    ctx.letterSpacing = '1px'
    ctx.fillText('ЧАСОВ ВСЕГО', centerX, centerY + 22)
    ctx.restore()
  }
}

const renderChart = () => {
  if (!canvasRef.value || !processedGenres.value.length) {
    if (chartInstance) {
      chartInstance.destroy()
      chartInstance = null
    }
    return
  }

  const data = processedGenres.value

  if (chartInstance) {
    chartInstance.data.labels = data.map(g => g.name)
    chartInstance.data.datasets[0].data = data.map(g => g.minutes)
    chartInstance.data.datasets[0].backgroundColor = data.map((_, i) => palette[i % palette.length])
    chartInstance.data.datasets[0].spacing = data.length === 1 ? 0 : 3
    chartInstance.options.onClick = (event, elements) => {
      if (elements.length > 0) {
        const index = elements[0].index
        handleGenreClick(data[index], index)
      }
    }
    chartInstance.options.plugins.tooltip.callbacks.label = (ctx) => {
      const val = ctx.parsed
      const h = Math.floor(val / 60)
      const m = val % 60
      return ` ${h}ч ${m}м (${data[ctx.dataIndex].percent}%)`
    }
    chartInstance.options.plugins.datalabels.formatter = (value, ctx) => {
      const pct = data[ctx.dataIndex].percent
      return pct > 5 ? pct + '%' : ''
    }
    chartInstance.update()
    return
  }

  chartInstance = new Chart(canvasRef.value, {
    type: 'doughnut',
    plugins: [ChartDataLabels, centerTextPlugin],
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
      cutout: '50%',
      layout: { padding: 15 },
      animation: { animateRotate: true, duration: 1200, easing: 'easeOutQuart' },
      onHover: (event, elements) => {
        event.native.target.style.cursor = elements.length ? 'pointer' : 'default'
      },
      onClick: (event, elements) => {
        if (elements.length > 0) {
          const index = elements[0].index
          handleGenreClick(data[index], index)
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: true,
          callbacks: {
            label: (ctx) => {
              const val = ctx.parsed
              const h = Math.floor(val / 60)
              const m = val % 60
              return ` ${h}ч ${m}м (${data[ctx.dataIndex].percent}%)`
            }
          }
        },
        datalabels: {
          color: '#fff',
          font: { weight: '800', size: 10 },
          formatter: (value, ctx) => {
            const pct = data[ctx.dataIndex].percent
            return pct > 5 ? pct + '%' : ''
          },
          display: 'auto'
        }
      }
    }
  })
}

onMounted(renderChart)
watch([processedGenres, () => props.isDark], renderChart, { deep: true })
onUnmounted(() => {
  if (chartInstance) chartInstance.destroy()
})
</script>

<style scoped>
.legend-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 6px;
    margin-top: 20px;
}
.legend-item {
    display: flex;
    align-items: center;
    gap: clamp(4px, 1.5vw, 6px);
    padding: 5px clamp(6px, 1.8vw, 8px);
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
}
.legend-item:hover {
    border-color: var(--accent);
    transform: translateY(-2px);
    background: var(--bg-card);
}
.legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}
.legend-name {
    font-size: clamp(10px, 2.8vw, 12px);
    font-weight: 700;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.legend-val {
    font-size: clamp(9px, 2.4vw, 10px);
    color: var(--text-muted);
    font-weight: 600;
    margin-left: auto;
    white-space: nowrap;
}
</style>