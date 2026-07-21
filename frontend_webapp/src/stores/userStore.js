import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

const initialRole = localStorage.getItem('user_role') || window.USER_ROLE || 'guest'
window.USER_ROLE = initialRole

export const useUserStore = defineStore('user', () => {
  const userData = ref(null)
  const userRole = ref(initialRole)
  const isAnonymous = ref(true)
  const privacyChoiceMade = ref(false)

  const isGuest = computed(() => userRole.value === 'guest')
  const firstName = computed(() => userData.value?.first_name || 'Guest')

  function setUser(data) {
    userData.value = data
    if (data?.role) {
      userRole.value = data.role
    }
  }

  watch(userRole, (newRole) => {
    window.USER_ROLE = newRole
    if (newRole) {
      localStorage.setItem('user_role', newRole)
    } else {
      localStorage.removeItem('user_role')
    }
  }, { immediate: true })

  return {
    userData,
    userRole,
    isGuest,
    firstName,
    isAnonymous,
    privacyChoiceMade,
    setUser
  }
})