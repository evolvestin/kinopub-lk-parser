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

const render = () => {
  if (chartInstance) chartInstance.destroy()
  if (!canvasRef.value) return
  
  // Если данных нет или массивы пусты, не рисуем
  if (!props.data?.datasets?.length) return

  chartInstance = new Chart(canvasRef.value, {
    type: props.type,
    data: props.data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      ...props.options
    }
  })
}

onMounted(render)
watch(() => props.data, render, { deep: true })
onUnmounted(() => chartInstance?.destroy())
</script>