class CasinoEngine {
    constructor() {
        this.canvas = document.getElementById('casino-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.animationId = null;
        this.colors = ['#2ecc71', '#3498db', '#f1c40f', '#e74c3c', '#ffffff', '#a371f7', '#ff00ff'];
        this.clockInterval = null;
        this.isActive = false;
        
        window.addEventListener('resize', () => this.resize());
        this.resize();
    }

    resize() {
        if (!this.canvas) return;
        const rect = this.canvas.closest('.modal-content').getBoundingClientRect();
        this.canvas.width = rect.width * window.devicePixelRatio;
        this.canvas.height = rect.height * window.devicePixelRatio;
        this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    }

    createParticle(x, y, type = 'firework') {
        const angle = Math.random() * Math.PI * 2;
        const isConfetti = type === 'confetti';
        const velocity = isConfetti ? (Math.random() * 3 + 1) : (Math.random() * 12 + 4);
        
        return {
            x, y,
            vx: Math.cos(angle) * velocity,
            vy: isConfetti ? (Math.random() * 2 + 2) : (Math.sin(angle) * velocity),
            life: 1.0,
            decay: isConfetti ? (Math.random() * 0.01 + 0.005) : (Math.random() * 0.02 + 0.01),
            size: isConfetti ? (Math.random() * 6 + 4) : (Math.random() * 4 + 2),
            color: this.colors[Math.floor(Math.random() * this.colors.length)],
            type: isConfetti ? 'rect' : 'circle',
            gravity: isConfetti ? 0.05 : 0.25,
            friction: 0.96,
            rotation: Math.random() * Math.PI,
            vRotation: (Math.random() - 0.5) * 0.2
        };
    }

    explode(x, y, count, type = 'firework') {
        for (let i = 0; i < count; i++) {
            this.particles.push(this.createParticle(x, y, type));
        }
        if (!this.animationId) {
            this.isActive = true;
            this.draw();
        }
    }

    draw() {
        if (!this.isActive) return;
        
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        for (let i = this.particles.length - 1; i >= 0; i--) {
            const p = this.particles[i];
            p.vx *= p.friction;
            p.vy *= p.friction;
            p.vy += p.gravity;
            p.x += p.vx;
            p.y += p.vy;
            p.life -= p.decay;
            p.rotation += p.vRotation;

            if (p.life <= 0) {
                this.particles.splice(i, 1);
                continue;
            }

            this.ctx.globalAlpha = p.life;
            this.ctx.fillStyle = p.color;
            
            this.ctx.save();
            this.ctx.translate(p.x, p.y);
            this.ctx.rotate(p.rotation);
            
            this.ctx.beginPath();
            if (p.type === 'circle') {
                this.ctx.arc(0, 0, p.size, 0, Math.PI * 2);
            } else {
                this.ctx.rect(-p.size/2, -p.size/2, p.size, p.size * 0.6);
            }
            this.ctx.fill();
            this.ctx.restore();
        }

        if (this.particles.length > 0) {
            this.animationId = requestAnimationFrame(() => this.draw());
        } else {
            this.animationId = null;
            this.isActive = false;
        }
    }

    stopAnimation() {
        this.particles = [];
        this.isActive = false;
        if (this.animationId) cancelAnimationFrame(this.animationId);
        this.animationId = null;
    }
}

let engine;

window.openCasino = function() {
    if (!engine) engine = new CasinoEngine();
    
    let allItemsCount = 0;
    wishlistFolders.forEach(f => allItemsCount += f.items.length);
    if (allItemsCount === 0) {
        showToast('Ваш список избранного пуст!');
        return;
    }

    const modal = document.getElementById('casino-modal');
    const body = document.getElementById('casino-body');
    body.style.opacity = '1';

    const cached = localStorage.getItem('kp_casino_res');
    if (cached) {
        const data = JSON.parse(cached);
        window.renderCasinoResult(data.item, data.expires);
        modal.classList.add('show');
        return;
    }

    const validFolders = wishlistFolders.filter(f => f.items.length > 0);
    
    let html = `<div style="font-size:22px; font-weight:900; margin-bottom:24px; color:#f1c40f;">🎰 Казино</div>`;
    html += `<button class="btn-primary" style="background:linear-gradient(135deg, #e74c3c, #c0392b); margin-bottom:15px;" onclick="window.startCasinoSpin('all')">ВЕСЬ КАТАЛОГ</button>`;
    
    validFolders.forEach(f => {
        html += `<button class="btn-primary casino-btn-choice" onclick="window.startCasinoSpin(${f.id})">
            <span style="color:${f.color}; margin-right:10px;">${Icons[f.icon] || Icons.folder}</span>
            <span style="flex:1;">${f.name}</span>
            <span style="opacity:0.6; font-size:12px;">${f.items.length}</span>
        </button>`;
    });

    body.innerHTML = html;
    modal.classList.add('show');
};

window.startCasinoSpin = function(folderId) {
    let pool = [];
    if (folderId === 'all') {
        let map = new Map();
        wishlistFolders.forEach(f => f.items.forEach(i => map.set(i.show_id, i)));
        pool = Array.from(map.values());
    } else {
        const f = wishlistFolders.find(x => x.id === folderId);
        if (f) pool = f.items;
    }

    if (!pool.length) return;

    const winner = pool[Math.floor(Math.random() * pool.length)];
    const body = document.getElementById('casino-body');
    
    // Плавный переход от выбора к игре
    body.style.opacity = '0';
    
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

        let elapsed = 0, duration = 5000, delay = 50;

        const tick = () => {
            const rnd = pool[Math.floor(Math.random() * pool.length)];
            posterEl.src = rnd.poster_url?.replace('/small/', '/medium/') || '';
            
            let progress = elapsed / duration;
            if (dimmer) dimmer.style.opacity = (progress * 0.9).toString();
            if (window.navigator.vibrate) window.navigator.vibrate(10);
            
            elapsed += delay;
            if (elapsed < duration) {
                delay = 50 + (Math.pow(progress, 3) * 400); 
                setTimeout(tick, delay);
            } else {
                runMysteryPhase(winner);
            }
        };
        tick();
    }, 300);
};

function runMysteryPhase(winner) {
    const posterEl = document.getElementById('cas-poster');
    const placeholderEl = document.getElementById('cas-placeholder');
    const titleEl = document.getElementById('cas-title');
    
    // Мгновенная смена состояния без задержек, чтобы не было "дырки"
    posterEl.style.display = 'none';
    placeholderEl.style.display = 'flex';
    titleEl.textContent = 'КТО ЖЕ ТАМ...';

    const modal = document.querySelector('.casino-modal-content');
    const rect = modal.getBoundingClientRect();
    
    const interval = setInterval(() => {
        if (!document.getElementById('casino-modal').classList.contains('show')) {
            clearInterval(interval);
            return;
        }
        engine.explode(Math.random() * rect.width, -10, 3, 'confetti');
    }, 100);

    setTimeout(() => {
        clearInterval(interval);
        runReveal(winner);
    }, 1500);
}

function runReveal(winner) {
    const expires = Date.now() + 10 * 60 * 1000;
    localStorage.setItem('kp_casino_res', JSON.stringify({ item: winner, expires }));

    // Сначала рендерим результат, чтобы избежать пустоты
    window.renderCasinoResult(winner, expires, true);

    const dimmer = document.getElementById('casino-global-dimmer');
    if (dimmer) {
        dimmer.style.opacity = '0';
        setTimeout(() => dimmer.classList.remove('active'), 300);
    }
    
    document.body.classList.add('app-shake-active');
    setTimeout(() => document.body.classList.remove('app-shake-active'), 500);

    const modal = document.querySelector('.casino-modal-content');
    const rect = modal.getBoundingClientRect();
    const cx = rect.width / 2, cy = rect.height / 3;

    engine.explode(cx, cy, 300, 'firework');
    
    let fireworkTime = 0;
    const launchInterval = setInterval(() => {
        if (!document.getElementById('casino-modal').classList.contains('show')) {
            clearInterval(launchInterval);
            return;
        }
        engine.explode(
            Math.random() * rect.width, 
            Math.random() * (rect.height / 2), 
            80, 
            'firework'
        );
        fireworkTime += 1000;
        if (fireworkTime >= 10000) clearInterval(launchInterval);
    }, 1000);

    if (window.navigator.vibrate) window.navigator.vibrate([100, 50, 100, 50, 500]);
}

window.renderCasinoResult = function(item, expires, withAnimation = false) {
    // Важно: проверяем наличие лейаута, чтобы не перерисовывать всё через innerHTML
    if (!document.getElementById('cas-window')) {
        window.setupCasinoLayout();
    }

    const windowEl = document.getElementById('cas-window');
    const posterEl = document.getElementById('cas-poster');
    const placeholderEl = document.getElementById('cas-placeholder');
    const titleEl = document.getElementById('cas-title');
    const metaEl = document.getElementById('cas-meta');
    const controlsEl = document.getElementById('cas-controls');
    const btnWatch = document.getElementById('cas-btn-watch');
    const btnReset = document.getElementById('cas-btn-reset');
    const countdownEl = document.getElementById('casino-countdown');

    const poster = item.poster_url?.replace('/small/', '/medium/') || '';
    
    if (withAnimation) {
        windowEl.classList.add('casino-win-glow');
    }
    
    posterEl.src = poster;
    posterEl.style.display = 'block';
    posterEl.style.opacity = '1';
    placeholderEl.style.display = 'none';
    
    titleEl.textContent = item.title;
    metaEl.textContent = `${item.year || ''} ${item.type ? `· ${item.type}` : ''}`;

    btnWatch.onclick = () => { 
        window.closeCasino(); 
        window.App.openShowLayer(item.show_id); 
    };
    btnReset.onclick = () => window.resetCasino();

    controlsEl.classList.add('active');

    if (engine.clockInterval) clearInterval(engine.clockInterval);

    const isExpired = Date.now() >= expires;

    const updateExpiredUI = () => {
        if (countdownEl) {
            countdownEl.textContent = "ГОТОВО";
            countdownEl.style.color = "var(--accent)";
        }
        if (btnReset) {
            btnReset.textContent = "🎰 ИГРАТЬ СНОВА";
            btnReset.style.background = "var(--accent)";
            btnReset.style.color = "#fff";
            btnReset.style.borderColor = "var(--accent)";
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
            const m = Math.floor(left / 60), s = (left % 60).toString().padStart(2, '0');
            if (countdownEl) countdownEl.textContent = `${m}:${s}`;
        };
        tick();
        engine.clockInterval = setInterval(tick, 1000);
    }
};

window.resetCasino = function() {
    localStorage.removeItem('kp_casino_res');
    if (engine.clockInterval) clearInterval(engine.clockInterval);
    showToast('Казино сброшено');
    window.openCasino();
};

window.closeCasino = function() {
    const modal = document.getElementById('casino-modal');
    const dimmer = document.getElementById('casino-global-dimmer');
    
    // Запускаем плавное исчезновение
    modal.classList.remove('show');
    if (dimmer) dimmer.classList.remove('active');
    document.body.classList.remove('app-shake-active');

    if (engine) {
        engine.stopAnimation();
    }

    // Ждем окончания CSS анимации (0.4s в стиле модалки) прежде чем чистить интервалы
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
            <div class="casino-info-container">
                <div class="casino-title" id="cas-title"></div>
                <div class="casino-meta-info" id="cas-meta"></div>
                <div id="cas-controls" class="casino-controls-reveal">
                    <button class="btn-primary" id="cas-btn-watch" style="margin-top:0;">Подробнее</button>
                    <div class="casino-timer-wrap">
                        <div style="font-size:10px; color:var(--accent); font-weight:800; margin-bottom:4px;">СЛЕДУЮЩИЙ ШАНС</div>
                        <div class="casino-timer-clock" id="casino-countdown">10:00</div>
                    </div>
                    <button class="btn-reset" id="cas-btn-reset" style="margin-top: 15px;">🎰 СБРОС</button>
                </div>
            </div>
        </div>
    `;
};