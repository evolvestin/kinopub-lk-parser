document.querySelectorAll('.public-poster').forEach((img) => {
  const fallback = () => { const icon = document.createElement('span'); icon.className = 'poster-placeholder'; icon.setAttribute('aria-label', 'Постер отсутствует'); icon.textContent = '▤'; img.replaceWith(icon); };
  img.addEventListener('error', fallback, {once: true});
  img.addEventListener('load', () => { if (img.naturalWidth === 208 && img.naturalHeight === 304) fallback(); }, {once: true});
});
document.querySelectorAll('.crew-person img').forEach((img) => {
  img.addEventListener('error', () => {
    const avatar = document.createElement('span');
    avatar.className = 'crew-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = (img.alt || '•').trim().charAt(0).toLocaleUpperCase('ru');
    img.replaceWith(avatar);
  }, {once: true});
});
