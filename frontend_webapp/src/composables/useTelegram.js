const getCookie = (name) => {
  try {
    const matches = document.cookie.match(new RegExp(
      "(?:^|; )" + name.replace(/([\.$?*|{}\(\)\[\]\\\/\+^])/g, '\\$1') + "=([^;]*)"
    ));
    return matches ? decodeURIComponent(matches[1]) : '';
  } catch (e) {
    return '';
  }
}

const setCookie = (name, value, days = 7) => {
  try {
    const d = new Date();
    d.setTime(d.getTime() + (days * 24 * 60 * 60 * 1000));
    document.cookie = `${name}=${encodeURIComponent(value)}; path=/; expires=${d.toUTCString()}; SameSite=Lax`;
  } catch (e) {}
}

const parseInitDataFromUrl = () => {
  const sources = [window.location.hash, window.location.search];
  for (const src of sources) {
    if (!src) continue;
    const cleanSrc = src.replace(/^[#?]/, '');
    const params = new URLSearchParams(cleanSrc);
    const data = params.get('tgWebAppData') || params.get('init_data');
    if (data) return data;
    if (params.has('hash') && (params.has('user') || params.has('query_id') || params.has('auth_date'))) {
      return cleanSrc;
    }
  }
  return '';
}

const earlyInitData = window.__telegram_init_data__ || parseInitDataFromUrl();
if (earlyInitData) {
  window.__telegram_init_data__ = earlyInitData;
  try { localStorage.setItem('tg_init_data', earlyInitData); } catch (e) {}
  try { sessionStorage.setItem('tg_init_data', earlyInitData); } catch (e) {}
  setCookie('tg_init_data', earlyInitData);
}

const getStoredInitData = () => {
  if (window.__telegram_init_data__ && window.__telegram_init_data__ !== 'undefined' && window.__telegram_init_data__ !== 'null') {
    return window.__telegram_init_data__;
  }
  let val = '';
  try {
    val = localStorage.getItem('tg_init_data');
    if (val && val !== 'undefined' && val !== 'null') return val;
  } catch (e) {}
  try {
    val = sessionStorage.getItem('tg_init_data');
    if (val && val !== 'undefined' && val !== 'null') return val;
  } catch (e) {}
  val = getCookie('tg_init_data');
  if (val && val !== 'undefined' && val !== 'null') return val;
  return '';
}

const storeInitData = (val) => {
  if (!val || val === 'undefined' || val === 'null') return;
  window.__telegram_init_data__ = val;
  try {
    localStorage.setItem('tg_init_data', val);
  } catch (e) {}
  try {
    sessionStorage.setItem('tg_init_data', val);
  } catch (e) {}
  setCookie('tg_init_data', val);
}

export function useTelegram() {
  const tg = window.Telegram?.WebApp
  
  let initData = window.__telegram_init_data__ || tg?.initData || ''
  
  if (initData && initData !== 'undefined' && initData !== 'null') {
    storeInitData(initData)
  } else {
    initData = getStoredInitData()
  }

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