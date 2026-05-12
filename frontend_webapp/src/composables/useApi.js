import { useTelegram } from './useTelegram'

export function useApi() {
  const { initData } = useTelegram()

  async function post(endpoint, payload = {}) {
    const response = await fetch(`/api/webapp/${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        init_data: initData,
        ...payload
      })
    })

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`)
    }

    return await response.json()
  }

  return {
    post
  }
}