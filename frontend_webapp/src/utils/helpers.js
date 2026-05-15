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

const preloadPool = new Set();

export function preloadImage(url, priority = 'auto') {
  if (!url || typeof url !== 'string') return Promise.resolve(false);
  
  return new Promise((resolve) => {
    const img = new Image();
    
    // Согласно архитектурному правилу: всегда проверяем размеры для Кинопоиска
    img.onload = () => {
      preloadPool.delete(img);
      // Детекция заглушки Кинопоиска (no-poster.gif) 208x304
      if (img.naturalWidth === 208 && img.naturalHeight === 304) {
        resolve(false);
      } else {
        resolve(true);
      }
    };
    
    img.onerror = () => {
      preloadPool.delete(img);
      resolve(false);
    };

    if (priority === 'low') {
      img.decoding = 'async';
    }

    preloadPool.add(img);
    img.src = url;
  });
}

export async function resolvePersonImage(primary, secondary) {
  // Если URL пуст, сразу возвращаем null
  if (!primary && !secondary) return null;

  if (primary) {
    const ok = await preloadImage(primary);
    if (ok) return primary;
  }
  
  if (secondary) {
    const ok = await preloadImage(secondary);
    if (ok) return secondary;
  }
  
  return null;
}

export function validateImageGeom(event, onPlaceholderNeeded) {
  const img = event.target;
  // Детекция заглушки Кинопоиска (no-poster.gif)
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