export const logger = {
  info(message, ...args) {
    if (window.IS_DEBUG || window.USER_ROLE === 'admin') {
      console.info(`[AppInfo] [${new Date().toISOString()}]`, message, ...args)
    }
  },
  warn(message, ...args) {
    if (window.IS_DEBUG || window.USER_ROLE === 'admin') {
      console.warn(`[AppWarn] [${new Date().toISOString()}]`, message, ...args)
    }
  },
  error(message, ...args) {
    if (window.IS_DEBUG || window.USER_ROLE === 'admin') {
      console.error(`[AppError] [${new Date().toISOString()}]`, message, ...args)
    }
  },
  time(label) {
    if (window.IS_DEBUG || window.USER_ROLE === 'admin') {
      console.time(`[AppTime] ${label}`)
    }
  },
  timeEnd(label) {
    if (window.IS_DEBUG || window.USER_ROLE === 'admin') {
      console.timeEnd(`[AppTime] ${label}`)
    }
  }
}