window.App = window.App || {};

window.App.rateData = {
    showId: null,
    showType: null,
    level: 'show', 
    season: null,
    episode: null,
    title: '',
    episodesData: [],
    currentShowRating: null
};

window.App.openRateModal = function(showId, title, currentRating, type = null) {
    this.rateData = {
        showId: showId,
        showType: type || 'Movie',
        level: 'show',
        season: null,
        episode: null,
        title: title,
        currentShowRating: currentRating,
        episodesData: [],
        needsRefresh: false
    };

    if (!type) {
        const show = D?.history_movies?.find(s => s.show_id === showId) || 
                     D?.history_episodes?.find(s => s.show_id === showId);
        
        if (show) this.rateData.showType = show.show__type || 'Movie';
    }
    
    const isSeries = ['Series', 'Documentary Series', 'TV Show'].includes(this.rateData.showType);
    document.getElementById('rate-mode-toggle').style.display = isSeries ? 'flex' : 'none';
    document.getElementById('rate-show-title').textContent = title;
    
    this.setRateLevel('show');
    document.getElementById('rate-show-modal').classList.add('show');
};

window.App.setRateLevel = function(level, params = {}) {
    this.rateData.level = level;
    const grid = document.getElementById('rate-show-grid');
    const epNav = document.getElementById('rate-episodes-nav');
    const backBtn = document.getElementById('rate-back-btn');
    const breadcrumb = document.getElementById('rate-breadcrumb');
    const modeToggle = document.getElementById('rate-mode-toggle');
    const delBtn = document.getElementById('btn-delete-rating');

    grid.style.display = 'none';
    epNav.style.display = 'none';
    backBtn.style.display = 'none';
    delBtn.style.display = 'none';

    if (level === 'show') {
        breadcrumb.textContent = 'Общая оценка проекта';
        modeToggle.querySelector('#rate-mode-main').classList.add('active');
        modeToggle.querySelector('#rate-mode-ep').classList.remove('active');
        this.renderScoreGrid(this.rateData.currentShowRating);
    } 
    else if (level === 'seasons') {
        breadcrumb.textContent = 'Выбор сезона';
        backBtn.style.display = 'block';
        modeToggle.querySelector('#rate-mode-main').classList.remove('active');
        modeToggle.querySelector('#rate-mode-ep').classList.add('active');
        this.loadAndRenderSeasons();
    }
    else if (level === 'episodes') {
        this.rateData.season = params.season;
        breadcrumb.textContent = `Сезон ${params.season}`;
        backBtn.style.display = 'block';
        this.renderEpisodes(params.season);
    }
    else if (level === 'score') {
        this.rateData.season = params.season;
        this.rateData.episode = params.episode;
        breadcrumb.textContent = `S${params.season} E${params.episode}`;
        backBtn.style.display = 'block';
        this.renderScoreGrid(params.rating);
    }
};

window.App.renderScoreGrid = function(activeValue) {
    const grid = document.getElementById('rate-show-grid');
    const delBtn = document.getElementById('btn-delete-rating');
    grid.style.display = 'grid';
    
    const isValidValue = (activeValue !== null && activeValue !== undefined && activeValue !== 'null');
    const currentVal = isValidValue ? parseFloat(activeValue) : null;
    
    if (isValidValue) {
        delBtn.style.display = 'block';
        delBtn.innerHTML = 'Удалить';
        delBtn.disabled = false;
    }

    let html = '';
    for (let i = 2; i <= 20; i++) {
        const val = i / 2;
        const label = Number.isInteger(val) ? val.toString() : val.toFixed(1);
        const isActive = (currentVal !== null && Math.abs(val - currentVal) < 0.01) ? 'active' : '';
        html += `<button class="rating-grid-btn ${isActive}" onclick="window.App.submitRating(${val}, event)">${label}</button>`;
    }
    grid.innerHTML = html;
};

window.App.loadAndRenderSeasons = async function() {
    const epNav = document.getElementById('rate-episodes-nav');
    epNav.style.display = 'block';
    epNav.innerHTML = '<div class="loader-inline"><div class="spinner"></div></div>';

    try {
        const r = await fetch('/api/webapp/get_episodes/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ show_id: this.rateData.showId, init_data: tg?.initData || '' })
        });
        const data = await r.json();
        this.rateData.episodesData = data.seasons;

        let html = '<div class="rating-grid-wa" style="grid-template-columns: repeat(3, 1fr);">';
        data.seasons.forEach(s => {
            const ratedCount = s.episodes.filter(e => e.rating).length;
            const badge = ratedCount ? `<span style="font-size:10px; opacity:0.8; display:block; color:var(--accent);">★ ${ratedCount}/${s.episodes.length}</span>` : `<span style="font-size:10px; opacity:0.5; display:block;">0/${s.episodes.length}</span>`;
            html += `<button class="rating-grid-btn" style="height:auto; padding:10px 0;" onclick="window.App.setRateLevel('episodes', {season: ${s.season_number}})">
                Сезон ${s.season_number}${badge}
            </button>`;
        });
        html += '</div>';
        epNav.innerHTML = html;
    } catch(e) {
        epNav.innerHTML = '<div class="empty">Ошибка загрузки серий</div>';
    }
};

window.App.renderEpisodes = function(seasonNum) {
    const epNav = document.getElementById('rate-episodes-nav');
    epNav.style.display = 'block';
    const season = this.rateData.episodesData.find(s => s.season_number === seasonNum);
    
    let html = '<div class="rating-grid-wa" style="grid-template-columns: repeat(4, 1fr);">';
    season.episodes.forEach(e => {
        const isActive = e.rating ? 'active' : '';
        const label = e.rating ? `<span style="font-size:11px; display:block; color:inherit; font-weight:900;">★ ${e.rating}</span>` : `E${e.episode_number}`;
        html += `<button class="rating-grid-btn ${isActive}" onclick="window.App.setRateLevel('score', {season: ${seasonNum}, episode: ${e.episode_number}, rating: ${e.rating}})">
            ${label}
        </button>`;
    });
    html += '</div>';
    epNav.innerHTML = html;
};

window.App.rateGoBack = function() {
    if (this.rateData.level === 'score') this.setRateLevel('episodes', {season: this.rateData.season});
    else if (this.rateData.level === 'episodes') this.setRateLevel('seasons');
    else if (this.rateData.level === 'seasons') this.setRateLevel('show');
};

window.App.closeRateModal = function() {
    document.getElementById('rate-show-modal').classList.remove('show');
    if (this.rateData && this.rateData.needsRefresh) {
        window.App.openShowLayer(this.rateData.showId);
    }
};

window.App.submitRating = async function(rating, event) {
    const btn = event.currentTarget;
    const origContent = btn.innerHTML;
    btn.innerHTML = '<div class="spinner" style="width:14px;height:14px;border-width:2px;margin:0;"></div>';
    
    try {
        const r = await fetch('/api/webapp/rate/', {
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
        if (!r.ok) throw new Error();
        
        showToast('Оценка сохранена');
        window.AppData.cache.clear();
        this.rateData.needsRefresh = true;
        
        if (this.rateData.episode) {
            const season = this.rateData.episodesData.find(s => s.season_number === this.rateData.season);
            if (season) {
                const ep = season.episodes.find(e => e.episode_number === this.rateData.episode);
                if (ep) ep.rating = rating;
            }
            this.setRateLevel('episodes', {season: this.rateData.season});
        } else {
            this.rateData.currentShowRating = rating;
            this.closeRateModal();
            load(curYear);
            window.App.openShowLayer(this.rateData.showId);
        }
    } catch(e) {
        btn.innerHTML = origContent;
        showToast('Ошибка сохранения');
    }
};

window.App.deleteRating = async function() {
    const msg = this.rateData.episode 
        ? `Удалить оценку эпизода S${this.rateData.season} E${this.rateData.episode}?`
        : 'Удалить общую оценку проекта?';

    if (!confirm(msg)) return;
    
    const btn = document.getElementById('btn-delete-rating');
    const origContent = btn.innerHTML;
    btn.innerHTML = '<div class="spinner" style="width:14px;height:14px;border-width:2px;margin:0;border-top-color:var(--danger);"></div>';
    btn.disabled = true;

    try {
        const r = await fetch('/api/webapp/delete_rating/', {
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

        if (this.rateData.episode) {
            const season = this.rateData.episodesData.find(s => s.season_number === this.rateData.season);
            if (season) {
                const ep = season.episodes.find(e => e.episode_number === this.rateData.episode);
                if (ep) ep.rating = null;
            }
            this.setRateLevel('episodes', {season: this.rateData.season});
        } else {
            this.rateData.currentShowRating = null;
            this.closeRateModal();
            load(curYear);
            window.App.openShowLayer(this.rateData.showId);
        }
    } catch(e) {
        showToast('Ошибка удаления');
        btn.innerHTML = origContent;
        btn.disabled = false;
    }
};