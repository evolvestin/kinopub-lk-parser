import { useTelegram } from './useTelegram'

export function useApi() {
  const { initData } = useTelegram()

  async function request(endpoint, method = 'GET', payload = null) {
    const options = {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      }
    }

    if (payload) {
      options.body = JSON.stringify({
        init_data: initData,
        ...payload
      })
    } else if (method === 'GET' && initData) {
      const separator = endpoint.includes('?') ? '&' : '?'
      endpoint += `${separator}init_data=${encodeURIComponent(initData)}`
    }

    const response = await fetch(`/api/webapp/${endpoint}`, options)
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.error || `Server Error: ${response.status}`)
    }

    return await response.json()
  }

  return {
    get: (endpoint) => request(endpoint, 'GET'),
    post: (endpoint, payload) => request(endpoint, 'POST', payload)
  }
}