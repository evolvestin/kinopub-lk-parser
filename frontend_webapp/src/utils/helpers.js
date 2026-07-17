import { logger } from './logger'

const brokenImages = new Set();

export function isImageBroken(url) {
  return url ? brokenImages.has(url) : false;
}

export function markImageAsBroken(url) {
  if (url) brokenImages.add(url);
}

export function plural(n, forms) {
  const num = Math.abs(parseInt(n)) || 0;
  const n10 = num % 10;
  const n100 = num % 100;
  
  if (n100 >= 11 && n100 <= 14) return forms[2];
  if (n10 === 1) return forms[0];
  if (n10 >= 2 && n10 <= 4) return forms[1];
  return forms[2];
}

export function getUserColor(id) {
  const colors = ['#3498db', '#9b59b6', '#f1c40f', '#e67e22', '#e74c3c', '#1abc9c', '#34495e', '#2ecc71'];
  if (!id || id === 0) return 'var(--bg-input)';
  return colors[Math.abs(id - 1) % colors.length];
}

export function getRatingClass(val) {
  if (!val) return ''
  if (val >= 8) return 'rating-high'
  if (val >= 5) return 'rating-mid'
  return 'rating-low'
}

const preloadPool = new Set();
const preloadedUrls = new Set();
const preloadingPromises = new Map();

export function preloadImage(url, priority = 'auto') {
  if (!url || typeof url !== 'string' || brokenImages.has(url)) return Promise.resolve(false);
  if (preloadedUrls.has(url)) return Promise.resolve(true);
  if (preloadingPromises.has(url)) return preloadingPromises.get(url);
  
  const startTime = performance.now();
  logger.info(`Asset preload queued: ${url}`);

  const promise = new Promise((resolve) => {
    const img = new Image();
    
    img.onload = () => {
      preloadPool.delete(img);
      preloadingPromises.delete(url);
      if (img.naturalWidth === 208 && img.naturalHeight === 304) {
        brokenImages.add(url);
        logger.warn(`Asset failed validation (broken geometry 208x304): ${url} (took ${(performance.now() - startTime).toFixed(1)}ms)`);
        resolve(false);
      } else {
        preloadedUrls.add(url);
        logger.info(`Asset preloaded successfully: ${url} (took ${(performance.now() - startTime).toFixed(1)}ms)`);
        resolve(true);
      }
    };
    
    img.onerror = () => {
      preloadPool.delete(img);
      preloadingPromises.delete(url);
      brokenImages.add(url);
      logger.error(`Asset preload failed: ${url} (took ${(performance.now() - startTime).toFixed(1)}ms)`);
      resolve(false);
    };

    if (priority === 'low') {
      img.decoding = 'async';
    }

    preloadPool.add(img);
    img.src = url;
  });

  preloadingPromises.set(url, promise);
  return promise;
}

export function validateImageGeom(event, onPlaceholderNeeded) {
  const img = event.target;
  if (img.naturalWidth === 208 && img.naturalHeight === 304) {
    onPlaceholderNeeded();
  }
}

export function handleImageFallback(primaryUrl, fallbackUrl, stateRef) {
  if (fallbackUrl && stateRef.value === primaryUrl) {
    stateRef.value = fallbackUrl;
  } else {
    stateRef.value = null;
  }
}
