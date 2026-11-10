(() => {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) return;
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    const node = entry.target, target = Number(node.dataset.number.replace(',', '.')), digits = Number(node.dataset.decimals || 0);
    if (!Number.isFinite(target)) return;
    observer.unobserve(node);
    const started = performance.now(), duration = 3200;
    const frame = now => { const progress = Math.min((now - started) / duration, 1), eased = 1 - Math.pow(1 - progress, 2); node.textContent = (target * eased).toLocaleString('ru-RU', {minimumFractionDigits: digits, maximumFractionDigits: digits}); if (progress < 1) requestAnimationFrame(frame); };
    requestAnimationFrame(frame);
  }), {threshold: .3});
  document.querySelectorAll('.count-up').forEach(node => observer.observe(node));
})();
