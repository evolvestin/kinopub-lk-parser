export function useTelegram() {
  const tg = window.Telegram?.WebApp
  
  const initData = tg?.initData || ''
  
  const close = () => {
    tg?.close()
  }

  const showConfirm = (message, callback) => {
    if (tg?.showConfirm) {
      tg.showConfirm(message, callback)
    } else {
      callback(window.confirm(message))
    }
  }

  return {
    tg,
    initData,
    close,
    showConfirm
  }
}