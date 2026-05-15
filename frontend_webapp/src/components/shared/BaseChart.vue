<template>
  <div class="chart-box" :style="{ height: height + 'px' }">
    <canvas ref="canvasRef"></canvas>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted } from 'vue'
import { Chart, registerables } from 'chart.js'

Chart.register(...registerables)

const props = defineProps({
  type: { type: String, default: 'bar' },
  data: { type: Object, required: true },
  options: { type: Object, default: () => ({}) },
  height: { type: Number, default: 180 }
})

const canvasRef = ref(null)
let chartInstance = null

const getContext = () => canvasRef.value?.getContext('2d')

const render = () => {
  if (chartInstance) chartInstance.destroy()
  const ctx = getContext()
  if (!ctx || !props.data?.datasets?.length) return

  // Применяем логику градиентов для линейных графиков (Динамика)
  const dataCopy = JSON.parse(JSON.stringify(props.data))
  
  if (props.type === 'line' && dataCopy.datasets[0]) {
    const fillGradient = ctx.createLinearGradient(0, 0, 0, props.height);
    fillGradient.addColorStop(0, 'rgba(46, 160, 67, 0.4)');
    fillGradient.addColorStop(1, 'rgba(46, 160, 67, 0)');
    dataCopy.datasets[0].backgroundColor = fillGradient;
  }

  chartInstance = new Chart(ctx, {
    type: props.type,
    data: dataCopy,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      ...props.options
    }
  })
}

onMounted(render)

// Используем watch с флагом immediate: false, так как первый рендер в onMounted
watch(() => props.data, () => {
  render()
}, { deep: true })

// Следим за темой
watch(() => props.options, () => {
  render()
}, { deep: true })

onUnmounted(() => chartInstance?.destroy())
</script>