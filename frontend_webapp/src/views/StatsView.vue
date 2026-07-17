<template>
  <div class="view active-view" style="display: flex; flex-direction: column; overflow-y: auto; position: relative;">
    <div v-if="isFakeMode" class="onboarding-overlay-fixed">
      <div class="onboarding-card">
        <div class="onboarding-icon">📊</div>
        <div class="onboarding-title">Здесь будет ваша статистика</div>
        <div class="onboarding-text">Отмечайте просмотренные фильмы и сериалы, ставьте оценки, и этот экран наполнится вашими личными данными.</div>
        <button class="btn-primary" style="margin-top: 0;" @click="uiStore.switchBaseView('search')">Найти первый фильм</button>
      </div>
    </div>

    <template v-if="currentStats">
      <div :class="{ 'blurred-content': isFakeMode }" style="display: flex; flex-direction: column; flex: 1; min-height: 0;">
        <div class="header">
          <div class="header-left">
            <div class="avatar">
              <img v-if="userPhoto" :src="userPhoto" alt="A">
              <template v-else>{{ firstLetter }}</template>
            </div>
            <div>
              <div class="header-name glow-text">{{ userName }}</div>
              <div class="header-sub">{{ periodLabel }}</div>
            </div>
          </div>
          <div class="top-controls">
            <button v-if="!statsStore.isShared" class="share-btn" @click="uiStore.openModal('share')">
              <span v-html="icons.share"></span>
            </button>
            <button class="theme-btn" @click="uiStore.toggleTheme">
              <span v-html="themeIcon"></span>
            </button>
          </div>
        </div>

        <div v-if="isGamificationMode" class="gamification-progress-card">
          <div class="gamification-title">Начало положено! 🚀</div>
          <div class="gamification-text">Вы отметили {{ statsStore.currentStats.summary.total_views }} {{ plural(statsStore.currentStats.summary.total_views, ['фильм', 'фильма', 'фильмов']) }}. Добавьте еще {{ 10 - statsStore.currentStats.summary.total_views }}, чтобы разблокировать красивые графики, топы актеров и тепловую карту активности.</div>
          <div class="gamification-bar-wrap">
            <div class="gamification-bar-fill" :style="{ width: (statsStore.currentStats.summary.total_views / 10 * 100) + '%' }"></div>
          </div>
          <div style="font-size: 11px; color: var(--accent); font-weight: 800;">ПРОГРЕСС {{ statsStore.currentStats.summary.total_views }} / 10</div>
        </div>

        <div class="tabs" v-if="statsStore.hasGroup">
          <button class="tab" :class="{ on: statsStore.activeTab === 'personal' }" @click="statsStore.setActiveTab('personal')">
            <div class="icon" v-html="icons.user"></div> Личная
          </button>
          <button class="tab" :class="{ on: statsStore.activeTab === 'group' }" @click="statsStore.setActiveTab('group')">
            <div class="icon" v-html="icons.users"></div> Группа
          </button>
        </div>

        <div class="years" v-if="statsStore.availableYears.length > 1">
          <button 
            v-for="year in statsStore.availableYears" 
            :key="year"
            class="yr clickable" 
            :class="{ on: String(statsStore.currentYear) === String(year) }" 
            @click="statsStore.setYear(year)"
          >{{ year === 'all' ? 'Всё время' : year }}</button>
        </div>

        <div v-if="statsStore.activeTab === 'personal'" id="sec-personal">
          <div class="label"><div class="icon" v-html="icons.dash"></div> Обзор</div>
          
          <div class="grid">
            <StatCard
              :icon="icons.time"
              :value="summary.duration_display || '0м'"
              label="Время просмотра"
              :sub-value="summary.total_views"
              :sub-label="plural(summary.total_views || 0, ['просмотр', 'просмотра', 'просмотров'])"
              :clickable="true"
              @click="openHistory('all')"
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
              :clickable="true"
              @click="openHistory('episodes')"
            />
            <StatCard
              :icon="icons.film"
              :value="summary.total_movies || 0"
              label="Фильмов"
              :sub-value="summary.movies_duration || '0м'"
              sub-color-class="orange"
              :clickable="true"
              @click="openHistory('movies')"
            />
            <StatCard
              :icon="icons.bookmark"
              :value="summary.wishlist_added || 0"
              label="Добавлено в избранное"
              :clickable="!statsStore.isShared"
              @click="handleWishlistClick"
            />
            <StatCard
              :icon="icons.check"
              :value="summary.wishlist_watched || 0"
              label="Просмотрено из избранного"
              :clickable="true"
              @click="openHistory('wishlist_watched')"
            />
          </div>

          <div class="card hoverable anim-item" v-if="currentStats.ratings?.total">
            <div class="label"><div class="icon" style="color: #f1c40f;" id="it-star-label"></div> Оценки</div>
            <div class="critic-header">
                <div class="critic-title-box">
                    <div class="critic-badge" :style="ratingBadgeStyle">{{ ratingBadgeText }}</div>
                    <div class="critic-avg" :style="{ color: ratingColor }">{{ (currentStats.ratings.avg || 0).toFixed(1) }}<span>/ 10</span></div>
                </div>
                <div class="critic-total">
                  {{ currentStats.ratings.total }}<br>
                  <span style="font-size: 11px; opacity: 0.7;">{{ plural(currentStats.ratings.total || 0, ['оценка', 'оценки', 'оценок']) }}</span>
                </div>
            </div>
            <BouncyBarChart 
              :labels="['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']"
              :data="currentStats.ratings.distribution"
              :palette="['#f85149', '#f85149', '#e67e22', '#e67e22', '#d29922', '#d29922', '#388bfd', '#388bfd', '#2ea043', '#39d353']"
              @node-click="(idx) => openHistory('rating_filter', { idx: idx + 1, title: 'Оценка: ' + (idx + 1) })"
            />
            <div class="stat clickable centered-stat-btn" style="flex-direction: row; justify-content: center; align-items: center; padding: 16px; margin-top: 12px; border-radius: 15px;" @click="openHistory('ratings')">
                <span style="font-weight: 800; font-size: 14px; color: var(--text-primary);">Все оценки</span>
            </div>
          </div>

          <div class="card hoverable anim-item" v-if="hasMonthlyData" style="margin-top: 16px;">
            <div class="label"><div class="icon" style="color:var(--info)" v-html="icons.chart"></div> Динамика</div>
            <BaseChart type="line" :data="monthlyChartData" :options="monthlyChartOptions" :height="320" />
          </div>

          <div class="card hoverable anim-item" v-if="hasWeekdayData" style="margin-top: 16px;">
            <div class="label more-pad"><div class="icon" style="color:#2ecc71" v-html="icons.days"></div> Дни недели</div>
            <BouncyBarChart 
              :labels="['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']"
              :data="currentStats.weekday_chart.data"
              :palette="['#2ea043', '#2ea043', '#2ea043', '#2ea043', '#2ea043', '#388bfd', '#388bfd']"
              :show-values="true"
              @node-click="(idx) => {
                const fullDays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];
                openHistory('weekday', { idx, title: fullDays[idx] })
              }"
            />
          </div>

          <ActivityHeatmap 
            v-if="currentStats.heatmap?.length && !isGamificationMode"
            :years-data="currentStats.heatmap"
            @cell-click="handleHeatmapClick"
          />

          <GenreDonut 
            v-if="currentStats.genres?.length && !isGamificationMode"
            :genres="currentStats.genres"
            :total-minutes="summary.total_minutes_watched || 0"
            :is-dark="uiStore.theme === 'dark'"
          />

          <LeaderList 
            v-if="hasActorsData"
            category="actors"
            title="Актёры" icon-color="#d29922" :icon="icons.users"
            :data="currentStats.actors"
          />
          <LeaderList 
            v-if="hasDirectorsData"
            category="directors"
            title="Режиссёры" icon-color="#e74c3c" :icon="icons.film"
            :data="currentStats.directors"
          />
          <LeaderList 
            v-if="hasWritersData"
            category="writers"
            title="Сценаристы" icon-color="#3498db" :icon="icons.list"
            :data="currentStats.writers"
          />

          <div class="card hoverable anim-item" v-if="hasCountriesData">
            <div class="label">
              <div class="icon" style="color: #388bfd" v-html="icons.globe"></div>
              Страны
            </div>
            <div>
              <div 
                v-for="(item, idx) in currentStats.countries" 
                :key="item.name" 
                class="li li-clickable clickable"
                @click="openHistory('filter', { key: 'countries', idx, title: item.name })"
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

          <div class="card hoverable anim-item" v-if="hasBingesData">
            <div class="label">
              <div class="icon" style="color: #a371f7" v-html="icons.bolt"></div>
              Марафоны
            </div>
            <div>
              <div 
                v-for="b in currentStats.binges" 
                :key="b.show_id + '-' + b.date" 
                class="li li-clickable clickable"
                @click="openHistory('binge', { show_id: b.show_id, date: b.date, title: b.show_title })"
              >
                <div class="li-l">
                  <img v-if="b.poster_url" :src="b.poster_url" style="width: clamp(36px, 10vw, 44px); height: clamp(54px, 15vw, 66px); border-radius: 6px; object-fit: cover; flex-shrink: 0; background: var(--bg-input); border: 1px solid var(--border);" />
                  <div v-else style="width: clamp(36px, 10vw, 44px); height: clamp(54px, 15vw, 66px); border-radius: 6px; flex-shrink: 0; background: var(--bg-input); border: 1px solid var(--border);"></div>
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

        <div v-if="statsStore.activeTab === 'group'" id="sec-group">
            <div class="empty" v-if="!currentStats.group">
                <div class="icon" v-html="icons.users"></div>Вы не состоите в группе
            </div>
            <template v-else>
                <div class="card hoverable anim-item">
                    <div style="display:flex;align-items:center;gap:16px">
                        <div class="icon" style="font-size:clamp(28px, 8vw, 36px);line-height:1;color:var(--info);filter:drop-shadow(0 4px 8px rgba(56, 139, 253, 0.3))" v-html="icons.users"></div>
                        <div>
                            <div style="font-size:clamp(16px, 4.5vw, 20px);font-weight:800;color:var(--text-primary)">{{ currentStats.group.group_name }}</div>
                            <div style="font-size:clamp(12px, 3.2vw, 14px);color:var(--text-muted);font-weight:600;margin-top:2px;">
                              {{ currentStats.group.members_count }} {{ plural(currentStats.group.members_count || 0, ['участник', 'участника', 'участников']) }} · {{ currentStats.group.duration_display }}
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card hoverable anim-item">
                    <div class="label more-pad"><div class="icon" v-html="icons.chart"></div> {{ currentStats.meta.name }} vs Группа</div>
                    <div style="display:flex;justify-content:space-between;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--border)">
                        <span style="font-size:clamp(12px, 3.2vw, 14px);font-weight:800;color:var(--accent);letter-spacing:0.5px;text-transform:uppercase;">👤 {{ currentStats.meta.name }}</span>
                        <span style="font-size:clamp(12px, 3.2vw, 14px);font-weight:800;color:var(--info);letter-spacing:0.5px;text-transform:uppercase;">👥 Группа</span>
                    </div>
                    <div v-for="row in groupCompareRows" :key="row.lb" class="cmp">
                        <span class="cmp-lb"><div class="icon" v-html="row.i"></div>{{ row.lb }}</span>
                        <div class="cmp-vs">
                          <span class="cmp-v cmp-you">{{ row.y }}</span>
                          <span style="color:var(--text-muted);font-size:12px">vs</span>
                          <span class="cmp-v cmp-grp">{{ row.gv }}</span>
                        </div>
                    </div>
                </div>

                <div class="card hoverable anim-item">
                    <div class="label more-pad"><div class="icon" v-html="icons.user"></div> Участники</div>
                    <div v-for="(m, idx) in currentStats.group.members" :key="m.id" class="mb clickable" @click="openGroupMemberHistory(idx, m.name)">
                        <span class="mb-n">{{ m.name }}</span>
                        <div class="mb-t">
                          <div class="mb-f" :style="{ width: (m.views / groupMaxViews * 100) + '%' }"></div>
                        </div>
                        <span class="mb-c">{{ m.views }}</span>
                    </div>
                </div>
            </template>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useStatsStore } from '../stores/useStatsStore'
import { useUIStore } from '../stores/uiStore'
import { useUserStore } from '../stores/userStore'
import { icons } from '../utils/icons'
import { plural } from '../utils/helpers'
import StatCard from '../components/stats/StatCard.vue'
import ActivityHeatmap from '../components/stats/ActivityHeatmap.vue'
import GenreDonut from '../components/stats/GenreDonut.vue'
import LeaderList from '../components/stats/LeaderList.vue'
import BaseChart from '../components/shared/BaseChart.vue'
import BouncyBarChart from '../components/shared/BouncyBarChart.vue'
import { useTelegram } from '../composables/useTelegram'

const statsStore = useStatsStore()
const uiStore = useUIStore()
const userStore = useUserStore()
const { showConfirm } = useTelegram()

const FAKE_STATS = {
  meta: { name: 'Гость', year: 'all', years: ['all'] },
  summary: {
    duration_display: '14д 6ч',
    total_views: 128,
    activity_percent: 64,
    daily_average_min: 105,
    total_episodes: 94,
    unique_series: 8,
    series_duration: '11д 2ч',
    total_movies: 34,
    movies_duration: '3д 4ч',
    wishlist_added: 42,
    wishlist_watched: 12,
    period_label: 'Всё время'
  },
  ratings: {
    total: 86,
    avg: 8.4,
    distribution: [0, 0, 1, 2, 5, 12, 24, 30, 8, 4]
  },
  monthly_chart: {
    labels: ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн'],
    views: [10, 15, 25, 18, 30, 30],
    hours: [8, 12, 20, 15, 24, 25]
  },
  weekday_chart: {
    labels: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
    data: [12, 10, 15, 14, 20, 35, 32]
  },
  heatmap: [],
  genres: [
    { name: 'Драма', minutes: 4200, percent: 35 },
    { name: 'Фантастика', minutes: 3000, percent: 25 },
    { name: 'Комедия', minutes: 2400, percent: 20 },
    { name: 'Боевик', minutes: 1200, percent: 10 },
    { name: 'Триллер', minutes: 1200, percent: 10 }
  ],
  actors: { series: [], others: [] },
  directors: { series: [], others: [] },
  writers: { series: [], others: [] },
  countries: [],
  binges: []
};

const isFakeMode = computed(() => {
  return statsStore.currentStats && statsStore.currentStats.summary?.total_views === 0;
});

const isGamificationMode = computed(() => {
  const views = statsStore.currentStats?.summary?.total_views || 0;
  return views > 0 && views < 10 && !statsStore.isShared;
});

const currentStats = computed(() => {
  return isFakeMode.value ? FAKE_STATS : statsStore.currentStats;
});

const summary = computed(() => currentStats.value?.summary || {})
const userName = computed(() => currentStats.value?.meta?.name || userStore.firstName || '...')
const userPhoto = computed(() => currentStats.value?.meta?.photo_url || userStore.userData?.photo_url)
const firstLetter = computed(() => userName.value.charAt(0).toUpperCase())
const periodLabel = computed(() => summary.value.period_label || '')
const themeIcon = computed(() => uiStore.theme === 'dark' ? icons.moon : icons.sun)

const hasMonthlyData = computed(() => currentStats.value?.monthly_chart?.views?.some(v => v > 0) && !isGamificationMode.value)
const hasWeekdayData = computed(() => currentStats.value?.weekday_chart?.data?.some(v => v > 0) && !isGamificationMode.value)
const hasActorsData = computed(() => (currentStats.value?.actors?.series?.length || currentStats.value?.actors?.others?.length) && !isGamificationMode.value)
const hasDirectorsData = computed(() => (currentStats.value?.directors?.series?.length || currentStats.value?.directors?.others?.length) && !isGamificationMode.value)
const hasWritersData = computed(() => (currentStats.value?.writers?.series?.length || currentStats.value?.writers?.others?.length) && !isGamificationMode.value)
const hasCountriesData = computed(() => currentStats.value?.countries?.length && !isGamificationMode.value)
const hasBingesData = computed(() => currentStats.value?.binges?.length && !isGamificationMode.value)

const ratingColor = computed(() => {
  const avg = currentStats.value?.ratings?.avg || 0
  if (avg >= 8.5) return '#2ea043'; if (avg >= 7.0) return '#388bfd'; if (avg >= 5.5) return '#d29922';
  return '#f85149'
})
const ratingBadgeText = computed(() => {
  const avg = currentStats.value?.ratings?.avg || 0
  if (avg >= 8.5) return 'Восторженный зритель'; if (avg >= 7.0) return 'Позитивный критик';
  if (avg >= 5.5) return 'Объективный судья'; return 'Суровый критик'
})
const ratingBadgeStyle = computed(() => {
  const avg = currentStats.value?.ratings?.avg || 0
  let c = { bg: 'rgba(248, 81, 73, 0.15)', text: '#e74c3c' }
  if (avg >= 8.5) c = { bg: 'rgba(46, 204, 113, 0.15)', text: '#2ecc71' }
  else if (avg >= 7.0) c = { bg: 'rgba(56, 139, 253, 0.15)', text: '#60a5fa' }
  else if (avg >= 5.5) c = { bg: 'rgba(210, 153, 34, 0.15)', text: '#d29922' }
  return { backgroundColor: c.bg, color: c.text }
})

const ratingsChartData = computed(() => {
  const dist = currentStats.value?.ratings?.distribution || [];
  const palette = ['#f85149', '#f85149', '#e67e22', '#e67e22', '#d29922', '#d29922', '#388bfd', '#388bfd', '#2ea043', '#39d353'];
  const pressPalette = ['#d32f2f', '#d32f2f', '#c2410c', '#c2410c', '#b45309', '#b45309', '#1d4ed8', '#1d4ed8', '#15803d', '#166534'];
  
  return {
    labels: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'],
    datasets: [{
      data: dist,
      backgroundColor: palette,
      hoverBackgroundColor: pressPalette,
      borderRadius: 6,
      borderWidth: 0,
      borderSkipped: false,
      hoverInflateAmount: -5 
    }]
  };
});

const ratingsChartOptions = computed(() => {
  const isDark = uiStore.theme === 'dark';
  const c = {
    t: isDark ? 'rgba(229, 231, 235, .8)' : 'rgba(31, 35, 40, .8)',
    b: isDark ? '#2d333b' : '#d0d7de'
  };
  const fSize = Math.max(10, Math.min(13, window.innerWidth * 0.03));

  return {
    responsive: true,
    maintainAspectRatio: false,
    transitions: {
      active: {
        animation: {
          duration: 200,
          easing: 'easeOutBack'
        }
      }
    },
    animation: {
      duration: 1000,
      easing: 'easeOutBack',
      delay: (context) => (context.type === 'data' && context.mode === 'default' && !context.active) ? context.dataIndex * 40 : 0
    },
    onHover: (event, activeElements) => {
      event.native.target.style.cursor = activeElements.length ? 'pointer' : 'default';
    },
    onClick: (event, activeElements) => {
      if (activeElements.length > 0) {
        if (window.navigator.vibrate) window.navigator.vibrate(10);
        const score = activeElements[0].index + 1;
        openHistory('rating_filter', { idx: score, title: `Оценка: ${score}` });
      }
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: isDark ? 'rgba(22, 27, 34, 0.95)' : 'rgba(255, 255, 255, 0.95)',
        titleColor: isDark ? '#f0f6fc' : '#1f2328',
        bodyColor: isDark ? '#8b949e' : '#59636e',
        borderColor: c.b,
        borderWidth: 1,
        cornerRadius: 10,
        padding: 12,
        displayColors: false,
        callbacks: {
          title: (ctx) => `Оценка: ${ctx[0].label}`,
          label: (ctx) => ` ${ctx.parsed.y} ${plural(ctx.parsed.y, ['оценка', 'оценки', 'оценок'])}`
        }
      }
    },
    scales: {
      x: { ticks: { color: c.t, font: { size: fSize, weight: '700' } }, grid: { display: false } },
      y: { display: false, beginAtZero: true }
    }
  };
});


const monthlyChartData = computed(() => {
  const ch = currentStats.value?.monthly_chart || { labels: [], views: [], hours: [] };
  
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
  const isDark = uiStore.theme === 'dark';
  const textColor = isDark ? 'rgba(229, 231, 235, .8)' : 'rgba(31, 35, 40, .8)';
  const gridColor = isDark ? 'rgba(255, 255, 255, .05)' : 'rgba(0, 0, 0, .05)';
  const borderColor = isDark ? '#2d333b' : '#d0d7de';
  const fSize = Math.max(10, Math.min(13, window.innerWidth * 0.03));

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
        ticks: { color: '#60a5fa', font: { size: fSize } },
        grid: { drawOnChartArea: false },
        beginAtZero:true
      }
    }
  }
})

const weekdayChartData = computed(() => {
  const ch = currentStats.value?.weekday_chart || { labels: [], data: [] };
  const barColor = '#2ea043';
  const weekendColor = '#388bfd';
  const pressBar = '#166534';
  const pressWeekend = '#1d4ed8';

  return {
    labels: ch.labels,
    datasets: [{
      data: ch.data,
      backgroundColor: ch.data.map((_, i) => i >= 5 ? weekendColor : barColor),
      hoverBackgroundColor: ch.data.map((_, i) => i >= 5 ? pressWeekend : pressBar),
      borderRadius: 8,
      borderWidth: 0,
      borderSkipped: false,
      hoverInflateAmount: -5
    }]
  };
});

const weekdayChartOptions = computed(() => {
  const isDark = uiStore.theme === 'dark';
  const c = {
    t: isDark ? 'rgba(229, 231, 235, .8)' : 'rgba(31, 35, 40, .8)',
    g: isDark ? 'rgba(255, 255, 255, .05)' : 'rgba(0, 0, 0, .05)'
  };
  const totalViews = currentStats.value?.weekday_chart?.data.reduce((a, b) => a + b, 0) || 0;
  const fSize = Math.max(10, Math.min(13, window.innerWidth * 0.03));

  return {
    responsive: true,
    maintainAspectRatio: false,
    transitions: {
      active: {
        animation: {
          duration: 200,
          easing: 'easeOutBack'
        }
      }
    },
    animation: {
      duration: 1000,
      easing: 'easeOutBack',
      delay: (context) => (context.type === 'data' && context.mode === 'default' && !context.active) ? context.dataIndex * 60 : 0
    },
    onHover: (event, activeElements) => {
      event.native.target.style.cursor = activeElements.length ? 'pointer' : 'default';
    },
    onClick: (event, activeElements) => {
      if (activeElements.length > 0) {
        if (window.navigator.vibrate) window.navigator.vibrate(10);
        const idx = activeElements[0].index;
        const fullDays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];
        openHistory('weekday', { idx: idx, title: fullDays[idx] });
      }
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: isDark ? 'rgba(22, 27, 34, 0.95)' : 'rgba(255, 255, 255, 0.95)',
        titleColor: isDark ? '#f0f6fc' : '#1f2328',
        bodyColor: isDark ? '#8b949e' : '#59636e',
        borderWidth: 0,
        cornerRadius: 10,
        padding: 12,
        displayColors: false,
        callbacks: {
          label: (context) => {
            const val = context.parsed.y;
            const pct = totalViews > 0 ? Math.round((val / totalViews) * 100) : 0;
            return ` ${val} ${plural(val, ['просмотр', 'просмотра', 'просмотров'])} (${pct}%)`;
          }
        }
      }
    },
    scales: {
      x: { ticks: { color: c.t, font: { size: fSize, weight: '700' } }, grid: { display: false } },
      y: { ticks: { color: c.t, font: { size: fSize }, precision: 0 }, grid: { color: c.g }, beginAtZero: true, border: { display: false } }
    }
  };
});

const groupCompareRows = computed(() => {
    const g = currentStats.value?.group; if (!g) return []
    const p = currentStats.value.summary
    return [
        { lb: 'Просмотры', i: icons.tv, y: p.total_views, gv: g.total_views },
        { lb: 'Эпизоды', i: icons.film, y: p.total_episodes, gv: g.total_episodes },
        { lb: 'Фильмы', i: icons.time, y: p.total_movies, gv: g.total_movies },
        { lb: 'Уникальных', i: icons.star, y: p.unique_shows, gv: g.unique_shows }
    ]
})
const groupMaxViews = computed(() => Math.max(...(currentStats.value?.group?.members || []).map(m => m.views), 1))

const handleWishlistClick = () => {
  if (statsStore.isShared) return
  uiStore.switchBaseView('wishlist')
}

const openHistory = (type, props = {}) => {
  uiStore.openLayer('history', type, props)
}

const openGroupMemberHistory = (index, name) => {
  openHistory('group_member', { idx: index, title: name })
}

const handleHeatmapClick = ({ date, value }) => value > 0 && openHistory('day', { date: date, title: date })

onMounted(() => { if (!statsStore.currentStats) statsStore.fetchStats(statsStore.currentYear) })
</script>

<style scoped>
.centered-stat-btn::after {
    top: 50% !important;
    transform: translateY(-50%) rotate(45deg) !important;
    right: 20px !important;
}
</style>