(() => {
  const article = document.querySelector('.editorial-article');
  const progress = document.querySelector('.reading-line span');
  if (article && progress) {
    let queued = false;
    const update = () => {
      queued = false;
      const rect = article.getBoundingClientRect();
      const total = Math.max(1, article.offsetHeight - innerHeight);
      progress.style.width = `${Math.min(100, Math.max(0, (-rect.top / total) * 100))}%`;
    };
    addEventListener('scroll', () => { if (!queued) { queued = true; requestAnimationFrame(update); } }, {passive: true});
    update();
  }
  if (!('IntersectionObserver' in window) || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const nodes = document.querySelectorAll('.advantages, .feature-grid article, .steps-grid article, .faq details');
  const observer = new IntersectionObserver(entries => entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); } }), {threshold: 0.12});
  nodes.forEach(node => { node.classList.add('reveal'); observer.observe(node); });
})();
