import { useTelegram } from './useTelegram'
import { logger } from '../utils/logger'

export function useApi() {
  async function request(endpoint, method = 'GET', payload = null) {
    const { initData } = useTelegram()
    const startTime = performance.now()
    
    const options = {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      }
    }

    if (initData) {
      options.headers['Authorization'] = `Bearer ${initData}`
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

    logger.info(`API Request initiated: ${method} ${endpoint}`)

    try {
      const response = await fetch(`/api/webapp/${endpoint}`, options)
      const duration = (performance.now() - startTime).toFixed(1)
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        const errorMsg = errorData.error || `Server Error: ${response.status}`
        logger.error(`API Request failed: ${method} ${endpoint} - Error: ${errorMsg} (took ${duration}ms)`)
        throw new Error(errorMsg)
      }

      logger.info(`API Request succeeded: ${method} ${endpoint} - Status: ${response.status} (took ${duration}ms)`)
      return await response.json()
    } catch (e) {
      const duration = (performance.now() - startTime).toFixed(1)
      logger.error(`API Request encountered exception: ${method} ${endpoint} - Exception: ${e.message} (took ${duration}ms)`)
      throw e
    }
  }

  return {
    get: (endpoint) => request(endpoint, 'GET'),
    post: (endpoint, payload) => request(endpoint, 'POST', payload)
  }
}