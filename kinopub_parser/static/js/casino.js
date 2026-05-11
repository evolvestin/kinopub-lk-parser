window.App = window.App || {};
class CasinoEngine {
    constructor() {
        this.canvas = document.getElementById('casino-canvas');
        this.ctx = this.canvas.getContext('2d', { alpha: true });
        this.particles = [];
        this.rockets = [];
        this.animationId = null;
        this.isActive = false;

        window.addEventListener('resize', () => this.resize());
        this.resize();
    }

    resize() {
        if (!this.canvas) return;
        const rect = this.canvas.closest('.modal-content').getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
    }

    launch() {
        if (!this.isActive) {
            this.isActive = true;
            this.draw();
        }

        const startX = this.canvas.width / 2 + (Math.random() * 100 - 50);
        const startY = this.canvas.height;
        const targetX = Math.random() * this.canvas.width * 0.8 + (this.canvas.width * 0.1);
        const targetY = Math.random() * this.canvas.height * 0.3 + 50;

        const hue = Math.floor(Math.random() * 360);
        
        this.rockets.push({
            x: startX,
            y: startY,
            vx: (targetX - startX) / 45,
            vy: (targetY - startY) / 45,
            targetY: targetY,
            hue: hue,
            alpha: 1,
            history: []
        });
    }

    explode(x, y, hue) {
        const count = 120;
        const baseSize = Math.random() * 1.5 + 1;
        
        for (let i = 0; i < count; i++) {
            const angle = Math.random() * Math.PI * 2;
            const speed = Math.random() * 6 + 2;
            const friction = 0.95 + Math.random() * 0.03;
            
            this.particles.push({
                x: x,
                y: y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                hue: hue + (Math.random() * 40 - 20),
                brightness: 50 + Math.random() * 30,
                alpha: 1,
                decay: Math.random() * 0.015 + 0.007,
                size: baseSize,
                friction: friction,
                gravity: 0.12,
                twinkle: Math.random() > 0.4
            });
        }
    }

    draw() {
        if (!this.isActive) return;

        this.ctx.globalCompositeOperation = 'destination-out';
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.2)';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        this.ctx.globalCompositeOperation = 'lighter';

        for (let i = this.rockets.length - 1; i >= 0; i--) {
            const r = this.rockets[i];
            
            r.history.push({ x: r.x, y: r.y });
            if (r.history.length > 5) r.history.shift();

            r.x += r.vx;
            r.y += r.vy;
            r.vy += 0.05;

            this.ctx.beginPath();
            this.ctx.strokeStyle = `hsla(${r.hue}, 100%, 70%, ${r.alpha})`;
            this.ctx.lineWidth = 2;
            if (r.history.length > 1) {
                this.ctx.moveTo(r.history[0].x, r.history[0].y);
                this.ctx.lineTo(r.x, r.y);
            }
            this.ctx.stroke();

            if (r.vy >= 0 || r.y <= r.targetY) {
                this.explode(r.x, r.y, r.hue);
                this.rockets.splice(i, 1);
            }
        }

        for (let i = this.particles.length - 1; i >= 0; i--) {
            const p = this.particles[i];
            
            p.vx *= p.friction;
            p.vy *= p.friction;
            p.vy += p.gravity;
            p.x += p.vx;
            p.y += p.vy;
            p.alpha -= p.decay;

            if (p.alpha <= 0) {
                this.particles.splice(i, 1);
                continue;
            }

            let b = p.brightness;
            if (p.twinkle && Math.random() > 0.8) {
                b += 30;
            }

            this.ctx.fillStyle = `hsla(${p.hue}, 100%, ${b}%, ${p.alpha})`;
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.size * (0.5 + p.alpha * 0.5), 0, Math.PI * 2);
            this.ctx.fill();
        }

        if (this.particles.length > 0 || this.rockets.length > 0) {
            this.animationId = requestAnimationFrame(() => this.draw());
        } else {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            this.isActive = false;
        }
    }

    stopAnimation() {
        this.particles = [];
        this.rockets = [];
        this.isActive = false;
        if (this.animationId) cancelAnimationFrame(this.animationId);
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }
}

let engine;

window.openCasino = async function() {
    if (!engine) engine = new CasinoEngine();
    
    const body = document.getElementById('casino-body');
    const headerIcon = document.getElementById('casino-header-icon');
    const debugBtn = document.getElementById('casino-debug-reset');
    
    if (debugBtn) {
        debugBtn.style.display = window.IS_DEBUG ? 'block' : 'none';
    }
    
    if (headerIcon) headerIcon.innerHTML = '🎰';
    body.style.opacity = '1';
    body.innerHTML = '<div class="spinner" style="margin: 20px auto;"></div>';

    // Управляем через состояние
    window.App.setState('modals.casino.isOpen', true);

    try {
        const res = await fetch('/api/webapp/casino/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action: 'status', init_data: tg?.initData || '' })
        });
        const data = await res.json();

        if (data.active_spin) {
            window.renderCasinoResult(data.active_spin.show, data.active_spin.expires);
        } else {
            window.showCasinoMainMenu();
        }
    } catch(e) {
        window.App.showToast('Ошибка соединения');
        window.closeCasino();
    }
};

window.showCasinoMainMenu = function() {
    const body = document.getElementById('casino-body');
    body.innerHTML = `
        <div style="color:var(--accent); font-weight:800; font-size:14px; margin-bottom:15px; text-transform:uppercase; letter-spacing:0.5px;">✅ Рулетка доступна</div>
        <button class="btn-primary" style="margin-bottom:15px;" onclick="window.showCasinoFolders()">Запустить рулетку</button>
        <button class="btn-primary" style="background:var(--bg-input); color:var(--text-primary); border:1px solid var(--border);" onclick="window.loadCasinoHistory()">История</button>
    `;
};

window.checkCasinoStatus = async function() {
    const body = document.getElementById('casino-body');
    body.innerHTML = '<div class="spinner" style="margin: 20px auto;"></div>';

    try {
        const res = await fetch('/api/webapp/casino/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action: 'status', init_data: tg?.initData || '' })
        });
        const data = await res.json();

        if (data.active_spin) {
            window.renderCasinoResult(data.active_spin.show, data.active_spin.expires);
        } else {
            window.showCasinoFolders();
        }
    } catch(e) {
        window.App.showToast('Ошибка соединения');
        window.closeCasino();
    }
};

window.showCasinoFolders = function() {
    const folders = window.App.getState('data.wishlistFolders') || [];
    let allItemsCount = 0;
    folders.forEach(f => allItemsCount += f.items.length);
    
    if (allItemsCount === 0) {
        window.App.showToast('Ваш список избранного пуст!');
        window.closeCasino();
        return;
    }

    const validFolders = folders.filter(f => f.items.length > 0);
    if (validFolders.length === 1) {
        window.startCasinoSpin(validFolders[0].id);
        return;
    }

    const body = document.getElementById('casino-body');
    let html = `<button class="btn-primary" style="margin-bottom:15px;" onclick="window.startCasinoSpin('all')">Весь каталог</button>`;
    
    validFolders.forEach(f => {
        html += `<button class="btn-primary casino-btn-choice" onclick="window.startCasinoSpin(${f.id})">
            <span style="color:${f.color}; margin-right:10px;">${window.App.Icons[f.icon] || window.App.Icons.folder}</span>
            <span style="flex:1; color: var(--text-primary);">${f.name}</span>
            <span style="opacity:0.6; font-size:12px; color: var(--text-muted);">${f.items.length}</span>
        </button>`;
    });

    body.innerHTML = html;
};

window.startCasinoSpin = async function(folderId) {
    const body = document.getElementById('casino-body');
    body.style.opacity = '0';

    try {
        const res = await fetch('/api/webapp/casino/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action: 'spin', folder_id: folderId, init_data: tg?.initData || '' })
        });
        const data = await res.json();
        if (data.error) {
            window.App.showToast('Ошибка: ' + data.error);
            window.closeCasino();
            return;
        }

        const winner = data.show;
        const expires = data.expires;

        let pool = [];
        if (folderId === 'all') {
            let map = new Map();
            window.App.wishlistFolders.forEach(f => f.items.forEach(i => map.set(i.show_id, i)));
            pool = Array.from(map.values());
        } else {
            const f = window.App.wishlistFolders.find(x => x.id === folderId);
            if (f) pool = f.items;
        }
        if (!pool.length) pool = [winner];

        setTimeout(() => {
            window.setupCasinoLayout();
            body.style.opacity = '1';
            
            let dimmer = document.getElementById('casino-global-dimmer');
            if (!dimmer) {
                dimmer = document.createElement('div');
                dimmer.id = 'casino-global-dimmer';
                dimmer.className = 'casino-dimmed';
                document.body.appendChild(dimmer);
            }
            dimmer.classList.add('active');

            const posterEl = document.getElementById('cas-poster');
            const placeholderEl = document.getElementById('cas-placeholder');
            const titleEl = document.getElementById('cas-title');
            
            posterEl.style.display = 'block';
            placeholderEl.style.display = 'none';
            titleEl.textContent = 'КРУТИМ...';

            let elapsed = 0, duration = 4000, delay = 50;

            const tick = () => {
                const rnd = pool[Math.floor(Math.random() * pool.length)];
                posterEl.src = rnd.poster_url?.replace('/small/', '/medium/') || '';
                
                let progress = elapsed / duration;
                if (dimmer) dimmer.style.opacity = (progress * 0.7).toString();
                
                if (elapsed % 200 === 0 && progress < 0.8) {
                    engine.launch();
                }
                
                if (window.navigator.vibrate) window.navigator.vibrate(10);
                
                elapsed += delay;
                if (elapsed < duration) {
                    delay = 50 + (Math.pow(progress, 3) * 400); 
                    setTimeout(tick, delay);
                } else {
                    window.runMysteryPhase(winner, expires);
                }
            };
            tick();
        }, 300);

    } catch (e) {
        window.App.showToast('Ошибка при запуске рулетки');
        window.closeCasino();
    }
};


window.runMysteryPhase = function(winner, expires) {
    const posterEl = document.getElementById('cas-poster');
    const placeholderEl = document.getElementById('cas-placeholder');
    const titleEl = document.getElementById('cas-title');
    
    posterEl.style.display = 'none';
    placeholderEl.style.display = 'flex';
    titleEl.textContent = 'КТО ЖЕ ТАМ...';

    let count = 0;
    const timer = setInterval(() => {
        if (!document.getElementById('casino-modal').classList.contains('show') || count >= 3) {
            clearInterval(timer);
            return;
        }
        engine.launch();
        count++;
    }, 500);

    setTimeout(() => {
        clearInterval(timer);
        window.runReveal(winner, expires);
    }, 1600);
};

window.runReveal = function(winner, expires) {
    window.renderCasinoResult(winner, expires, true);

    const revealAnimations = () => {
        const dimmer = document.getElementById('casino-global-dimmer');
        if (dimmer) {
            dimmer.style.opacity = '0';
            setTimeout(() => dimmer.classList.remove('active'), 300);
        }
        
        document.body.classList.add('app-shake-active');
        setTimeout(() => document.body.classList.remove('app-shake-active'), 500);

        for (let i = 0; i < 6; i++) {
            setTimeout(() => {
                if (document.getElementById('casino-modal').classList.contains('show')) {
                    engine.launch();
                    engine.launch();
                }
            }, i * 300);
        }

        if (window.navigator.vibrate) window.navigator.vibrate([100, 50, 100, 50, 500]);
    };

    const img = new Image();
    img.src = winner.poster_url?.replace('/small/', '/medium/') || '';
    img.onload = revealAnimations;
    img.onerror = revealAnimations;
};

function runMysteryPhase(winner) {
    const posterEl = document.getElementById('cas-poster');
    const placeholderEl = document.getElementById('cas-placeholder');
    const titleEl = document.getElementById('cas-title');
    
    posterEl.style.display = 'none';
    placeholderEl.style.display = 'flex';
    titleEl.textContent = 'КТО ЖЕ ТАМ...';

    let count = 0;
    const timer = setInterval(() => {
        if (!document.getElementById('casino-modal').classList.contains('show') || count >= 3) {
            clearInterval(timer);
            return;
        }
        engine.launch();
        count++;
    }, 500);

    setTimeout(() => {
        clearInterval(timer);
        runReveal(winner);
    }, 1600);
}

function runReveal(winner) {
    const expires = Date.now() + 24 * 60 * 60 * 1000;
    localStorage.setItem('kp_casino_res', JSON.stringify({ item: winner, expires }));

    window.renderCasinoResult(winner, expires, true);

    const revealAnimations = () => {
        const dimmer = document.getElementById('casino-global-dimmer');
        if (dimmer) {
            dimmer.style.opacity = '0';
            setTimeout(() => dimmer.classList.remove('active'), 300);
        }
        
        document.body.classList.add('app-shake-active');
        setTimeout(() => document.body.classList.remove('app-shake-active'), 500);

        for (let i = 0; i < 6; i++) {
            setTimeout(() => {
                if (document.getElementById('casino-modal').classList.contains('show')) {
                    engine.launch();
                    engine.launch();
                }
            }, i * 300);
        }

        if (window.navigator.vibrate) window.navigator.vibrate([100, 50, 100, 50, 500]);
    };

    const img = new Image();
    img.src = winner.poster_url?.replace('/small/', '/medium/') || '';
    img.onload = revealAnimations;
    img.onerror = revealAnimations;
}

window.renderCasinoResult = function(item, expires, withAnimation = false) {
    if (!document.getElementById('cas-window')) {
        window.setupCasinoLayout();
    }

    // Сохраняем результат в контекст стейта для восстановления при перезагрузке
    window.App.setState('modals.casino.context', { item, expires });

    const windowEl = document.getElementById('cas-window');
    const posterEl = document.getElementById('cas-poster');
    const placeholderEl = document.getElementById('cas-placeholder');
    const titleEl = document.getElementById('cas-title');
    const metaEl = document.getElementById('cas-meta');
    const controlsEl = document.getElementById('cas-controls');
    const btnWatch = document.getElementById('cas-btn-watch');
    const countdownEl = document.getElementById('casino-countdown');

    const poster = item.poster_url?.replace('/small/', '/medium/') || '';
    
    if (withAnimation) {
        windowEl.classList.add('casino-win-glow');
    }
    
    posterEl.src = poster;
    posterEl.style.display = 'block';
    posterEl.style.opacity = '1';
    placeholderEl.style.display = 'none';
    
    let badgesContainer = windowEl.querySelector('.grid-badges');
    if (item.user_rating) {
        if (!badgesContainer) {
            badgesContainer = document.createElement('div');
            badgesContainer.className = 'grid-badges';
            windowEl.appendChild(badgesContainer);
        }
        badgesContainer.innerHTML = `<span class="rating-badge" style="background:rgba(0,0,0,0.6);border:none;">${window.App.Icons.star}${item.user_rating}</span>`;
        badgesContainer.style.display = 'flex';
    } else if (badgesContainer) {
        badgesContainer.style.display = 'none';
    }
    
    titleEl.textContent = item.title;
    metaEl.textContent = `${item.year || ''} ${item.type ? '· ' + (window.App.SHOW_TYPE_RU[item.type] || item.type) : ''}`;

    btnWatch.onclick = () => { 
        window.closeCasino(); 
        window.App.openShowLayer(item.show_id || item.id); 
    };

    controlsEl.classList.add('active');

    if (engine.clockInterval) clearInterval(engine.clockInterval);

    const isExpired = Date.now() >= expires;

    const updateExpiredUI = () => {
        if (countdownEl) {
            countdownEl.innerHTML = '<button class="btn-primary" style="margin-top: 10px; padding: 10px; font-size: 14px; width: 100%;" onclick="window.showCasinoFolders()">Крутить снова</button>';
            countdownEl.previousElementSibling.textContent = "✅ РУЛЕТКА ГОТОВА";
            countdownEl.previousElementSibling.style.color = "var(--accent)";
        }
    };

    if (isExpired) {
        updateExpiredUI();
    } else {
        const tick = () => {
            const left = Math.floor((expires - Date.now()) / 1000);
            if (left <= 0) { 
                clearInterval(engine.clockInterval); 
                updateExpiredUI();
                return; 
            }
            const h = Math.floor(left / 3600);
            const m = Math.floor((left % 3600) / 60);
            const s = (left % 60).toString().padStart(2, '0');
            
            if (h > 0) {
                countdownEl.textContent = `${h}:${m.toString().padStart(2, '0')}:${s}`;
            } else {
                countdownEl.textContent = `${m}:${s}`;
            }
        };
        tick();
        engine.clockInterval = setInterval(tick, 1000);
    }
};

window.loadCasinoHistory = async function() {
    window.App.closeCasino();
    window.App.showLoader();

    try {
        const res = await fetch('/api/webapp/casino/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action: 'history', init_data: tg?.initData || '' })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        window.App.D.casino_history = data.history || [];
        window.App.openHistoryLayer('casino', 'История рулетки');
    } catch(e) {
        window.App.showToast('Ошибка загрузки истории');
    } finally {
        window.App.hideLoader();
    }
};

window.resetCasino = async function() {
    try {
        await fetch('/api/webapp/casino/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action: 'reset', init_data: tg?.initData || '' })
        });
    } catch(e) {}

    if (engine && engine.clockInterval) {
        clearInterval(engine.clockInterval);
    }
    window.closeCasino();
    showToast('Cброшено');
};

window.closeCasino = function() {
    // Управляем через состояние
    window.App.setState('modals.casino.isOpen', false);

    const dimmer = document.getElementById('casino-global-dimmer');
    if (dimmer) dimmer.classList.remove('active');
    document.body.classList.remove('app-shake-active');

    if (engine) {
        engine.stopAnimation();
    }

    setTimeout(() => {
        if (engine && engine.clockInterval) {
            clearInterval(engine.clockInterval);
        }
    }, 400);
};

window.setupCasinoLayout = function() {
    const body = document.getElementById('casino-body');
    body.style.transition = 'opacity 0.3s ease';
    body.innerHTML = `
        <div id="cas-container" class="casino-slot-container active">
            <div class="casino-slot-window" id="cas-window">
                <img id="cas-poster" src="" alt="" style="display:none; width:100%; height:100%; object-fit:cover;">
                <div id="cas-placeholder" style="display:flex; align-items:center; justify-content:center; height:100%; font-size:100px; font-weight:900; color:var(--accent);">?</div>
            </div>
            <div class="casino-info-container" style="height: auto; padding-bottom: 10px;">
                <div class="casino-title" id="cas-title"></div>
                <div class="casino-meta-info" id="cas-meta"></div>
                <div id="cas-controls" class="casino-controls-reveal">
                    <div style="display: flex; gap: 10px; width: 100%;">
                        <button class="btn-primary" id="cas-btn-watch" style="margin-top:0; flex: 1;">Подробнее</button>
                        <button class="btn-primary" style="margin-top:0; flex: 1; background:var(--bg-input); color:var(--text-primary); border:1px solid var(--border);" onclick="window.loadCasinoHistory()">История</button>
                    </div>
                    <div class="casino-timer-wrap" style="width: 100%;">
                        <div style="font-size:10px; color:var(--accent); font-weight:800; margin-bottom:4px;">СЛЕДУЮЩИЙ ШАНС</div>
                        <div class="casino-timer-clock" id="casino-countdown">10:00</div>
                    </div>
                </div>
            </div>
        </div>
    `;
};