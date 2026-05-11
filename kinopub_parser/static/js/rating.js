window.App = window.App || {};

Object.assign(window.App, {
    rateData: {
        showId: null,
        showType: null,
        level: 'show', 
        season: null,
        episode: null,
        title: '',
        currentVal: 5.0,
        isDragging: false,
        episodesData: [],
        needsRefresh: false
    },

    openRateModal: function(showId, title, currentRating, type = null) {
        const hasExisting = (currentRating !== undefined && currentRating !== 'null' && currentRating !== null);
        
        const context = {
            showId: showId,
            showType: type || 'Movie',
            title: title,
            currentVal: hasExisting ? parseFloat(currentRating) : 5.0,
            hasExistingRating: hasExisting,
            needsRefresh: false,
            season: null,
            episode: null,
            level: 'show',
            episodesData: []
        };

        // Сначала устанавливаем контекст, потом открываем
        this.setState('modals.rateShow.context', context);
        this.setState('modals.rateShow.isOpen', true);

        document.getElementById('rate-show-title').textContent = title;
        
        // Инициализация UI компонентов
        requestAnimationFrame(() => {
            this.initSlider();
            this.setRateLevel('show');
        });
    },

    initSlider: function() {
        const hitArea = document.getElementById('rate-slider-hit');
        if (!hitArea) return;

        const handleMove = (e) => {
            const ctx = this.getState('modals.rateShow.context');
            if (!ctx.isDragging && e.type === 'pointermove') return;
            
            const rect = hitArea.querySelector('.rate-slider-track').getBoundingClientRect();
            const clientX = e.clientX || (e.touches ? e.touches[0].clientX : 0);
            let percent = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
            
            let val = Math.round((1 + (percent * 9)) * 2) / 2;
            
            if (val !== ctx.currentVal) {
                const oldVal = ctx.currentVal;
                ctx.currentVal = val;
                this.setState('modals.rateShow.context', ctx);
                this.updateSliderUI(true);
                
                if (window.navigator.vibrate) {
                    window.navigator.vibrate(Math.floor(val) !== Math.floor(oldVal) ? 10 : 3);
                }
            }
        };

        hitArea.onpointerdown = (e) => {
            const ctx = this.getState('modals.rateShow.context');
            ctx.isDragging = true;
            this.setState('modals.rateShow.context', ctx);
            hitArea.setPointerCapture(e.pointerId);
            handleMove(e);
        };
        hitArea.onpointermove = handleMove;
        hitArea.onpointerup = () => {
            const ctx = this.getState('modals.rateShow.context');
            ctx.isDragging = false;
            this.setState('modals.rateShow.context', ctx);
        };
        this.updateSliderUI();
    },

    updateSliderUI: function(withPulse = false) {
        const ctx = window.App.getState('modals.rateShow.context');
        if (!ctx) return;

        const val = ctx.currentVal;
        const percent = ((val - 1) / 9) * 100;
        
        const fill = document.getElementById('rate-slider-fill');
        const handle = document.getElementById('rate-slider-handle');
        const huge = document.getElementById('rate-huge-val');
        const modalContent = document.querySelector('#rate-show-modal .modal-content');

        if (fill) fill.style.width = `${percent}%`;
        if (handle) handle.style.left = `${percent}%`;
        if (huge) huge.innerHTML = `${val.toFixed(val % 1 === 0 ? 0 : 1)}<span>/ 10</span>`;

        if (modalContent) {
            modalContent.classList.remove('score-low', 'score-mid', 'score-high');
            if (val < 5) modalContent.classList.add('score-low');
            else if (val < 8) modalContent.classList.add('score-mid');
            else modalContent.classList.add('score-high');
        }
    },

    setRateLevel: function (level, params = {}) {
        const ctx = window.App.State.getState('modals.rateShow.context');
        ctx.level = level;
        
        const slider = document.getElementById('rate-slider-container');
        const epNav = document.getElementById('rate-episodes-nav');
        const backBtn = document.getElementById('rate-back-btn');
        const breadcrumb = document.getElementById('rate-breadcrumb');
        const modeToggle = document.getElementById('rate-mode-toggle');
        const submitBtn = document.getElementById('btn-submit-rating');
        const delBtn = document.getElementById('btn-delete-rating');
        const modalContent = document.querySelector('#rate-show-modal .modal-content');

        if (slider) slider.style.display = 'none';
        if (epNav) epNav.style.display = 'none';
        if (submitBtn) submitBtn.style.display = 'none';
        if (delBtn) delBtn.style.display = 'none';
        
        if (backBtn) backBtn.style.display = (level !== 'show' && level !== 'seasons') ? 'block' : 'none';

        if (modalContent && (level === 'seasons' || level === 'episodes')) {
            modalContent.classList.remove('score-low', 'score-mid', 'score-high');
        }

        if (level === 'show') {
            ctx.season = null;
            ctx.episode = null;
            if (breadcrumb) breadcrumb.textContent = 'Общая оценка';
            if (slider) slider.style.display = 'flex';
            if (submitBtn) submitBtn.style.display = 'block';
            if (modeToggle) {
                modeToggle.querySelector('#rate-mode-main').classList.add('active');
                modeToggle.querySelector('#rate-mode-ep').classList.remove('active');
            }
            window.App.State.setState('modals.rateShow.context', ctx);
            window.App.updateSliderUI();
        } 
        else if (level === 'seasons') {
            ctx.season = null;
            ctx.episode = null;
            if (breadcrumb) breadcrumb.textContent = 'Выбор сезона';
            if (epNav) epNav.style.display = 'block';
            if (modeToggle) {
                modeToggle.querySelector('#rate-mode-main').classList.remove('active');
                modeToggle.querySelector('#rate-mode-ep').classList.add('active');
            }
            window.App.State.setState('modals.rateShow.context', ctx);
            window.App.loadAndRenderSeasons();
        }
        else if (level === 'episodes') {
            ctx.season = params.season;
            ctx.episode = null;
            if (breadcrumb) breadcrumb.textContent = `Сезон ${params.season}`;
            if (epNav) epNav.style.display = 'block';
            window.App.State.setState('modals.rateShow.context', ctx);
            window.App.renderEpisodes(params.season);
        }
        else if (level === 'score') {
            ctx.season = params.season;
            ctx.episode = params.episode;
            
            const hasExisting = (params.rating && params.rating !== 'null' && params.rating !== null);
            ctx.hasExistingRating = hasExisting;
            ctx.currentVal = hasExisting ? parseFloat(params.rating) : 5.0;
            
            if (breadcrumb) breadcrumb.textContent = `S${params.season} E${params.episode}`;
            if (slider) slider.style.display = 'flex';
            if (submitBtn) submitBtn.style.display = 'block';
            window.App.State.setState('modals.rateShow.context', ctx);
            window.App.updateSliderUI();
        }
    },

    loadAndRenderSeasons: async function() {
        const epNav = document.getElementById('rate-episodes-nav');
        if (!epNav) return;
        epNav.innerHTML = '<div class="loader-inline"><div class="spinner"></div></div>';
        try {
            const ctx = window.App.State.getState('modals.rateShow.context');
            const r = await fetch('/api/webapp/get_episodes/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ show_id: ctx.showId, init_data: tg?.initData || '' })
            });
            const data = await r.json();
            
            if (!data.seasons || data.seasons.length === 0) {
                epNav.innerHTML = '<div class="empty">Данные о сезонах отсутствуют.<br><small style="opacity:0.6; font-weight:normal;">Требуется обновление хронометража</small></div>';
                return;
            }

            ctx.episodesData = data.seasons;
            window.App.State.setState('modals.rateShow.context', ctx);

            let html = '<div class="rating-grid-wa">';
            data.seasons.forEach(s => {
                const rated = s.episodes.filter(e => e.rating).length;
                const badge = rated ? `<span style="color:var(--accent);font-size:10px;display:block;">★ ${rated}/${s.episodes.length}</span>` : `<span style="opacity:0.5;font-size:10px;display:block;">0/${s.episodes.length}</span>`;
                html += `<button class="rating-grid-btn" onclick="window.App.setRateLevel('episodes', {season: ${s.season_number}})">
                    Сезон ${s.season_number}${badge}
                </button>`;
            });
            epNav.innerHTML = html + '</div>';
        } catch(e) { 
            epNav.innerHTML = '<div class="empty">Ошибка загрузки данных</div>'; 
        }
    },

    renderEpisodes: function (seasonNum) {
        const epNav = document.getElementById('rate-episodes-nav');
        if (!epNav) return;
        const ctx = window.App.State.getState('modals.rateShow.context');
        const season = ctx.episodesData.find(s => s.season_number === seasonNum);
        let html = '<div class="rating-grid-wa" style="grid-template-columns: repeat(4, 1fr);">';
        season.episodes.forEach(e => {
            let colorClass = '';
            if (e.rating) {
                if (e.rating < 5) colorClass = 'score-low';
                else if (e.rating < 8) colorClass = 'score-mid';
                else colorClass = 'score-high';
            }
            const isActive = e.rating ? 'active ' + colorClass : '';
            const label = e.rating ? `<span style="font-weight:900;">★ ${e.rating}</span>` : `E${e.episode_number}`;
            html += `<button class="rating-grid-btn ${isActive}" onclick="window.App.setRateLevel('score', {season: ${seasonNum}, episode: ${e.episode_number}, rating: ${e.rating}})">${label}</button>`;
        });
        epNav.innerHTML = html + '</div>';
    },

    submitRatingFromSlider: function() {
        const ctx = window.App.State.getState('modals.rateShow.context');
        window.App.submitRating(ctx.currentVal);
    },

    submitRating: async function(rating) {
        const btn = document.getElementById('btn-submit-rating');
        const origText = btn.textContent;
        btn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px;border-top-color:#fff;margin:0;"></div>';
        btn.disabled = true;
        
        const ctx = window.App.State.getState('modals.rateShow.context');
        
        try {
            await fetch('/api/webapp/rate/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    init_data: tg?.initData || '',
                    show_id: ctx.showId,
                    rating: rating,
                    season: ctx.season,
                    episode: ctx.episode
                })
            });
            
            window.App.showToast('Оценка сохранена');
            window.App.Data.cache.clear();
            ctx.needsRefresh = true;
            window.App.State.setState('modals.rateShow.context', ctx);
            
            if (ctx.episode) {
                window.App.setRateLevel('seasons');
            } else {
                window.App.closeRateModal();
            }
        } catch(e) { window.App.showToast('Ошибка'); } finally {
            btn.textContent = origText;
            btn.disabled = false;
        }
    },

    deleteRating: async function() {
        if (!confirm('Удалить оценку?')) return;
        const ctx = window.App.State.getState('modals.rateShow.context');
        try {
            await fetch('/api/webapp/delete_rating/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    init_data: tg?.initData || '',
                    show_id: ctx.showId,
                    season: ctx.season,
                    episode: ctx.episode
                })
            });
            window.App.showToast('Оценка удалена');
            window.App.Data.cache.clear();
            ctx.needsRefresh = true;
            window.App.State.setState('modals.rateShow.context', ctx);
            if (ctx.episode)window.App.setRateLevel('seasons');
            else window.App.closeRateModal();
        } catch(e) {}
    },

    rateGoBack: function() {
        const ctx = window.App.State.getState('modals.rateShow.context');

        if (ctx.level === 'score') {
            window.App.setRateLevel('episodes', { season: ctx.season });
        } else if (ctx.level === 'episodes') {
            window.App.setRateLevel('seasons');
        }
    },

    closeRateModal: function() {
        const ctx = window.App.getState('modals.rateShow.context');
        const showId = ctx?.showId;
        const needsRefresh = ctx?.needsRefresh;
        
        window.App.closeModal('rateShow');

        if (needsRefresh && showId) {
            if (window.App.getState('nav.activeMainView') === 'stats') {
                window.App.load(window.App.getState('nav.query.y'));
            }
            window.App.openShowLayer(showId);
        }
    },

});
