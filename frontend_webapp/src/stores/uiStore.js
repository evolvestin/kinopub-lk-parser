import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUIStore = defineStore('ui', () => {
  const isLoading = ref(true)
  const isAppReady = ref(false)
  const theme = ref('dark')
  
  const activeMainView = ref('search')
  const toast = ref({ text: '', visible: false })

  function setLoading(status) {
    isLoading.value = status
  }

  function setAppReady(status) {
    isAppReady.value = status
  }

  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  function showToast(text) {
    toast.value = { text, visible: true }
    setTimeout(() => {
      toast.value.visible = false
    }, 2500)
  }

  return {
    isLoading,
    isAppReady,
    theme,
    activeMainView,
    toast,
    setLoading,
    setAppReady,
    toggleTheme,
    showToast
  }
})