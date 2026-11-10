(() => {
  if (!('IntersectionObserver' in window) || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const nodes = document.querySelectorAll('.advantages, .feature-grid article, .steps-grid article, .faq details');
  const observer = new IntersectionObserver(entries => entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); } }), {threshold: 0.12});
  nodes.forEach(node => { node.classList.add('reveal'); observer.observe(node); });
})();
