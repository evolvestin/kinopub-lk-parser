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
      
      <button class="detail-add-view-btn" @click="uiStore.openRatingModal(showId, show.title, show.personal_rating, show.type)">
        <span v-html="icons.star"></span>
      </button>
    </div>

    <div class="show-info">
      <div class="show-meta-tags">
        <div class="sm-tag">{{ show.year }}</div>
        <div class="sm-tag" style="color:var(--info)">{{ show.type }}</div>
      </div>
      <div class="plot-box">{{ show.plot }}</div>
    </div>
    
    <div class="label">В ролях</div>
    <div class="h-scroll-container">
       <PersonPill v-for="person in cast" :key="person.id" :person="person" />
    </div>
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
const cast = ref([])

onMounted(async () => {
  const data = await api.get(`show/${props.showId}/`)
  show.value = data
  cast.value = data.crew?.[0]?.persons || []
})
</script>