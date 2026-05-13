<template>
  <div class="layer-content" v-if="show">
    <div class="layer-header">
       <button class="tab clickable" @click="uiStore.popLayer">
         <span v-html="icons.chevron_left"></span> Назад
       </button>
       <div class="layer-title-main">{{ show.title }}</div>
    </div>

    <div class="hero-container">
      <div class="hero-bg" :style="{ backgroundImage: `url(${show.poster_large})` }"></div>
      <div class="hero-gradient"></div>
      <img :src="show.poster_large" class="hero-poster">
      
      <div class="hero-controls" style="position: relative; z-index: 3; height: 85%; max-width: 65%; display: flex; align-items: flex-end;">
        <button class="wishlist-add-btn detail-wishlist-btn anim-item" @click="toggleWishlist">
          <span v-html="icons.bookmark_plus"></span>
        </button>
        <button class="detail-add-view-btn anim-item" style="top:40px !important" @click="openAddView">
          <span v-html="icons.eye"></span>
        </button>
        <button class="detail-add-view-btn detail-rate-btn anim-item" style="top:92px !important" @click="openRating">
          <span v-html="icons.star"></span>
        </button>
      </div>
    </div>

    <div class="show-info">
      <div class="show-title">{{ show.title }}</div>
      <div class="show-orig" v-if="show.original_title !== show.title">{{ show.original_title }}</div>
      
      <div class="show-meta-tags">
        <div v-for="c in show.countries" :key="c.id" class="sm-tag">{{ c.emoji }} {{ c.name }}</div>
      </div>

      <div class="show-meta-tags">
        <div class="sm-tag">{{ show.year || '?' }}</div>
        <div class="sm-tag" style="color:var(--info)">{{ show.type }}</div>
        <div class="sm-tag" v-if="show.status">{{ show.status }}</div>
      </div>

      <div class="show-meta-tags">
        <div v-if="show.kinopoisk_rating" class="sm-tag" style="background:rgba(241, 90, 36, 0.15); color:#f15a24; border:none">KP {{ show.kinopoisk_rating }}</div>
        <div v-if="show.imdb_rating" class="sm-tag" style="background:rgba(245, 197, 24, 0.15); color:#f5c518; border:none">IMDb {{ show.imdb_rating }}</div>
        <div v-if="show.internal_rating" class="sm-tag" style="background:var(--accent-dim); color:var(--accent); border:none">★ {{ show.internal_rating.toFixed(1) }}</div>
      </div>
    </div>

    <div class="plot-box" v-if="show.plot">{{ show.plot }}</div>
    
    <template v-for="group in show.crew" :key="group.profession">
      <div class="label">{{ group.profession }}</div>
      <div class="h-scroll-container">
         <PersonPill v-for="person in group.persons" :key="person.id" :person="person" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { useUIStore } from '../../stores/uiStore'
import { icons } from '../../utils/icons'
import PersonPill from '../shared/PersonPill.vue'

const props = defineProps(['showId'])
const api = useApi()
const uiStore = useUIStore()
const show = ref(null)

onMounted(async () => {
  try {
    const data = await api.get(`show/${props.showId}/`)
    show.value = data
  } catch (e) {
    uiStore.showToast('Ошибка загрузки')
    uiStore.popLayer()
  }
})

const openRating = () => uiStore.showToast('Будет в след. итерации')
const openAddView = () => uiStore.showToast('Будет в след. итерации')
const toggleWishlist = () => uiStore.showToast('Добавлено')
</script>