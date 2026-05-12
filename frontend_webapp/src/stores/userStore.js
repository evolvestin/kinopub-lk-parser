import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  const initData = ref('')
  const userData = ref(null)

  const firstName = computed(() => userData.value?.first_name || 'Guest')
  const telegramId = computed(() => userData.value?.id || null)

  function setInitData(data) {
    initData.value = data
  }

  function setUserData(data) {
    userData.value = data
  }

  return {
    initData,
    userData,
    firstName,
    telegramId,
    setInitData,
    setUserData
  }
})