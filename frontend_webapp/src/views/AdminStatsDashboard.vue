<template>
  <div class="admin-stats-container">
    <div v-if="isLoading" class="loader-inline">
      <div class="spinner"></div>
    </div>

    <template v-else-if="stats">
      <div class="label" id="label-overview">
        <div class="icon" v-html="icons.dash"></div> Глобальная статистика ({{ periodLabel }})
      </div>

      <div class="years" v-if="availableYears.length > 1">
        <button 
          v-for="year in availableYears" 
          :key="year"
          class="yr clickable" 
          :class="{ on: String(currentYear) === String(year) }" 
          @click="selectYear(year)"
        >{{ year === 'all' ? 'Всё время' : year }}</button>
      </div>

      <div class="grid">
        <StatCard
          :icon="icons.time"
          :value="summary.duration_display || '0м'"
          label="Время просмотра"
          :sub-value="summary.total_views"
          :sub-label="plural(summary.total_views || 0, ['просмотр', 'просмотра', 'просмотров'])"
        />
        <StatCard
          :icon="icons.cal"
          :value="`${summary.activity_percent || 0}%`"
          label="Активность"
          :sub-value="`~${summary.daily_average_min || 0}`"
          sub-label="мин/день"
          sub-color-class="info"
        />
        <StatCard
          :icon="icons.tv"
          :value="summary.total_episodes || 0"
          label="Эпизодов"
          :sub-value="`${summary.unique_series || 0} ${plural(summary.unique_series || 0, ['сериал', 'сериала', 'сериалов'])}`"
          :sub-label="`· ${summary.series_duration || '0м'}`"
          sub-color-class="purple"
        />
        <StatCard
          :icon="icons.film"
          :value="summary.total_movies || 0"
          label="Фильмов"
          :sub-value="summary.movies_duration || '0м'"
          sub-color-class="orange"
        />
      </div>

      <div class="card hoverable anim-item" v-if="stats.ratings?.total">
        <div class="label">
          <div class="icon" style="color: #f1c40f;" v-html="icons.star"></div> Оценки
        </div>
        <div class="critic-header">
          <div class="critic-title-box">
            <div class="critic-badge" :style="ratingBadgeStyle">{{ ratingBadgeText }}</div>
            <div class="critic-avg" :style="{ color: ratingColor }">{{ (stats.ratings.avg || 0).toFixed(1) }}<span>/ 10</span></div>
          </div>
          <div class="critic-total">
            {{ stats.ratings.total }}<br>
            <span style="font-size: 11px; opacity: 0.7;">{{ plural(stats.ratings.total || 0, ['оценка', 'оценки', 'оценок']) }}</span>
          </div>
        </div>
        <BouncyBarChart 
          :labels="['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']"
          :data="stats.ratings.distribution"
          :palette="['#f85149', '#f85149', '#e67e22', '#e67e22', '#d29922', '#d29922', '#388bfd', '#388bfd', '#2ea043', '#39d353']"
        />
      </div>

      <div class="grid" style="margin-top: 16px;">
        <div class="card hoverable anim-item" v-if="hasMonthlyData" style="margin-bottom: 0;">
          <div class="label">
            <div class="icon" style="color: var(--info)" v-html="icons.chart"></div> Динамика
          </div>
          <BaseChart type="line" :data="monthlyChartData" :options="monthlyChartOptions" :height="320" />
        </div>

        <div class="card hoverable anim-item" v-if="hasWeekdayData" style="margin-bottom: 0;">
          <div class="label more-pad">
            <div class="icon" style="color: #2ecc71" v-html="icons.days"></div> Дни недели
          </div>
          <BouncyBarChart 
            :labels="['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']"
            :data="stats.weekday_chart.data"
            :palette="['#2ea043', '#2ea043', '#2ea043', '#2ea043', '#2ea043', '#388bfd', '#388bfd']"
            :show-values="true"
          />
        </div>
      </div>

      <div style="margin-top: 16px;">
        <ActivityHeatmap 
          v-if="stats.heatmap?.length"
          :years-data="stats.heatmap"
        />
      </div>

      <div style="margin-top: 16px;">
        <GenreDonut 
          v-if="stats.genres?.length"
          :genres="stats.genres"
          :total-minutes="summary.total_minutes_watched || 0"
          :is-dark="uiStore.theme === 'dark'"
        />
      </div>

      <div class="grid" style="margin-top: 16px;">
        <LeaderList 
          v-if="hasActorsData"
          category="actors"
          title="Актёры" icon-color="#d29922" :icon="icons.users"
          :data="stats.actors"
        />
        <LeaderList 
          v-if="hasDirectorsData"
          category="directors"
          title="Режиссёры" icon-color="#e74c3c" :icon="icons.film"
          :data="stats.directors"
        />
        <LeaderList 
          v-if="hasWritersData"
          category="writers"
          title="Сценаристы" icon-color="#3498db" :icon="icons.list"
          :data="stats.writers"
        />

        <div class="card hoverable anim-item" v-if="hasCountriesData" style="margin-bottom: 0;">
          <div class="label">
            <div class="icon" style="color: #388bfd" v-html="icons.globe"></div> Страны
          </div>
          <div>
            <div 
              v-for="(item, idx) in stats.countries" 
              :key="item.name" 
              class="li"
            >
              <div class="li-l">
                <span class="li-rank">{{ idx + 1 }}</span>
                <span v-if="item.emoji" style="font-size: clamp(18px, 5vw, 22px); margin-right: 6px; line-height: 1;">{{ item.emoji }}</span>
                <div class="li-name">{{ item.name }}</div>
              </div>
              <span class="li-r" style="color: var(--info)">{{ item.count }} {{ plural(item.count, ['просмотр', 'просмотра', 'просмотров']) }}</span>
            </div>
          </div>
        </div>

        <div class="card hoverable anim-item" v-if="hasBingesData" style="margin-bottom: 0;">
          <div class="label">
            <div class="icon" style="color: #a371f7" v-html="icons.bolt"></div> Марафоны
          </div>
          <div>
            <div 
              v-for="b in stats.binges" 
              :key="b.show_id + '-' + b.date" 
              class="li"
            >
              <div class="li-l">
                <img v-if="b.poster_url" :src="b.poster_url" style="width: clamp(36px, 10vw, 44px); height: clamp(54px, 15vw, 66px); border-radius: 6px; object-fit: cover; flex-shrink: 0; background: var(--bg-input); border: 1px solid var(--border);" />
                <div v-else style="width: clamp(36px, 10vw, 44px); height: clamp(54px, 15vw, 666px); border-radius: 6px; flex-shrink: 0; background: var(--bg-input); border: 1px solid var(--border);"></div>
                <div style="min-width: 0;">
                  <div class="li-name">{{ b.show_title }}</div>
                  <div class="li-sub">{{ b.date }}</div>
                </div>
              </div>
              <span class="li-r" style="color: var(--info)">{{ b.count }} {{ plural(b.count, ['эпизод', 'эпизода', 'эпизодов']) }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { icons } from '../utils/icons'
import { plural } from '../utils/helpers'
import { useUIStore } from '../stores/uiStore'
import StatCard from '../components/stats/StatCard.vue'
import BaseChart from '../components/shared/BaseChart.vue'
import BouncyBarChart from '../components/shared/BouncyBarChart.vue'
import ActivityHeatmap from '../components/stats/ActivityHeatmap.vue'
import GenreDonut from '../components/stats/GenreDonut.vue'
import LeaderList from '../components/stats/LeaderList.vue'

const uiStore = useUIStore()

const stats = ref(window.GLOBAL_STATS)
const currentYear = ref('all')
const isLoading = ref(false)

const availableYears = computed(() => {
  const years = stats.value?.meta?.years || []
  if (years.length > 0 && !years.includes('all')) {
    return ['all', ...years]
  }
  return years
})

const periodLabel = computed(() => stats.value?.summary?.period_label || '')
const summary = computed(() => stats.value?.summary || {})

const hasMonthlyData = computed(() => stats.value?.monthly_chart?.views?.some(v => v > 0))
const hasWeekdayData = computed(() => stats.value?.weekday_chart?.data?.some(v => v > 0))
const hasActorsData = computed(() => stats.value?.actors?.series?.length || stats.value?.actors?.others?.length)
const hasDirectorsData = computed(() => stats.value?.directors?.series?.length || stats.value?.directors?.others?.length)
const hasWritersData = computed(() => stats.value?.writers?.series?.length || stats.value?.writers?.others?.length)
const hasCountriesData = computed(() => stats.value?.countries?.length)
const hasBingesData = computed(() => stats.value?.binges?.length)

const ratingColor = computed(() => {
  const avg = stats.value?.ratings?.avg || 0
  if (avg >= 8.5) return '#2ea043'
  if (avg >= 7.0) return '#388bfd'
  if (avg >= 5.5) return '#d29922'
  return '#f85149'
})

const ratingBadgeText = computed(() => {
  const avg = stats.value?.ratings?.avg || 0
  if (avg >= 8.5) return 'Восторженный зритель'
  if (avg >= 7.0) return 'Позитивный критик'
  if (avg >= 5.5) return 'Объективный судья'
  return 'Суровый критик'
})

const ratingBadgeStyle = computed(() => {
  const avg = stats.value?.ratings?.avg || 0
  let c = { bg: 'rgba(248, 81, 73, 0.15)', text: '#e74c3c' }
  if (avg >= 8.5) c = { bg: 'rgba(46, 204, 113, 0.15)', text: '#2ecc71' }
  else if (avg >= 7.0) c = { bg: 'rgba(56, 139, 253, 0.15)', text: '#60a5fa' }
  else if (avg >= 5.5) c = { bg: 'rgba(210, 153, 34, 0.15)', text: '#d29922' }
  return { backgroundColor: c.bg, color: c.text }
})

const selectYear = async (year) => {
  if (currentYear.value === year) return
  isLoading.value = true
  try {
    const resp = await fetch(`/api/admin/global_stats/?year=${year}`)
    const data = await resp.json()
    stats.value = data
    currentYear.value = year
  } catch (e) {
    console.error('Failed to load global stats:', e)
  } finally {
    isLoading.value = false
  }
}

const monthlyChartData = computed(() => {
  const ch = stats.value?.monthly_chart || { labels: [], views: [], hours: [] }
  return {
    labels: ch.labels,
    datasets: [
      {
        label: ' Просмотры',
        data: ch.views,
        borderColor: '#3fb950',
        borderWidth: 3,
        tension: 0.4,
        fill: true,
        yAxisID: 'y',
        pointBackgroundColor: uiStore.theme === 'dark' ? '#0d1117' : '#ffffff',
        pointBorderColor: '#3fb950',
        pointBorderWidth: 2,
        pointRadius: 4,
        pointHoverRadius: 6
      },
      {
        label: ' Часы',
        data: ch.hours,
        borderColor: '#60a5fa',
        backgroundColor: 'transparent',
        borderWidth: 2,
        borderDash: [5, 5],
        tension: 0.4,
        fill: false,
        yAxisID: 'y1',
        pointRadius: 0,
        pointHoverRadius: 5
      }
    ]
  }
})

const monthlyChartOptions = computed(() => {
  const isDark = uiStore.theme === 'dark'
  const textColor = isDark ? 'rgba(229, 231, 235, .8)' : 'rgba(31, 35, 40, .8)'
  const gridColor = isDark ? 'rgba(255, 255, 255, .05)' : 'rgba(0, 0, 0, .05)'
  const borderColor = isDark ? '#2d333b' : '#d0d7de'
  const fSize = Math.max(10, Math.min(13, window.innerWidth * 0.03))

  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false
    },
    plugins: {
      legend: {
        display: true,
        position: 'top',
        labels: {
          color: textColor,
          usePointStyle: true,
          boxWidth: 8,
          padding: 15,
          font: { size: fSize, family: 'system-ui' }
        }
      },
      tooltip: {
        backgroundColor: isDark ? 'rgba(22, 27, 34, 0.95)' : 'rgba(255, 255, 255, 0.95)',
        titleColor: isDark ? '#f0f6fc' : '#1f2328',
        bodyColor: isDark ? '#8b949e' : '#59636e',
        borderColor: borderColor,
        borderWidth: 1,
        padding: 12,
        cornerRadius: 8,
        displayColors: true,
        boxPadding: 6,
        bodySpacing: 8,
        titleSpacing: 10
      }
    },
    scales: {
      x: {
        ticks: { 
          color: textColor, 
          font: { size: fSize },
          maxRotation: 45,
          minRotation: 45
        },
        grid: { display: false }
      },
      y: {
        type: 'linear',
        display: true,
        position: 'left',
        beginAtZero: true,
        ticks: { color: '#2ecc71', font: { size: fSize } },
        grid: { color: gridColor }
      },
      y1: {
        type: 'linear',
        display: true,
        position: 'right',
        beginAtZero: true,
        ticks: { color: '#60a5fa', font: { size: fSize } },
        grid: { drawOnChartArea: false }
      }
    }
  }
})
</script>

<style scoped>
.admin-stats-container .clickable,
.admin-stats-container .li-clickable,
.admin-stats-container .legend-item {
  pointer-events: none !important;
  cursor: default !important;
}

.admin-stats-container .years .yr {
  pointer-events: auto !important;
  cursor: pointer !important;
}
</style>