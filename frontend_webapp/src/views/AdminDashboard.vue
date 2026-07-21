<template>
  <div class="webapp-container">
    <div class="layer-header">
      <div class="header-container">
        <div class="header-title">KinoPub Observer</div>
        <div class="wa-nav-links">
          <a href="/metrics/" class="wa-nav-btn active">Метрики</a>
          <a href="/admin/" class="wa-nav-btn">Админка</a>
          <a href="/admin/tasks/" class="wa-nav-btn">Задачи</a>
        </div>
        <div></div>
      </div>
      <div class="period-switcher-row">
        <div class="period-tabs-small">
          <button class="tab" :class="{ on: activePeriod === 'now' }" @click="activePeriod = 'now'">Сейчас</button>
          <button class="tab" :class="{ on: activePeriod === 'yesterday' }" @click="activePeriod = 'yesterday'">Вчера</button>
          <button class="tab" :class="{ on: activePeriod === 'week_ago' }" @click="activePeriod = 'week_ago'">7 дней назад</button>
        </div>
        <div id="data-timestamp">{{ dataTimestamp }}</div>
      </div>
    </div>

    <div id="system-status-container">
      <div style="padding-left: 35px; margin-bottom: 4px; margin-top: 10px; display: flex; align-items: center; gap: 8px; color: var(--text-muted); font-weight: 700; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.8;">
        <div class="icon" style="width:16px; height:16px; display: flex; align-items: center;" v-html="icons.time"></div>
        Системный статус
        <span class="live-indicator-badge">
          <span class="live-dot"></span>
          актуально сейчас
        </span>
      </div>
      <div class="status-grid">
        <div class="status-card" v-for="(stat, i) in systemStats" :key="i">
          <div class="status-icon-wrap" :style="{ background: stat.bg, color: stat.color }">
            <div class="icon" v-html="icons[stat.icon]"></div>
          </div>
          <div class="status-info">
            <div class="status-label">{{ stat.label }}</div>
            <div class="status-val">{{ stat.val }}</div>
          </div>
        </div>
      </div>
    </div>

    <template v-for="(group, groupIdx) in metricGroups" :key="groupIdx">
      <div style="padding-left: 35px; margin-top: 24px; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; color: var(--text-primary); font-weight: 800; font-size: 18px; text-transform: uppercase;">
        <div class="icon" :style="{ color: group.color }" v-html="icons[group.icon]"></div>
        {{ group.title }}
      </div>
      
      <div class="metrics-grid">
        <div class="card hoverable anim-item" v-for="metric in group.metrics" :key="metric.key" :class="{ 'critical-glow': getMetricTotal(metric.key) > 0 && metric.severity === 'critical' }">
          <div class="label label-clickable" @click="metric.showDesc = !metric.showDesc">
            <div class="icon" :style="{ color: metric.color }" v-html="icons[metric.icon]"></div>
            {{ metric.label }}
            <div class="js-ic-help" style="margin-left:auto; opacity:0.5; width: 18px; height: 18px; display: flex;" v-html="icons.help"></div>
          </div>
          <div class="metric-desc" :class="{ visible: metric.showDesc }">{{ metric.desc }}</div>
          
          <template v-if="!hasData(metric.key)">
            <div class="empty-overlay" style="display:flex;flex-direction:column;align-items:center;justify-content:center;flex-grow:1;min-height:180px;text-align:center;">
              <template v-if="!getMetricTimestamp(metric.key)">
                <div style="font-size:36px;margin-bottom:8px;opacity:0.5;">⏳</div>
                <div style="color:var(--text-muted);font-weight:800;font-size:16px;text-transform:uppercase;letter-spacing:0.5px;">Нет данных</div>
                <div style="font-size:12px;color:var(--text-muted);margin-top:4px;opacity:0.7;">Метрика еще не рассчитывалась</div>
              </template>
              <template v-else>
                <div style="font-size:36px;margin-bottom:8px;filter:drop-shadow(0 0 8px rgba(46, 204, 113, 0.3));">✅</div>
                <div style="color:var(--accent);font-weight:800;font-size:16px;text-transform:uppercase;letter-spacing:0.5px;">Проблем не найдено</div>
              </template>
            </div>
          </template>
          
          <template v-else>
            <BaseChart 
              type="doughnut" 
              :data="getChartData(metric)" 
              :options="getChartOptions(metric)" 
              :plugins="[ChartDataLabels, getCenterPlugin(metric)]" 
              :height="280" 
            />
            <div class="legend-grid" v-if="getMetricData(metric.key).length > 1">
              <div v-for="(item, i) in getMetricData(metric.key)" :key="i" class="legend-item clickable" @click="openDetails(metric.key, item.name || item.type)">
                <div class="legend-dot" :style="{ background: getPaletteColor(metric.severity, i) }"></div>
                <div class="legend-name">{{ item.name || item.type }}</div>
                <div class="legend-val">{{ item[metric.valField].toLocaleString('ru-RU') }} ({{ formatPercentage(metric.key, item.name || item.type, item[metric.valField]) }})</div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </template>

    <!-- Модалка Детализации -->
    <div class="modal-overlay" :class="{ show: isModalOpen }" @click.self="closeDetails">
      <div class="modal-content" :class="{ 'modal-wide': modalItems.length >= 5 }">
        <div class="modal-header">
          <div class="modal-title">{{ modalTitle }}</div>
          <button class="modal-close" @click="closeDetails">×</button>
        </div>
        <div v-if="isModalLoading" style="text-align:center; padding: 20px;">
          <div class="spinner" style="width:30px; height:30px; display:inline-block;"></div>
        </div>
        <div v-else class="modal-body-list" ref="modalListRef">
          <div v-if="!ctx.is_authenticated" class="empty" style="grid-column: 1/-1; padding: 40px 20px;">
            <div style="font-size: 48px; margin-bottom: 16px;">🔒</div>
            <div style="font-size: 16px; font-weight: 700; margin-bottom: 12px; color: var(--text-primary);">
              Авторизуйтесь для просмотра детализации
            </div>
            <a href="/admin/login/?next=/" class="add-all-btn" style="text-decoration: none; display: inline-flex; justify-content: center; align-items: center; width: auto; margin: 0 auto;">
              Войти в систему
            </a>
          </div>
          <div v-else-if="modalDataContext.is_summary" class="empty" style="grid-column: 1/-1; padding: 40px 20px;">
            <div style="font-size: 48px; margin-bottom: 16px;">📊</div>
            <div style="font-size: 16px; font-weight: 700; margin-bottom: 12px; color: var(--text-primary);">
              Открыть полный список
            </div>
            <a :href="modalDataContext.admin_url" target="_blank" class="add-all-btn" style="text-decoration: none; display: inline-flex; justify-content: center; align-items: center; width: auto; margin: 0 auto;">
              Открыть список в админке
            </a>
          </div>
          <div v-else-if="!modalItems.length" class="empty" style="grid-column: 1/-1;">Ничего не найдено</div>
          <template v-else>
            <div v-for="item in visibleModalItems" :key="item.id || item.name" class="modal-item" :class="{ 'merge-card': item.is_duplicate_group && item.persons }" :id="item.is_duplicate_group && item.persons ? `merge-group-${item.persons[0].id}` : `mi-${item.id}`" :style="{ minHeight: modalDataContext.is_genre || modalDataContext.is_country ? '60px' : '110px' }">
              
              <!-- Жанры -->
              <div v-if="modalDataContext.is_genre" class="modal-item-content">
                <div v-if="item.is_duplicate_group && item.names" class="modal-item-info" style="padding: 15px 20px;">
                  <div style="color: var(--danger); font-weight: 800; font-size: 12px; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px;">Найдены дубликаты:</div>
                  <div style="font-size: 15px; color: var(--text-primary); line-height: 1.4; margin-bottom: 12px;">
                    <div v-for="name in item.names" :key="name" style="margin-bottom:2px;">• {{ name }}</div>
                  </div>
                  <a :href="item.admin_url" target="_blank" class="nav-btn" style="width: fit-content; padding: 6px 14px; font-size: 12px; background: var(--bg-card);">Посмотреть в админке</a>
                </div>
                <div class="modal-item-info" style="flex-direction:row; justify-content:space-between; align-items:center; padding: 15px 20px;">
                  <div class="modal-item-title" style="margin:0; font-size: 16px;">{{ item.name }}</div>
                  <a :href="item.admin_url" target="_blank" class="nav-btn" style="padding:8px 16px; font-size:13px; height:auto; background: var(--bg-card);">Правка</a>
                </div>
              </div>

              <!-- Страны -->
              <div v-else-if="modalDataContext.is_country" class="modal-item-content">
                <div class="modal-item-info" style="flex-direction:row; justify-content:space-between; align-items:center; padding: 15px 20px;">
                  <div class="modal-item-title" style="margin:0; display:flex; align-items:center; font-size: 16px;">
                    <span v-if="item.emoji_flag" style="margin-right:10px; font-size: 1.2em;">{{ item.emoji_flag }}</span> {{ item.name }}
                  </div>
                  <a :href="item.admin_url" target="_blank" class="nav-btn" style="padding:6px 16px; font-size:13px; height:auto; background: var(--bg-card);">Правка</a>
                </div>
              </div>

              <!-- Персоны (Дубликаты) -->
              <template v-else-if="modalDataContext.is_person && item.is_duplicate_group && item.persons">
                <div class="merge-header">
                  <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <span style="font-size: 11px; font-weight: 800; color: var(--accent); text-transform: uppercase; letter-spacing: 0.5px;">Группа дубликатов</span>
                    <a :href="item.admin_url" target="_blank" class="edit-link" style="opacity: 1; color: var(--info); font-size: 10px;">[Админка]</a>
                    
                    <span v-if="item.kp_status === 'same'" style="font-size: 10px; font-weight: 800; color: #2ecc71; background: rgba(46, 204, 113, 0.15); padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">Фото KP совпадают</span>
                    <span v-else-if="item.kp_status === 'different'" style="font-size: 10px; font-weight: 800; color: #e74c3c; background: rgba(231, 76, 60, 0.15); padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">Фото KP отличаются</span>
                    <span v-else-if="item.kp_status === 'partial'" style="font-size: 10px; font-weight: 800; color: #f1c40f; background: rgba(241, 196, 15, 0.15); padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">Фото KP частично совпадают</span>
                    <span v-else-if="item.kp_status === 'missing'" style="font-size: 10px; font-weight: 800; color: #9ca3af; background: rgba(156, 163, 175, 0.15); padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">Нет фото KP</span>

                    <span v-if="item.tmdb_status === 'same'" style="font-size: 10px; font-weight: 800; color: #2ecc71; background: rgba(46, 204, 113, 0.15); padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">Фото TMDB совпадают</span>
                    <span v-else-if="item.tmdb_status === 'different'" style="font-size: 10px; font-weight: 800; color: #e74c3c; background: rgba(231, 76, 60, 0.15); padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">Фото TMDB отличаются</span>
                    <span v-else-if="item.tmdb_status === 'partial'" style="font-size: 10px; font-weight: 800; color: #f1c40f; background: rgba(241, 196, 15, 0.15); padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">Фото TMDB частично совпадают</span>
                    <span v-else-if="item.tmdb_status === 'missing'" style="font-size: 10px; font-weight: 800; color: #9ca3af; background: rgba(156, 163, 175, 0.15); padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">Нет фото TMDB</span>
                  </div>
                  <button class="btn-merge-action" @click="executeMerge(item.persons[0].id, item.persons)">Объединить</button>
                </div>
                <div class="merge-content">
                  <div class="merge-poster-area">
                    <img :src="item.tmdb_photo_url || item.kp_photo_url || fallbackIcon" alt="avatar">
                  </div>
                  <div class="merge-list">
                    <label v-for="p in item.persons" :key="p.id" class="merge-row" :class="{ 'is-master': p.id === mergeSelections[item.persons[0].id] }" @click="mergeSelections[item.persons[0].id] = p.id">
                      <input type="radio" :value="p.id" v-model="mergeSelections[item.persons[0].id]">
                      <div class="person-details-box">
                        <div class="person-meta-row">
                          <span class="person-name">{{ p.name }}</span>
                          <span class="person-id-badge">#{{ p.id }}</span>
                        </div>
                        <div v-if="p.en_name" class="person-en-name">{{ p.en_name }}</div>
                        <div style="margin-top: 6px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                          <div v-if="p.tmdb_photo_url" style="display: flex; align-items: center; gap: 6px;">
                            <img :src="p.tmdb_photo_url" style="width: 20px; height: 20px; border-radius: 50%; object-fit: cover; border: 1px solid var(--border);" alt="TMDB">
                            <span style="font-size: 11px; color: var(--text-muted);">TMDB</span>
                          </div>
                          <div v-if="p.kp_photo_url" style="display: flex; align-items: center; gap: 6px;">
                            <img :src="p.kp_photo_url" style="width: 20px; height: 20px; border-radius: 50%; object-fit: cover; border: 1px solid var(--border);" alt="KP">
                            <span style="font-size: 11px; color: var(--text-muted);">KP</span>
                          </div>
                        </div>
                      </div>
                      <a :href="`/admin/app/person/${p.id}/change/`" target="_blank" class="edit-link-btn-small" @click.stop>Правка</a>
                    </label>
                  </div>
                </div>
              </template>

              <!-- Персоны (Одиночные) -->
              <template v-else-if="modalDataContext.is_person">
                <img :src="item.poster_url || fallbackIcon" class="modal-item-poster" alt="avatar" style="width: 80px; object-fit: cover;">
                <div class="modal-item-content">
                  <div class="modal-item-info" style="flex-direction:row; justify-content:space-between; align-items:center; padding: 15px 20px;">
                    <div style="min-width: 0; padding-right: 15px;">
                      <div class="modal-item-title" style="margin:0; font-size: 15px;">{{ item.name }}</div>
                      <div class="modal-item-orig" style="margin-top: 4px;">{{ item.en_name || '' }}</div>
                    </div>
                    <a :href="item.admin_url" target="_blank" class="nav-btn" style="padding:8px 16px; font-size:13px; height:auto; background: var(--bg-card); flex-shrink: 0;">Правка</a>
                  </div>
                </div>
              </template>

              <!-- Обычные Шоу -->
              <template v-else>
                <img :src="item.poster_url" class="modal-item-poster" alt="poster" loading="lazy">
                <div class="modal-item-content">
                  <div class="modal-item-info">
                    <div class="modal-item-title">{{ item.title }}</div>
                    <div class="modal-item-orig">{{ item.original_title || '' }}</div>
                  </div>
                  <div class="modal-item-actions">
                    <button class="queue-btn" :disabled="item.in_queue" @click="addToQueue(item)">
                      <span>{{ item.in_queue ? 'В очереди' : (currentTargetTask === 'priority_sync' ? 'Синхронизировать' : (currentTargetTask === 'durations' ? 'Обновить время' : 'Обновить детали')) }}</span>
                    </button>
                    <a :href="item.kinopub_url" target="_blank" class="admin-link-btn" style="color: var(--accent); border-right: 1px solid var(--border);" title="Открыть на Кинопабе">На Кинопабе</a>
                    <a :href="item.admin_url" target="_blank" class="admin-link-btn" title="Открыть в админке">В админке</a>
                  </div>
                </div>
              </template>
            </div>
            <div ref="sentinelRef" style="height: 40px; width: 100%; grid-column: 1/-1;"></div>
          </template>
        </div>
        <div class="modal-footer" v-if="modalItems.length && !modalDataContext.is_genre && !modalDataContext.is_country && !modalDataContext.is_person">
          <button class="add-all-btn" :disabled="pendingQueueIds.length === 0 || isBatchQueuing" @click="addAllToQueue">
            <div v-if="isBatchQueuing" class="spinner" style="width:16px;height:16px;border-width:2px;border-top-color:#fff;margin:0;"></div>
            <span v-else>{{ pendingQueueIds.length === 0 ? 'Все добавлены в очередь' : `В очередь ${currentTargetTask === 'priority_sync' ? 'на синхронизацию' : (currentTargetTask === 'durations' ? 'длительности' : 'на обновление')} (${pendingQueueIds.length})` }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onUnmounted, onMounted, watch } from 'vue'
import BaseChart from '../components/shared/BaseChart.vue'
import { icons } from '../utils/icons'
import ChartDataLabels from 'chartjs-plugin-datalabels'

const allMetrics = window.ALL_METRICS || {}
const adminApps = window.ADMIN_APP_LIST || []
const ctx = window.ADMIN_CONTEXT || {}

const fallbackIcon = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%239ca3af"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>`

const activePeriod = ref('now')

const dataTimestamp = computed(() => {
  const ts = allMetrics.missing_kp?.[activePeriod.value]?.timestamp
  return ts ? `${ts} UTC` : 'Данные отсутствуют'
})

const systemStats = computed(() => [
  { label: 'Последний просмотр', val: ctx.last_actions?.history || '—', icon: 'chart', bg: 'rgba(56, 139, 253, 0.15)', color: '#388bfd' },
  { label: 'Запуск парсера', val: ctx.last_actions?.parser_run || '—', icon: 'zap', bg: 'rgba(163, 113, 247, 0.15)', color: '#a371f7' },
  { label: 'Новые релизы', val: ctx.last_actions?.shows || '—', icon: 'play_circle', bg: 'rgba(46, 160, 67, 0.15)', color: '#2ea043' },
  { label: 'Рейтинги (KP/IMDb)', val: ctx.last_actions?.ratings || '—', icon: 'star', bg: 'rgba(241, 196, 15, 0.15)', color: '#f1c40f' },
  { label: 'Хронометраж', val: ctx.last_actions?.durations || '—', icon: 'time', bg: 'rgba(163, 113, 247, 0.15)', color: '#a371f7' },
  { label: 'Фото персон', val: ctx.last_actions?.photos || '—', icon: 'user', bg: 'rgba(231, 76, 60, 0.15)', color: '#e74c3c' },
  { label: 'Активность Telegram', val: ctx.last_actions?.tg || '—', icon: 'check', bg: 'rgba(46, 204, 113, 0.15)', color: '#2ecc71' },
  { label: 'Пользователи бота', val: `${ctx.bot_users_active || 0} / ${ctx.bot_users_total || 0}`, icon: 'users', bg: 'rgba(96, 165, 250, 0.15)', color: '#60a5fa' },
  { label: 'Ошибки (24ч)', val: ctx.errors_24h_count || 0, icon: 'ghost', bg: 'rgba(96, 165, 250, 0.15)', color: '#60a5fa' }
])

const PALETTES = {
  critical: [['#ff4b4b', '#c92a2a'], ['#ff7b72', '#d2544e'], ['#e67e22', '#b35d18'], ['#d29922', '#a07416'], ['#a371f7', '#7b4bc6'], ['#ef1960', '#b31248']],
  warning: [['#e67e22', '#b35d18'], ['#d29922', '#a07416'], ['#f1c40f', '#b7950b'], ['#388bfd', '#1f6feb'], ['#a371f7', '#7b4bc6'], ['#1abc9c', '#117a65']],
  info: [['#388bfd', '#1f6feb'], ['#1abc9c', '#117a65'], ['#2ea043', '#238636'], ['#a371f7', '#7b4bc6'], ['#60a5fa', '#3b82f6'], ['#9b59b6', '#71368a']]
}

const metricGroups = ref([
  {
    title: 'Метаданные', icon: 'star', color: 'var(--info)',
    metrics: [
      { key: 'total_shows', icon: 'tv', color: '#9b59b6', label: 'Всего шоу', centerLabel: 'ВСЕГО ШОУ', valField: 'value', severity: 'info', desc: 'Общее количество фильмов, сериалов и других типов шоу в базе данных.', showDesc: false },
      { key: 'missing_year', icon: 'cal', color: '#e67e22', label: 'Год не указан', centerLabel: 'БЕЗ ГОДА', valField: 'value', severity: 'critical', desc: 'Шоу, у которых в нашей базе не заполнен год выхода.', showDesc: false },
      { key: 'missing_status', icon: 'target', color: '#ef1960', label: 'Статус не указан', centerLabel: 'БЕЗ СТАТУСА', valField: 'value', severity: 'critical', desc: 'Сериалы и ТВ-шоу, у которых в базе отсутствует статус (Завершен/В эфире).', showDesc: false },
      { key: 'title_collision', icon: 'edit', color: 'var(--info)', label: 'Коллизии названий', centerLabel: 'КОЛЛИЗИЙ', valField: 'collisions', severity: 'critical', desc: 'Случаи, когда основное название шоу содержит в себе оригинальное (например, "Интерстеллар Interstellar").', showDesc: false },
      { key: 'missing_durations', icon: 'time', color: '#6887ff', label: 'Без хронометража', centerLabel: 'БЕЗ ХРОНОМ.', valField: 'value', severity: 'critical', desc: 'Шоу, для которых в базе нет данных о времени (секундах) эпизодов или фильма.', showDesc: false },
      { key: 'missing_plot', icon: 'list', color: '#1abc9c', label: 'Нет описания', centerLabel: 'БЕЗ ОПИС.', valField: 'value', severity: 'critical', desc: 'Шоу, у которых в базе отсутствует или пустое текстовое описание.', showDesc: false }
    ]
  },
  {
    title: 'Жанры', icon: 'masks', color: '#f1c40f',
    metrics: [
      { key: 'total_genres', icon: 'masks', color: 'var(--info)', label: 'Всего жанров', centerLabel: 'ЖАНРОВ', valField: 'value', severity: 'info', desc: 'Общее количество уникальных жанров в базе.', showDesc: false },
      { key: 'no_genres', icon: 'frown', color: '#f1c40f', label: 'Нет жанра', centerLabel: 'БЕЗ ЖАНРА', valField: 'value', severity: 'critical', desc: 'Шоу, к которым не привязан ни один жанр.', showDesc: false },
      { key: 'unmapped_genres', icon: 'skull', color: 'var(--danger)', label: 'Нераспознанные жанры', centerLabel: 'НЕ РАСПОЗНАНО', valField: 'value', severity: 'critical', desc: 'Жанры, которые не были найдены в маппинге констант.', showDesc: false }
    ]
  },
  {
    title: 'Рейтинги', icon: 'star', color: 'var(--accent)',
    metrics: [
      { key: 'has_kp', icon: 'smile', color: 'var(--info)', label: 'Есть рейтинг KP', centerLabel: 'С РЕЙТИНГОМ', valField: 'value', severity: 'info', desc: 'Шоу, у которых успешно собран и сохранен рейтинг Кинопоиска.', showDesc: false },
      { key: 'missing_kp', icon: 'frown', color: 'var(--danger)', label: 'Нет рейтинга KP', centerLabel: 'БЕЗ РЕЙТИНГА', valField: 'value', severity: 'critical', desc: 'Шоу, у которых в нашей базе есть ссылка на Кинопоиск, но отсутствует сам рейтинг.', showDesc: false },
      { key: 'has_imdb', icon: 'smile', color: 'var(--accent)', label: 'Есть рейтинг IMDb', centerLabel: 'С РЕЙТИНГОМ', valField: 'value', severity: 'info', desc: 'Шоу, у которых успешно собран и сохранен рейтинг IMDb.', showDesc: false },
      { key: 'missing_imdb', icon: 'frown', color: '#f1c40f', label: 'Нет рейтинга IMDb', centerLabel: 'БЕЗ IMDB', valField: 'value', severity: 'critical', desc: 'Шоу, у которых указана ссылка на IMDb, но в таблице внешних рейтингов данные отсутствуют.', showDesc: false },
    ]
  },
  {
    title: 'География', icon: 'globe', color: '#388bfd',
    metrics: [
      { key: 'total_countries', icon: 'globe', color: '#388bfd', label: 'Всего стран', centerLabel: 'СТРАН', valField: 'value', severity: 'info', desc: 'Статистика базы стран.', showDesc: false },
      { key: 'no_countries', icon: 'minus', color: '#2ea043', label: 'Нет страны', centerLabel: 'БЕЗ СТРАНЫ', valField: 'value', severity: 'critical', desc: 'Шоу, к которым не привязна ни одна страна производства.', showDesc: false },
      { key: 'missing_country_meta', icon: 'target', color: 'var(--danger)', label: 'Страны без ISO кода', centerLabel: 'БЕЗ ISO', valField: 'value', severity: 'critical', desc: 'Страны, для которых не заполнен ISO код или отсутствует флаг Эмодзи.', showDesc: false }
    ]
  },
  {
    title: 'Люди и роли', icon: 'users', color: '#9b59b6',
    metrics: [
      { key: 'duplicate_photo_urls', icon: 'users', color: '#ef1960', label: 'Дубликаты людей', centerLabel: 'ДУБЛИКАТОВ', valField: 'value', severity: 'critical', desc: 'Разные записи людей с совпадающими аватарками.', showDesc: false },
      { key: 'total_persons_by_show_type', icon: 'user', color: '#388bfd', label: 'Персоны в базе', centerLabel: 'ПЕРСОН', valField: 'value', severity: 'info', desc: 'Количество уникальных людей в различных типах шоу.', showDesc: false },
      { key: 'persons_avatar_stats', icon: 'eye', color: '#e67e22', label: 'Наличие фотографий', centerLabel: 'С ФОТО', valField: 'value', severity: 'warning', desc: 'Соотношение загруженных фото для людей.', showDesc: false },
      { key: 'professions_stats', icon: 'rocket', color: '#1abc9c', label: 'Роли в кино', centerLabel: 'РОЛЕЙ', valField: 'value', severity: 'info', desc: 'Топ уникальных профессий.', showDesc: false },
      { key: 'en_professions_stats', icon: 'gear', color: '#a371f7', label: 'Роли в кино (EN)', centerLabel: 'ROLES', valField: 'value', severity: 'info', desc: 'Топ профессий на английском языке.', showDesc: false },
      { key: 'unused_persons', icon: 'trash', color: 'var(--danger)', label: 'Балласт', centerLabel: 'ПЕРСОН', valField: 'value', severity: 'critical', desc: 'Люди, не привязанные ни к одному шоу.', showDesc: false }
    ]
  }
])

const getMetricData = (key) => {
  return allMetrics[key]?.[activePeriod.value]?.data?.filter(i => i[getMetricField(key)] > 0) || []
}

const getMetricTimestamp = (key) => {
  return allMetrics[key]?.[activePeriod.value]?.timestamp || null
}

const hasData = (key) => {
  const ts = getMetricTimestamp(key)
  const d = getMetricData(key)
  return ts && d.length > 0
}

const getMetricField = (key) => {
  for (const g of metricGroups.value) {
    const m = g.metrics.find(x => x.key === key)
    if (m) return m.valField
  }
  return 'value'
}

const getMetricTotal = (key) => {
  const field = getMetricField(key)
  const data = getMetricData(key)
  if (key === 'persons_avatar_stats') {
    return data
      .filter(item => item.name === 'Есть фото (TMDB)' || item.name === 'Есть фото (KP)')
      .reduce((acc, item) => acc + item[field], 0)
  }
  return data.reduce((acc, item) => acc + item[field], 0)
}

const formatPercentage = (metricKey, itemName, val) => {
  const total = getMetricTotal(metricKey)
  return total > 0 ? `${Math.round((val / total) * 100)}%` : '0%'
}

const getPercent = (val, total) => {
  return total > 0 ? Math.round((val / total) * 100) : 0
}

const getPaletteColor = (severity, index) => {
  const pal = PALETTES[severity] || PALETTES.info
  return pal[index % pal.length][0]
}

const getChartData = (metric) => {
  const rawData = getMetricData(metric.key)
  const bgColors = rawData.map((_, i) => getPaletteColor(metric.severity, i))
  
  return {
    labels: rawData.map(i => i.name || i.type),
    datasets: [{
      data: rawData.map(i => i[metric.valField]),
      backgroundColor: bgColors,
      borderWidth: 0,
      hoverOffset: 15,
      borderRadius: 6,
      spacing: rawData.length === 1 ? 0 : 3
    }]
  }
}

const getChartOptions = (metric) => {
  return {
    cutout: '50%',
    layout: { padding: 15 },
    animation: {
      animateRotate: false,
      duration: 1200,
      easing: 'easeOutQuart'
    },
    onHover: (evt, elements) => {
      if (evt.native?.target) evt.native.target.style.cursor = elements.length ? 'pointer' : 'default'
    },
    onClick: (evt, elements) => {
      if (elements.length) {
        const index = elements[0].index
        const rawData = getMetricData(metric.key)
        const label = rawData[index].name || rawData[index].type
        openDetails(metric.key, label)
      }
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(22, 27, 34, 0.95)',
        titleColor: '#f0f6fc',
        bodyColor: '#8b949e',
        borderColor: '#2d333b',
        borderWidth: 1,
        cornerRadius: 10,
        padding: 12,
        callbacks: {
          label: (context) => {
            const val = context.parsed
            const total = getMetricTotal(metric.key)
            const pct = total > 0 ? Math.round((val / total) * 100) : 0
            return ` ${val.toLocaleString('ru-RU')} шт. (${pct}%)`
          }
        }
      },
      datalabels: {
        color: '#fff',
        font: { weight: '800', size: 10 },
        formatter: (value, context) => {
          const total = getMetricTotal(metric.key)
          const pct = total > 0 ? Math.round((value / total) * 100) : 0
          return pct > 5 ? pct + '%' : ''
        },
        display: 'auto'
      }
    }
  }
}

const getCenterPlugin = (metric) => ({
  id: 'centerText_' + metric.key,
  afterDraw: (chart) => {
    const { ctx, chartArea: { top, height, left, width } } = chart
    ctx.save()
    
    const total = getMetricTotal(metric.key)
    const centerX = left + width / 2
    const centerY = top + height / 2
    const textStr = total.toLocaleString('ru-RU')
    
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    
    ctx.font = '900 30px system-ui'
    
    let numColor = '#e5e7eb'
    if (total > 0) {
      if (metric.severity === 'critical') numColor = '#ff4b4b'
      else if (metric.severity === 'warning') numColor = '#f1c40f'
      else numColor = '#60a5fa'
    }
    
    ctx.fillStyle = numColor
    ctx.fillText(textStr, centerX, centerY - 8)
    
    ctx.font = 'bold 10px system-ui'
    ctx.fillStyle = '#6e7681'
    ctx.letterSpacing = '1px'
    ctx.fillText(metric.centerLabel, centerX, centerY + 22)
    
    ctx.restore()
  }
})

// Модальное окно детализации
const isModalOpen = ref(false)
const isModalLoading = ref(false)
const modalTitle = ref('')
const modalItems = ref([])
const modalLimit = ref(50)
const modalDataContext = ref({})
const currentTargetTask = ref('details')
const isBatchQueuing = ref(false)

const mergeSelections = ref({})

const visibleModalItems = computed(() => modalItems.value.slice(0, modalLimit.value))
const pendingQueueIds = computed(() => modalItems.value.filter(i => !i.in_queue).map(i => i.id))

const sentinelRef = ref(null)
let observer = null

const setupObserver = () => {
  if (observer) observer.disconnect()
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && modalLimit.value < modalItems.value.length) {
      modalLimit.value += 50
    }
  }, { root: document.querySelector('.modal-body-list'), rootMargin: '600px' })
  
  if (sentinelRef.value) {
    observer.observe(sentinelRef.value)
  }
}

watch(visibleModalItems, () => {
  nextTick(setupObserver)
})

const getMetricName = (key) => {
  for (const g of metricGroups.value) {
    const m = g.metrics.find(x => x.key === key)
    if (m) return m.label
  }
  return 'Детализация'
}

const openDetails = async (key, typeLabel) => {
  modalTitle.value = `${getMetricName(key)}: ${typeLabel}`
  isModalOpen.value = true
  isModalLoading.value = true
  modalItems.value = []
  modalLimit.value = 50
  mergeSelections.value = {}

  try {
    // Добавляем credentials: 'same-origin' для передачи сессионных куки админа
    const resp = await fetch(`/api/metrics/details/${key}/?type=${encodeURIComponent(typeLabel)}`, {
        credentials: 'same-origin'
    })
    
    if (resp.status === 403) {
        modalDataContext.value = { is_authenticated: false }
        isModalLoading.value = false
        return
    }

    const data = await resp.json()
    modalDataContext.value = { ...data, is_authenticated: true }
    currentTargetTask.value = data.target_task || 'details'

    if (data.items && data.items.length) {
      modalItems.value = data.items
      data.items.forEach(item => {
        if (item.is_duplicate_group && item.persons && item.persons.length > 0) {
          mergeSelections.value[item.persons[0].id] = item.persons[0].id
        }
      })
    }
  } catch (e) {
    console.error(e)
  } finally {
    isModalLoading.value = false
    nextTick(setupObserver)
  }
}

const closeDetails = () => {
  isModalOpen.value = false
  if (observer) observer.disconnect()
}

const addToQueue = async (item) => {
  item.in_queue = true
  try {
    await fetch('/api/metrics/queue_update/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: [item.id], target: currentTargetTask.value })
    })
  } catch (e) {
    item.in_queue = false
    alert('Ошибка добавления в очередь: ' + e.message)
  }
}

const addAllToQueue = async () => {
  const ids = pendingQueueIds.value
  if (ids.length === 0) return

  isBatchQueuing.value = true
  try {
    await fetch('/api/metrics/queue_update/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: ids, target: currentTargetTask.value })
    })
    modalItems.value.forEach(i => i.in_queue = true)
  } catch (e) {
    alert('Ошибка добавления в очередь: ' + e.message)
  } finally {
    isBatchQueuing.value = false
  }
}

const executeMerge = async (groupId, personsArray) => {
  const masterId = mergeSelections.value[groupId]
  if (!masterId) return

  const aliasIds = personsArray.map(p => p.id).filter(id => id !== masterId)
  if (aliasIds.length === 0) {
    alert('Необходимо выбрать хотя бы один алиас для объединения.')
    return
  }

  const groupItem = modalItems.value.find(i => i.persons && i.persons[0].id === groupId)

  try {
    const response = await fetch('/api/metrics/merge_persons/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ master_id: masterId, alias_ids: aliasIds })
    })

    if (!response.ok) throw new Error('Ошибка API')
    if (groupItem) {
      groupItem.persons = null
    }
  } catch (e) {
    alert('Ошибка: ' + e.message)
  }
}

onUnmounted(() => {
  if (observer) observer.disconnect()
})
</script>

<style scoped>
.webapp-container { margin: 0 auto; padding-top: 0px; }

.layer-header { 
    position: sticky; 
    top: 0; 
    z-index: 100; 
    background: rgba(20, 24, 31, 0.9); 
    backdrop-filter: blur(15px); 
    border-bottom: 1px solid var(--border); 
    display: flex; 
    flex-direction: column; 
    align-items: center; 
}

.header-container { 
    max-width: 98%; 
    width: 100%; 
    margin: 0 auto; 
    display: flex; 
    align-items: center; 
    justify-content: space-between; 
    padding: 12px 16px 8px; 
}

.header-title { 
    font-size: 20px; 
    font-weight: 800; 
    color: var(--text-primary); 
    letter-spacing: -0.5px; 
    white-space: nowrap; 
    flex: 1 1 0;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
}

.wa-nav-links { 
    display: flex; 
    justify-content: center; 
    gap: 12px; 
    flex-wrap: wrap; 
    flex: 0 0 auto;
}

.header-container > div:last-child {
    flex: 1 1 0;
    min-width: 0;
}
.wa-nav-btn {
    background: var(--bg-input);
    color: var(--text-primary);
    border: 1px solid var(--border);
    padding: 8px 16px;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    text-decoration: none;
    transition: transform 0.2s, background 0.2s;
    min-width: 130px;
    text-align: center;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}
.wa-nav-btn:hover { background: var(--border); transform: translateY(-2px); }
.wa-nav-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }

.period-switcher-row { width: 100%; display: flex; flex-direction: column; align-items: center; gap: 6px; }
.period-tabs-small { display: flex; gap: 12px; justify-content: center; }
.period-tabs-small .tab {
    align-items: center;
    justify-content: center;
    font-size: 12px;
    padding: 6px 12px;
    border-radius: 8px;
    min-width: 130px;
    text-align: center;
    border: 1px solid var(--border);
    background: var(--bg-card);
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--transition-bounce);
}
.period-tabs-small .tab.on { background: var(--accent-dim); color: var(--accent); border-color: var(--accent); transform: scale(1.05); }

#data-timestamp { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 9px; color: var(--text-muted); font-weight: 500; letter-spacing: -0.2px; opacity: 0.6; text-transform: uppercase; text-align: center; margin-bottom: 4px; }

.status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; padding: 10px 16px 24px; }
.status-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; display: flex; align-items: center; gap: 12px; box-shadow: var(--shadow-sm); transition: transform var(--transition-smooth); }
.status-card:hover { transform: translateY(-2px); border-color: var(--text-muted); }
.status-icon-wrap { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.status-info { display: flex; flex-direction: column; min-width: 0; }
.status-label { font-size: 11px; color: var(--text-muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.status-val { font-size: 14px; color: var(--text-primary); font-weight: 800; font-variant-numeric: tabular-nums; }

.metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr)); gap: 10px; padding: 10px 16px; }
.metrics-grid .card {
    display: flex;
    flex-direction: column;
}

.metric-desc { max-height: 0; opacity: 0; overflow: hidden; margin: 0; padding: 0 12px; transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1); font-size: 13px; color: var(--text-muted); line-height: 1.5; background: var(--bg-main); border-radius: 10px; border-left: 3px solid var(--accent); pointer-events: none; }
.metric-desc.visible { max-height: 300px; opacity: 1; margin: 10px 0 20px; padding: 12px; pointer-events: auto; }
.label-clickable { cursor: pointer; user-select: none; }

.admin-models-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
.admin-li { padding: 10px 16px; border-bottom: 1px dashed var(--border); display: flex; justify-content: space-between; align-items: center; }
.admin-li:last-child { border: none; }

.modal-overlay { align-items: center !important; z-index: 2000; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(5px); display: flex; justify-content: center; opacity: 0; pointer-events: none; transition: opacity 0.3s ease; }
.modal-overlay.show { opacity: 1; pointer-events: auto; }
.modal-content {
    background: var(--bg-card);
    width: 90vw;
    max-width: 550px;
    max-height: 92vh;
    display: flex;
    flex-direction: column;
    border-radius: 24px !important;
    transform: scale(0.95);
    opacity: 0;
    transition: all 0.3s ease;
    margin: 0 auto;
    border: 1px solid var(--border);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
}
.modal-content.modal-wide {
    width: 90vw;
    max-width: 95vw;
}
.modal-overlay.show .modal-content { transform: scale(1); opacity: 1; }
.modal-header { flex-shrink: 0; display: flex; justify-content: space-between; align-items: center; padding: 20px; border-bottom: 1px solid var(--border); }
.modal-title { font-size: 20px; font-weight: 800; color: var(--text-primary); }
.modal-close { background: var(--bg-input); border: none; color: var(--text-muted); width: 32px; height: 32px; border-radius: 50%; font-size: 20px; cursor: pointer; display: flex; justify-content: center; align-items: center; transition: background 0.2s; }
.modal-close:hover { background: var(--border); color: var(--text-primary); }
.modal-body-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 380px), 450px)); grid-auto-rows: min-content; align-content: start; justify-content: center; gap: 16px; margin-top: 15px; overflow-y: auto; padding: 5px 10px 30px 5px; flex-grow: 1; min-height: 0; }

.modal-item { display: flex; flex-direction: row; align-items: stretch; background: var(--bg-input); border: 1px solid var(--border); border-radius: 12px; transition: all 0.2s; overflow: hidden; width: 100%; max-width: 450px; flex-shrink: 0; transform: translateZ(0); }
.modal-item-poster { width: 80px; height: auto; object-fit: cover; background: var(--bg-main); flex-shrink: 0; border-right: 1px solid var(--border); }
.modal-item-content { display: flex; flex-direction: column; justify-content: space-between; flex-grow: 1; min-width: 0; }
.modal-item-info { display: flex; flex-direction: column; justify-content: center; min-width: 0; flex-grow: 1; padding: 12px 14px; }
.modal-item-title { font-size: 14px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.3; }
.modal-item-orig { font-size: 11px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.modal-item-actions { display: flex; border-top: 1px solid var(--border); background: rgba(0,0,0,0.15); flex-wrap: nowrap; }

.queue-btn { flex-grow: 1; flex-shrink: 0; min-width: 140px; padding: 12px 10px; background: transparent; border: none; color: var(--text-primary); cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 14px; font-weight: 700; transition: background 0.2s; border-right: 1px solid var(--border); white-space: nowrap; }
.queue-btn:hover:not(:disabled) { background: rgba(46, 204, 113, 0.1); color: var(--accent); }
.queue-btn:disabled { color: var(--accent); cursor: default; }

.admin-link-btn { flex-shrink: 0; padding: 12px 12px; background: transparent; border: none; color: var(--text-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: color 0.2s, background 0.2s; text-decoration: none; font-size: 14px; font-weight: 700; white-space: nowrap; }
.admin-link-btn:hover { background: rgba(96, 165, 250, 0.1); color: var(--info); }

.modal-footer { padding: 15px 24px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; background: var(--bg-card); border-radius: 0 0 24px 24px; margin: 0; flex-shrink: 0; }
.add-all-btn { background: var(--accent); color: #fff; border: none; padding: 12px 24px; border-radius: 8px; font-size: 15px; font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: transform 0.2s; }
.add-all-btn:hover:not(:disabled) { transform: scale(0.98); }
.add-all-btn:disabled { opacity: 0.5; cursor: not-allowed; }

@keyframes pulseGlowRed {
    0% { box-shadow: 0 4px 12px rgba(231, 76, 60, 0.05); border-color: var(--border); }
    50% { box-shadow: 0 4px 24px rgba(231, 76, 60, 0.25); border-color: rgba(231, 76, 60, 0.5); }
    100% { box-shadow: 0 4px 12px rgba(231, 76, 60, 0.05); border-color: var(--border); }
}
.anim-item.critical-glow {
    animation: slideInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both, pulseGlowRed 10s infinite;
}

.merge-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 16px;
    margin-bottom: 16px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    transition: all 0.3s ease;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}
.merge-card:not(:has(.merge-list)) { opacity: 0.3; filter: grayscale(1); pointer-events: none; transform: scale(0.98); }

.merge-header { padding: 12px 16px; background: rgba(0, 0, 0, 0.25); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
.merge-content { display: flex; padding: 14px; gap: 16px; align-items: flex-start; }
.merge-poster-area { flex-shrink: 0; width: 100px; }
.merge-poster-area img { width: 100px; height: 120px; border-radius: 12px; object-fit: cover; box-shadow: var(--shadow-sm); border: 1px solid var(--border); }
.merge-list { flex: 1; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.merge-row { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 12px; cursor: pointer; transition: all 0.2s ease; border: 1px solid var(--border); background: rgba(0, 0, 0, 0.15); user-select: none; }
.merge-row:hover { background: var(--bg-input); border-color: var(--text-muted); }
.merge-row.is-master { background: var(--accent-dim); border-color: var(--accent); }
.merge-row input[type="radio"] { width: 18px; height: 18px; accent-color: var(--accent); margin: 0; cursor: pointer; flex-shrink: 0; }

.person-details-box {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex: 1;
    min-width: 0;
}
.person-meta-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}
.edit-link { opacity: 1; color: var(--info); font-size: 10px; }
.person-name { font-size: 14px; font-weight: 700; color: var(--text-primary); word-break: break-word; }
.person-id-badge { font-size: 10px; font-weight: 800; font-family: monospace; background: var(--bg-input); border: 1px solid var(--border); padding: 1px 5px; border-radius: 4px; color: var(--text-muted); }
.person-en-name { font-size: 12px; color: var(--text-secondary); font-style: italic; opacity: 0.85; text-align: left; word-break: break-word; }

.edit-link-btn-small {
    font-size: 11px;
    font-weight: 800;
    color: var(--info);
    background: var(--info-dim);
    padding: 4px 12px;
    border-radius: 8px;
    text-decoration: none;
    transition: all 0.2s ease;
    border: 1px solid transparent;
    white-space: nowrap;
    flex-shrink: 0;
}
.edit-link-btn-small:hover {
    background: var(--info);
    color: #fff;
    transform: translateY(-1px);
}
.btn-merge-action { background: var(--accent); color: white; border: none; padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 800; cursor: pointer; transition: transform 0.2s; }
.btn-merge-action:active { transform: scale(0.95); }

.legend-grid { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 16px; justify-content: center; }
.legend-item { display: flex; align-items: center; gap: 6px; padding: 6px 10px; background: var(--bg-input); border: 1px solid var(--border); border-radius: 8px; cursor: pointer; transition: all 0.2s; flex: 1 1 auto; box-sizing: border-box; }
.legend-item:hover { border-color: var(--accent); background: var(--bg-main); }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.legend-name { font-size: clamp(11px, 1.5vw, 13px); font-weight: 700; color: var(--text-primary); white-space: nowrap; flex: 1; line-height: 1.2; text-align: left; }
.legend-val { font-size: clamp(11px, 1.5vw, 12px); color: var(--text-muted); font-weight: 600; white-space: nowrap; flex-shrink: 0; }

.empty-overlay { display:flex; flex-direction:column; align-items:center; justify-content:center; height:180px; text-align:center; }
.empty-title { color:var(--text-muted); font-weight:800; font-size:16px; text-transform:uppercase; letter-spacing:0.5px; }
.empty-sub { font-size:12px; color:var(--text-muted); margin-top:4px; opacity:0.7; }

.live-indicator-badge {
  margin-left: 6px;
  color: var(--accent);
  font-size: 11px;
  font-weight: 800;
  background: var(--accent-dim);
  padding: 2px 8px;
  border-radius: 6px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.live-dot {
  width: 6px;
  height: 6px;
  background: var(--accent);
  border-radius: 50%;
  display: inline-block;
  animation: pulse-live 2s infinite;
}

@keyframes pulse-live {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(46, 204, 113, 0.7); }
  70% { transform: scale(1); box-shadow: 0 0 0 4px rgba(46, 204, 113, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(46, 204, 113, 0); }
}
</style>