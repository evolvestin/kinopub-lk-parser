<template>
  <div class="view active-view" style="display: flex; flex-direction: column;">
    
    <!-- Header remains the same as Iteration 4 -->
    <div class="header">
      <div class="header-left">
        <div class="avatar" id="avatar">
          <img v-if="userPhoto" :src="userPhoto" alt="A">
          <template v-else>{{ firstLetter }}</template>
        </div>
        <div>
          <div class="header-name glow-text">{{ userName }}</div>
          <div class="header-sub">{{ periodLabel }}</div>
        </div>
      </div>
      <div class="top-controls">
        <button class="share-btn" @click="openShareModal">
          <span v-html="icons.chart"></span>
        </button>
        <button class="theme-btn" @click="uiStore.toggleTheme">
          <span v-html="themeIcon"></span>
        </button>
      </div>
    </div>

    <!-- Tabs & Years from Iteration 4 -->
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
        class="yr clickable" 
        :class="{ on: statsStore.currentYear === 'all' }" 
        @click="statsStore.setYear('all')"
      >Всё время</button>
      <button 
        v-for="year in statsStore.availableYears.filter(y => y !== 'all')" 
        :key="year"
        class="yr clickable" 
        :class="{ on: String(statsStore.currentYear) === String(year) }" 
        @click="statsStore.setYear(year)"
      >{{ year }}</button>
    </div>

    <div v-if="statsStore.currentStats && statsStore.activeTab === 'personal'" id="sec-personal">
      <div class="label"><div class="icon" v-html="icons.dash"></div> Обзор</div>
      
      <div class="grid">
        <StatCard
          :icon="icons.time"
          :value="summary.duration_display || '0м'"
          label="Время просмотра"
          :sub-value="summary.total_views"
          :sub-label="plural(summary.total_views, ['просмотр', 'просмотра', 'просмотров'])"
          :clickable="true"
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
          :sub-value="summary.unique_series || 0"
          :sub-label="plural(summary.unique_series, ['сериал', 'сериала', 'сериалов'])"
          sub-color-class="purple"
          :clickable="true"
        />
        <StatCard
          :icon="icons.film"
          :value="summary.total_movies || 0"
          label="Фильмов"
          :sub-value="summary.movies_duration || '0м'"
          sub-color-class="orange"
          :clickable="true"
        />
      </div>

      <!-- NEW: Heatmap -->
      <ActivityHeatmap 
        v-if="statsStore.currentStats.heatmap?.length"
        :years-data="statsStore.currentStats.heatmap"
      />

      <!-- NEW: Genres -->
      <GenreDonut 
        v-if="statsStore.currentStats.genres?.length"
        :genres="statsStore.currentStats.genres"
        :total-minutes="summary.total_minutes_watched"
        :is-dark="uiStore.theme === 'dark'"
      />

      <!-- NEW: Leader Lists -->
      <LeaderList 
        v-if="statsStore.currentStats.actors"
        title="Актёры"
        :icon="icons.masks"
        icon-color="#d29922"
        :data="statsStore.currentStats.actors"
      />

      <LeaderList 
        v-if="statsStore.currentStats.directors"
        title="Режиссёры"
        :icon="icons.film"
        icon-color="#e74c3c"
        :data="statsStore.currentStats.directors"
      />

      <!-- Countries List (Flat) -->
      <div class="card hoverable anim-item" v-if="statsStore.currentStats.countries?.length">
        <div class="label">
            <div class="icon" style="color: #388bfd;" v-html="icons.globe"></div>
            Страны
        </div>
        <div 
          v-for="(c, idx) in statsStore.currentStats.countries" 
          :key="c.name"
          class="li li-clickable anim-list-item clickable"
        >
            <div class="li-l">
                <span class="li-rank">{{ idx + 1 }}</span>
                <div class="li-name">
                    <span style="font-size: 22px; margin-right: 8px;">{{ c.emoji }}</span>
                    {{ c.name }}
                </div>
            </div>
            <span class="li-r" style="color: var(--info)">{{ c.count }}</span>
        </div>
      </div>

    </div>

    <div v-if="statsStore.currentStats && statsStore.activeTab === 'group'" id="sec-group">
        <!-- Group stats will be Iteration 7 refinement -->
        <EmptyState icon="users" text="Групповая статистика в разработке" />
    </div>

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
import EmptyState from '../components/shared/EmptyState.vue'

const statsStore = useStatsStore()
const uiStore = useUIStore()
const userStore = useUserStore()

const themeIcon = computed(() => uiStore.theme === 'dark' ? icons.moon : icons.sun)
const userName = computed(() => statsStore.currentStats?.meta?.name || userStore.firstName || 'Загрузка…')
const userPhoto = computed(() => statsStore.currentStats?.meta?.photo_url || userStore.userData?.photo_url)
const firstLetter = computed(() => userName.value.charAt(0).toUpperCase())
const summary = computed(() => statsStore.currentStats?.summary || {})
const periodLabel = computed(() => summary.value.period_label || '')

onMounted(() => {
  if (!statsStore.currentStats) {
    statsStore.fetchStats('all')
  }
})

const openShareModal = () => console.log('Share')
</script>