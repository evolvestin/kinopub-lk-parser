<template>
  <div class="view active-view public-stats-preview">
    <div class="header">
      <div class="header-left"><div class="avatar">Д</div><div><div class="header-name glow-text">Демо-профиль</div><div class="header-sub">Пример статистики</div></div></div>
      <div class="top-controls"><button class="theme-btn" aria-label="Приватность статистики" @click="ui.openModal('privacy')">♧</button><button class="share-btn" aria-label="Поделиться статистикой" @click="ui.openModal('share')">↗</button></div>
    </div>
    <div class="years">
      <button v-for="year in years" :key="year" class="yr clickable" :class="{on:activeYear===year}" @click="activeYear=year">{{ year }}</button>
    </div>
    <div class="label"><div class="icon" v-html="icons.dash"></div> Обзор</div>
    <div class="grid">
      <StatCard :icon="icons.time" :value="activeYear==='Всё время'?'126 ч':activeYear==='2025'?'38 ч':'52 ч'" label="Время просмотра" :sub-value="activeYear==='Всё время'?'64':activeYear==='2025'?'24':'31'" sub-label="просмотра" />
      <StatCard :icon="icons.film" :value="activeYear==='Всё время'?'82':activeYear==='2025'?'24':'36'" label="Фильмы" />
      <StatCard :icon="icons.tv" :value="activeYear==='Всё время'?'18':activeYear==='2025'?'7':'9'" label="Сериалы" />
      <StatCard :icon="icons.star" :value="activeYear==='2024'?'8.1':'8.4'" label="Средняя оценка" />
    </div>
    <div class="card public-stats-card">
      <div class="label">Просмотры по месяцам <span class="sample-badge">ПРИМЕР</span></div>
      <div class="public-bars" aria-label="Пример графика просмотров">
        <div v-for="(bar,index) in bars" :key="index" class="public-bar-column"><span :style="{height:bar+'%'}"></span><small>{{ months[index] }}</small></div>
      </div>
    </div>
    <div class="card public-stats-card"><div class="label">Любимые жанры</div><div class="public-genre-list"><div v-for="item in genres" :key="item.name"><span>{{ item.name }}</span><b>{{ item.time }}</b><i><em :style="{width:item.percent+'%'}"></em></i></div></div></div>
    <ShareModal v-if="ui.modals.share.isOpen" :demo="true" />
    <PrivacyModal v-if="ui.modals.privacy.isOpen" :demo="true" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import StatCard from '../components/stats/StatCard.vue'
import ShareModal from '../components/modals/ShareModal.vue'
import PrivacyModal from '../components/modals/PrivacyModal.vue'
import { useUIStore } from '../stores/uiStore'
import { icons } from '../utils/icons'

const years = ['Всё время', '2025', '2024']
const activeYear = ref('Всё время')
const ui = useUIStore()
const months = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек']
const bars = [34,52,28,72,43,85,58,38,67,48,94,61]
const genres = [
  {name:'Драма',time:'42 ч',percent:78},
  {name:'Фантастика',time:'31 ч',percent:58},
  {name:'Комедия',time:'18 ч',percent:34}
]
</script>

<style scoped>
.public-stats-preview{padding-bottom:80px}.public-stats-preview .header{padding:10px 16px 16px}.public-stats-preview .header-left{display:flex;align-items:center;gap:12px}.public-stats-preview .header-name{font-size:17px;font-weight:800}.public-stats-preview .header-sub{font-size:12px;color:var(--text-muted)}.public-stats-preview .avatar{width:42px;height:42px;display:grid;place-items:center;border-radius:50%;background:var(--accent-dim);color:var(--accent);font-weight:900}.public-stats-preview .years{display:flex;gap:8px;overflow:auto;padding:8px 16px 18px}.public-stats-preview .yr{padding:8px 12px;border:1px solid var(--border);border-radius:12px;background:var(--bg-card);color:var(--text-secondary);font:inherit;font-size:12px;font-weight:800}.public-stats-preview .yr.on{border-color:var(--accent);background:var(--accent-dim);color:var(--accent)}.public-stats-preview>.label{padding:4px 20px 12px}.public-stats-preview .grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:0 16px}.public-stats-preview .card{margin:14px 16px;padding:18px;border:1px solid var(--border);border-radius:18px;background:var(--bg-card)}.public-stats-preview .label{display:flex;justify-content:space-between;align-items:center;color:var(--text-primary);font-weight:800}.sample-badge{font-size:9px;letter-spacing:.1em;color:var(--accent)}.public-bars{height:130px;display:flex;align-items:end;gap:7px;margin-top:20px}.public-bar-column{height:100%;flex:1;display:flex;flex-direction:column;align-items:center;justify-content:end;gap:7px}.public-bar-column span{width:100%;max-width:28px;min-height:5px;border-radius:7px 7px 3px 3px;background:linear-gradient(180deg,var(--accent),#168c57);animation:bar-rise .55s cubic-bezier(.2,.75,.25,1) both;transform-origin:bottom}.public-bar-column small{font-size:9px;color:var(--text-muted)}.public-genre-list{display:grid;gap:14px;margin-top:18px}.public-genre-list>div{display:grid;grid-template-columns:1fr auto;gap:7px;font-size:12px;color:var(--text-secondary)}.public-genre-list b{color:var(--text-primary)}.public-genre-list i{grid-column:1/-1;height:5px;border-radius:9px;background:var(--bg-input);overflow:hidden}.public-genre-list em{display:block;height:100%;border-radius:inherit;background:var(--accent)}@keyframes bar-rise{from{transform:scaleY(.05);opacity:.4}to{transform:scaleY(1);opacity:1}}
</style>
