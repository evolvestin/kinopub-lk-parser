window.App = window.App || {};

class StateManager {
    constructor() {
        this.listeners = {};
        this.saveSessionDebounced = this._debounce(() => this.saveSessionState(), 300);

        this.defaultState = {
            ui: {
                activeStatsTab: 'personal',
                theme: 'dark',
                viewMode: 'grid',
                sortMode: 'default',
                scrollPositions: {}
            },
            flags: {
                isReorderMode: false,
                isItemsReorderMode: false,
                isHistoryEditMode: false,
                isSyncingHash: false
            },
            nav: {
                activeMainView: 'search',
                query: { y: 'all', folderId: null },
                layerStack: [] 
            },
            modals: {
                addView: { isOpen: false, context: {} },
                rateShow: { isOpen: false, context: {} },
                share: { isOpen: false, context: {} },
                wlFolder: { isOpen: false, context: {} },
                wlEdit: { isOpen: false, context: {} },
                wlLimit: { isOpen: false, context: {} },
                wlDelete: { isOpen: false, context: {} },
                casino: { isOpen: false, context: {} },
                details: { isOpen: false, context: {} }
            },
            forms: {
                search: { query: '' },
                addView: { 
                    season: '', 
                    episode: '', 
                    dateMode: 'exact', 
                    exact: '', 
                    month: '', 
                    year: '' 
                },
                wlEdit: { name: '', color: '', icon: '' }
            }
        };

        this.state = this._deepClone(this.defaultState);
        this.loadSessionState();
        
        // Реактивные подписки для синхронизации состояния с DOM
        this.initGlobalListeners();
    }

    initGlobalListeners() {
        // Синхронизация вкладок статистики (Личная / Группа)
        this.subscribe('ui.activeStatsTab', (val) => {
            if (typeof window.App.mainTab === 'function') {
                window.App.mainTab(val, true);
            }
        });

        // Режим переупорядочивания папок
        this.subscribe('flags.isReorderMode', (val) => {
            const grid = document.getElementById('wl-folders-grid');
            const view = document.getElementById('view-wishlist');
            if (grid) grid.classList.toggle('reorder-mode', val);
            if (view) view.classList.toggle('reorder-active-state', val);
        });

        // Режим переупорядочивания элементов внутри папки
        this.subscribe('flags.isItemsReorderMode', (val) => {
            const container = document.getElementById('wl-items-container');
            if (container) container.classList.toggle('reorder-items-mode', val);
        });

        // Режим удаления истории
        this.subscribe('flags.isHistoryEditMode', (val) => {
            const container = document.getElementById('layer-hist-container');
            if (container) container.classList.toggle('history-edit-mode', val);
        });

        // Синхронизация темы (Dark/Light)
        this.subscribe('ui.theme', (val) => {
            document.body.classList.toggle('light', val === 'light');
            document.querySelectorAll('.js-theme-toggle').forEach(btn => {
                if (window.Icons) {
                    btn.innerHTML = val === 'dark' ? Icons.moon : Icons.sun;
                }
            });
        });
    }

    getState(path) {
        return path.split('.').reduce((acc, part) => acc && acc[part], this.state);
    }

    setState(path, value) {
        const keys = path.split('.');
        const lastKey = keys.pop();
        const target = keys.reduce((acc, part) => {
            if (acc[part] === undefined) acc[part] = {};
            return acc[part];
        }, this.state);

        if (JSON.stringify(target[lastKey]) !== JSON.stringify(value)) {
            target[lastKey] = value;
            this.emit(path, value);
            this.saveSessionDebounced();
        }
    }

    subscribe(path, callback) {
        if (!this.listeners[path]) this.listeners[path] = [];
        this.listeners[path].push(callback);
    }

    emit(path, value) {
        if (this.listeners[path]) {
            this.listeners[path].forEach(cb => cb(value));
        }
        
        const parts = path.split('.');
        let currentPath = '';
        for (let i = 0; i < parts.length - 1; i++) {
            currentPath += (i === 0 ? '' : '.') + parts[i];
            const wildcardPath = `${currentPath}.*`;
            if (this.listeners[wildcardPath]) {
                this.listeners[wildcardPath].forEach(cb => cb(this.getState(currentPath)));
            }
        }
    }

    applyStateToDOM() {
        document.querySelectorAll('[data-state-bind]').forEach(el => {
            const path = el.getAttribute('data-state-bind');
            const val = this.getState(path);
            if (val !== undefined && val !== null) {
                if (el.type === 'checkbox') el.checked = !!val;
                else if (el.type === 'radio') { 
                    if (el.value === String(val)) el.checked = true; 
                }
                else el.value = val;
            }
        });
        
        // Принудительный вызов слушателей для актуализации классов
        this.emit('ui.theme', this.getState('ui.theme'));
        this.emit('flags.isReorderMode', this.getState('flags.isReorderMode'));
        this.emit('flags.isItemsReorderMode', this.getState('flags.isItemsReorderMode'));
        this.emit('ui.activeStatsTab', this.getState('ui.activeStatsTab'));
    }

    saveSessionState() {
        try {
            sessionStorage.setItem('kp_app_state', JSON.stringify(this.state));
        } catch (e) {}
    }

    loadSessionState() {
        try {
            const saved = sessionStorage.getItem('kp_app_state');
            if (saved) {
                const parsed = JSON.parse(saved);
                this.state = this._mergeObjects(this._deepClone(this.defaultState), parsed);
            }
        } catch (e) {}
    }

    _mergeObjects(target, source) {
        for (const key of Object.keys(source)) {
            if (source[key] instanceof Object && key in target && !Array.isArray(source[key])) {
                this._mergeObjects(target[key], source[key]);
            } else {
                target[key] = source[key];
            }
        }
        return target;
    }

    _deepClone(obj) {
        return JSON.parse(JSON.stringify(obj));
    }

    _debounce(func, wait) {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => func(...args), wait);
        };
    }
}

window.App.State = new StateManager();

document.addEventListener('input', (e) => {
    const bindPath = e.target.getAttribute('data-state-bind');
    if (bindPath) {
        const val = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
        window.App.State.setState(bindPath, val);
    }
});
document.addEventListener('change', (e) => {
    const bindPath = e.target.getAttribute('data-state-bind');
    if (bindPath && (e.target.type === 'date' || e.target.type === 'month')) {
        window.App.State.setState(bindPath, e.target.value);
    }
});