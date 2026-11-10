(() => {
  if (!window.crypto?.randomUUID || !navigator.sendBeacon) return;
  let session = sessionStorage.getItem('observer_visit');
  if (!session) { session = crypto.randomUUID(); sessionStorage.setItem('observer_visit', session); }
  const send = (event, seconds = 0) => navigator.sendBeacon('/api/public/visit/', JSON.stringify({session_id: session, event, seconds}));
  send('pageview');
  let last = Date.now();
  const tick = () => { const now = Date.now(); if (document.visibilityState === 'visible') send('tick', Math.min(30, Math.floor((now - last) / 1000))); last = now; };
  setInterval(tick, 15000);
  document.addEventListener('visibilitychange', tick);
  window.addEventListener('pagehide', tick);
})();
