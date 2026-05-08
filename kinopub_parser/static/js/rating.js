window.App = window.App || {};

window.App.rateData = {
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
};

window.App.openRateModal = function(showId, title, currentRating, type = null) {
    const hasExisting = (currentRating && currentRating !== 'null' && currentRating !== null);
    
    this.rateData = {
        ...this.rateData,
        showId: showId,
        showType: type || 'Movie',
        title: title,
        currentVal: hasExisting ? parseFloat(currentRating) : 1.0,
        hasExistingRating: hasExisting,
        needsRefresh: false,
        season: null,
        episode: null
    };

    document.getElementById('rate-show-title').textContent = title;
    const isSeries = ['Series', 'Documentary Series', 'TV Show'].includes(this.rateData.showType);
    document.getElementById('rate-mode-toggle').style.display = isSeries ? 'flex' : 'none';
    
    this.initSlider();
    this.setRateLevel('show');
    document.getElementById('rate-show-modal').classList.add('show');
};


window.App.initSlider = function() {
    const hitArea = document.getElementById('rate-slider-hit');
    if (!hitArea) return;

    const handleMove = (e) => {
        if (!this.rateData.isDragging && e.type === 'pointermove') return;
        
        const rect = hitArea.querySelector('.rate-slider-track').getBoundingClientRect();
        const clientX = e.clientX || (e.touches ? e.touches[0].clientX : 0);
        let x = clientX - rect.left;
        let percent = Math.max(0, Math.min(1, x / rect.width));
        
        // Маппинг на шкалу 1-10 с шагом 0.5
        let val = 1 + (percent * 9);
        val = Math.round(val * 2) / 2;
        
        if (val !== this.rateData.currentVal) {
            this.rateData.currentVal = val;
            this.updateSliderUI(true);
            if (window.navigator.vibrate) window.navigator.vibrate(5);
        }
    };

    hitArea.onpointerdown = (e) => {
        this.rateData.isDragging = true;
        hitArea.setPointerCapture(e.pointerId);
        handleMove(e);
    };

    hitArea.onpointermove = handleMove;

    hitArea.onpointerup = () => {
        this.rateData.isDragging = false;
    };

    this.updateSliderUI();
};

window.App.updateSliderUI = function(withPulse = false) {
    const val = this.rateData.currentVal;
    const percent = ((val - 1) / 9) * 100;
    
    const fill = document.getElementById('rate-slider-fill');
    const handle = document.getElementById('rate-slider-handle');
    const huge = document.getElementById('rate-huge-val');
    const container = document.getElementById('rate-slider-container');
    const delBtn = document.getElementById('btn-delete-rating');

    fill.style.width = `${percent}%`;
    handle.style.left = `${percent}%`;
    huge.innerHTML = `${val.toFixed(1 === val % 1 ? 0 : 1)}<span>/ 10</span>`;

    if (withPulse) {
        huge.classList.remove('rate-pulse');
        void huge.offsetWidth;
        huge.classList.add('rate-pulse');
    }

    container.classList.remove('score-low', 'score-mid', 'score-high');
    if (val < 5) container.classList.add('score-low');
    else if (val < 8) container.classList.add('score-mid');
    else container.classList.add('score-high');

    const isInputView = (this.rateData.level === 'show' || this.rateData.level === 'score');
    delBtn.style.display = (isInputView && this.rateData.hasExistingRating) ? 'block' : 'none';
};

window.App.setRateLevel = function(level, params = {}) {
    this.rateData.level = level;
    const slider = document.getElementById('rate-slider-container');
    const epNav = document.getElementById('rate-episodes-nav');
    const backBtn = document.getElementById('rate-back-btn');
    const breadcrumb = document.getElementById('rate-breadcrumb');
    const modeToggle = document.getElementById('rate-mode-toggle');
    const submitBtn = document.getElementById('btn-submit-rating');
    const delBtn = document.getElementById('btn-delete-rating');

    slider.style.display = 'none';
    epNav.style.display = 'none';
    submitBtn.style.display = 'none';
    delBtn.style.display = 'none';
    
    backBtn.style.display = (level !== 'show') ? 'block' : 'none';

    if (level === 'show') {
        this.rateData.season = null;
        this.rateData.episode = null;
        breadcrumb.textContent = 'Общая оценка';
        slider.style.display = 'flex';
        submitBtn.style.display = 'block';
        modeToggle.querySelector('#rate-mode-main').classList.add('active');
        modeToggle.querySelector('#rate-mode-ep').classList.remove('active');
        this.updateSliderUI();
    } 
    else if (level === 'seasons') {
        this.rateData.season = null;
        this.rateData.episode = null;
        breadcrumb.textContent = 'Выбор сезона';
        epNav.style.display = 'block';
        modeToggle.querySelector('#rate-mode-main').classList.remove('active');
        modeToggle.querySelector('#rate-mode-ep').classList.add('active');
        this.loadAndRenderSeasons();
    }
    else if (level === 'episodes') {
        this.rateData.season = params.season;
        this.rateData.episode = null;
        breadcrumb.textContent = `Сезон ${params.season}`;
        epNav.style.display = 'block';
        this.renderEpisodes(params.season);
    }
    else if (level === 'score') {
        this.rateData.season = params.season;
        this.rateData.episode = params.episode;
        
        const hasExisting = (params.rating && params.rating !== 'null' && params.rating !== null);
        this.rateData.hasExistingRating = hasExisting;
        this.rateData.currentVal = hasExisting ? parseFloat(params.rating) : 1.0;
        
        breadcrumb.textContent = `S${params.season} E${params.episode}`;
        slider.style.display = 'flex';
        submitBtn.style.display = 'block';
        this.updateSliderUI();
    }
};

window.App.loadAndRenderSeasons = async function() {
    const epNav = document.getElementById('rate-episodes-nav');
    epNav.innerHTML = '<div class="loader-inline"><div class="spinner"></div></div>';
    try {
        const r = await fetch('/api/webapp/get_episodes/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ show_id: this.rateData.showId, init_data: tg?.initData || '' })
        });
        const data = await r.json();
        
        if (!data.seasons || data.seasons.length === 0) {
            epNav.innerHTML = '<div class="empty">Данные о сезонах отсутствуют.<br><small style="opacity:0.6; font-weight:normal;">Требуется обновление хронометража</small></div>';
            return;
        }

        this.rateData.episodesData = data.seasons;

        let html = '<div class="rating-grid-wa" style="grid-template-columns: repeat(3, 1fr);">';
        data.seasons.forEach(s => {
            const rated = s.episodes.filter(e => e.rating).length;
            const badge = rated ? `<span style="color:var(--accent);font-size:10px;display:block;">★ ${rated}/${s.episodes.length}</span>` : `<span style="opacity:0.5;font-size:10px;display:block;">0/${s.episodes.length}</span>`;
            html += `<button class="rating-grid-btn" style="height:auto;" onclick="window.App.setRateLevel('episodes', {season: ${s.season_number}})">
                Сезон ${s.season_number}${badge}
            </button>`;
        });
        epNav.innerHTML = html + '</div>';
    } catch(e) { 
        epNav.innerHTML = '<div class="empty">Ошибка загрузки данных</div>'; 
    }
};

window.App.renderEpisodes = function(seasonNum) {
    const epNav = document.getElementById('rate-episodes-nav');
    const season = this.rateData.episodesData.find(s => s.season_number === seasonNum);
    let html = '<div class="rating-grid-wa" style="grid-template-columns: repeat(4, 1fr);">';
    season.episodes.forEach(e => {
        const isActive = e.rating ? 'active' : '';
        const label = e.rating ? `<span style="font-weight:900;">★ ${e.rating}</span>` : `E${e.episode_number}`;
        html += `<button class="rating-grid-btn ${isActive}" onclick="window.App.setRateLevel('score', {season: ${seasonNum}, episode: ${e.episode_number}, rating: ${e.rating}})">${label}</button>`;
    });
    epNav.innerHTML = html + '</div>';
};

window.App.submitRatingFromSlider = function() {
    this.submitRating(this.rateData.currentVal);
};

window.App.submitRating = async function(rating) {
    const btn = document.getElementById('btn-submit-rating');
    const origText = btn.textContent;
    btn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px;border-top-color:#fff;margin:0;"></div>';
    btn.disabled = true;
    
    try {
        await fetch('/api/webapp/rate/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                init_data: tg?.initData || '',
                show_id: this.rateData.showId,
                rating: rating,
                season: this.rateData.season,
                episode: this.rateData.episode
            })
        });
        
        showToast('Оценка сохранена');
        window.AppData.cache.clear();
        this.rateData.needsRefresh = true;
        
        if (this.rateData.episode) {
            this.setRateLevel('seasons');
        } else {
            this.closeRateModal();
        }
    } catch(e) { showToast('Ошибка'); } finally {
        btn.textContent = origText;
        btn.disabled = false;
    }
};

window.App.deleteRating = async function() {
    if (!confirm('Удалить оценку?')) return;
    try {
        await fetch('/api/webapp/delete_rating/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                init_data: tg?.initData || '',
                show_id: this.rateData.showId,
                season: this.rateData.season,
                episode: this.rateData.episode
            })
        });
        showToast('Оценка удалена');
        window.AppData.cache.clear();
        this.rateData.needsRefresh = true;
        if (this.rateData.episode) this.setRateLevel('seasons');
        else this.closeRateModal();
    } catch(e) {}
};

window.App.rateGoBack = function() {
    if (this.rateData.level === 'score') this.setRateLevel('episodes', {season: this.rateData.season});
    else if (this.rateData.level === 'episodes') this.setRateLevel('seasons');
    else if (this.rateData.level === 'seasons') this.setRateLevel('show');
};

window.App.closeRateModal = function() {
    document.getElementById('rate-show-modal').classList.remove('show');
    if (this.rateData.needsRefresh) {
        if (activeMainView === 'stats') load(curYear);
        window.App.openShowLayer(this.rateData.showId);
    }
};