import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  const userData = ref(null)
  const userRole = ref('guest')

  const isGuest = computed(() => userRole.value === 'guest')
  const firstName = computed(() => userData.value?.first_name || 'Guest')

  function setUser(data) {
    userData.value = data
    if (data?.role) userRole.value = data.role
  }

  return {
    userData,
    userRole,
    isGuest,
    firstName,
    setUser
  }
})