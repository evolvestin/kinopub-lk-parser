/**
 * КЛАСС УПРАВЛЕНИЯ СОСТОЯНИЕМ (STATE ENGINE)
 * Только логика данных и уведомлений
 */
class StateManager {
    constructor(defaultState) {
        this.listeners = new Map();
        this.defaultState = defaultState;
        this.state = this._deepClone(defaultState);
        this.saveSessionDebounced = this._debounce(() => this._saveToSession(), 300);
        this._loadFromSession();
    }

    getState(path) {
        if (!path) return this.state;
        return path.split('.').reduce((acc, part) => acc && acc[part], this.state);
    }

    setState(path, valueOrFn) {
        const keys = path.split('.');
        const lastKey = keys.pop();
        const target = keys.reduce((acc, part) => {
            if (!acc[part]) acc[part] = {};
            return acc[part];
        }, this.state);

        const oldValue = target[lastKey];
        const newValue = typeof valueOrFn === 'function' ? valueOrFn(oldValue) : valueOrFn;

        if (JSON.stringify(oldValue) !== JSON.stringify(newValue)) {
            target[lastKey] = newValue;
            this._emit(path, newValue);
            this.saveSessionDebounced();
        }
    }

    subscribe(path, callback) {
        if (!this.listeners.has(path)) this.listeners.set(path, []);
        this.listeners.get(path).push(callback);
        callback(this.getState(path));
        return () => {
            const filtered = this.listeners.get(path).filter(cb => cb !== callback);
            this.listeners.set(path, filtered);
        };
    }

    syncAllBindings() {
        document.querySelectorAll('[data-state-bind]').forEach(el => {
            this._updateElementValue(el, this.getState(el.getAttribute('data-state-bind')));
        });
    }

    _emit(path, value) {
        if (this.listeners.has(path)) {
            this.listeners.get(path).forEach(cb => cb(value));
        }
        const parts = path.split('.');
        if (parts.length > 1) {
            for (let i = 1; i < parts.length; i++) {
                const parentPath = parts.slice(0, -i).join('.') + '.*';
                if (this.listeners.has(parentPath)) {
                    this.listeners.get(parentPath).forEach(cb => cb(this.getState(parts.slice(0, -i).join('.'))));
                }
            }
        }
    }

    _updateElementValue(el, val) {
        if (val === undefined || val === null) return;
        if (el.type === 'checkbox') el.checked = !!val;
        else if (el.type === 'radio') el.checked = (el.value === String(val));
        else if (el.value !== String(val)) el.value = val;
    }

    _saveToSession() {
        try {
            sessionStorage.setItem('app_state_v1', JSON.stringify(this.state));
        } catch (e) { console.warn('State save failed', e); }
    }

    _loadFromSession() {
        try {
            const saved = sessionStorage.getItem('app_state_v1');
            if (saved) {
                const parsed = JSON.parse(saved);
                this.state = this._mergeDeep(this._deepClone(this.defaultState), parsed);
            }
        } catch (e) { this.state = this._deepClone(this.defaultState); }
    }

    _mergeDeep(target, source) {
        for (const key in source) {
            if (source[key] instanceof Object && key in target) {
                Object.assign(source[key], this._mergeDeep(target[key], source[key]));
            }
        }
        return { ...target, ...source };
    }

    _deepClone(obj) { return JSON.parse(JSON.stringify(obj)); }
    _debounce(func, wait) {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => func(...args), wait);
        };
    }
}

/**
 * КОНФИГУРАЦИЯ И ИНИЦИАЛИЗАЦИЯ
 */

const DEFAULT_APP_STATE = {
    ui: {
        isLoading: true,
        isAppReady: false,
        activeStatsTab: 'personal',
        personTabs: {
            actors: 'series',
            directors: 'series',
            writers: 'series'
        },
        theme: 'dark',
        viewMode: 'grid',
        wlViewMode: 'grid',
        sortMode: 'default',
        isSortMenuOpen: false,
        scrollPositions: {},
        toast: { text: '', type: 'info', visible: false },
        helpPopoverVisible: false, // Новый флаг для подсказки в вишлисте
        bottomNavVisible: true,    // Управление видимостью меню
        shareBtnVisible: true      // Управление видимостью кнопки шаринга
    },
    flags: {
        isReorderMode: false,
        isItemsReorderMode: false,
        isHistoryEditMode: false,
        isSyncingHash: false,
        isSharedMode: false
    },
    nav: {
        activeMainView: 'search',
        query: { y: 'all', folderId: null },
        layerStack: []
    },
    data: {
        stats: null, 
        availableYears: [],
        wishlistFolders: [],
        activeWlFolderId: null,
        search: {
            results: null
        },
        history: {
            list: [],
            type: '',
            title: '',
            offset: 0,
            batchSize: 80,
            grouping: 'none',
            lastGroupKey: null,
            isRendering: false
        }
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
        wlEdit: {
            name: '',
            color: '#388bfd',
            icon: 'folder'
        }
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
    }
};

// Создаем экземпляр
const stateInstance = new StateManager(DEFAULT_APP_STATE);

/**
 * РЕАКТИВНЫЕ ЭФФЕКТЫ (UI BINDINGS)
 * Здесь описываем, как DOM реагирует на изменения в State
 */
function initUIEffects(App) {
    App.subscribe('ui.isLoading', (loading) => {
        const loader = document.getElementById('loader');
        if (!loader) return;
        if (loading) {
            loader.classList.remove('hidden');
            loader.style.opacity = '1';
        } else {
            loader.style.opacity = '0';
            setTimeout(() => {
                if (!App.getState('ui.isLoading')) loader.classList.add('hidden');
            }, 400);
        }
    });

    // Новое: управление видимостью всего приложения
    App.subscribe('ui.isAppReady', (ready) => {
        const appEl = document.getElementById('app');
        if (appEl && ready) {
            appEl.classList.remove('hidden');
        }
    });

    App.subscribe('ui.toast', (toast) => {
        let el = document.getElementById('toast-msg');
        if (!el) {
            el = document.createElement('div');
            el.id = 'toast-msg';
            el.className = 'toast';
            document.body.appendChild(el);
        }
        if (toast.visible) {
            el.textContent = toast.text;
            el.classList.add('show');
            if (App._toastTimer) clearTimeout(App._toastTimer);
            App._toastTimer = setTimeout(() => {
                App.setState('ui.toast.visible', false);
            }, 2500);
        } else {
            el.classList.remove('show');
        }
    });

    App.subscribe('ui.theme', (val) => {
        document.body.classList.toggle('light', val === 'light');
        document.querySelectorAll('.js-theme-toggle').forEach(btn => {
            if (window.App.Icons) {
                btn.innerHTML = val === 'dark' ? window.App.Icons.moon : window.App.Icons.sun;
            }
        });
    });

    const MODAL_MAP = {
        'addView': 'add-view-modal',
        'rateShow': 'rate-show-modal',
        'share': 'share-modal',
        'wlFolder': 'wl-modal',
        'wlEdit': 'wl-edit-modal',
        'wlLimit': 'wl-limit-modal',
        'wlDelete': 'wl-item-delete-modal',
        'casino': 'casino-modal',
        'details': 'details-modal'
    };

    Object.entries(MODAL_MAP).forEach(([stateKey, elId]) => {
        App.subscribe(`modals.${stateKey}.isOpen`, (isOpen) => {
            const el = document.getElementById(elId);
            if (!el) return;
            
            if (isOpen) {
                el.classList.add('show');
                document.body.style.overflow = 'hidden';
            } else {
                el.classList.remove('show');
                const anyOpen = Object.keys(MODAL_MAP).some(key => App.getState(`modals.${key}.isOpen`));
                if (!anyOpen) document.body.style.overflow = '';
            }
        });
    });

    App.subscribe('ui.activeStatsTab', val => {
        if (typeof window.App.mainTab === 'function') {
            window.App.mainTab(val, true);
        }
    });

    const syncInput = (path) => {
        document.querySelectorAll(`[data-state-bind="${path}"]`).forEach(el => {
            stateInstance._updateElementValue(el, stateInstance.getState(path));
        });
    };

    ['forms.search.query', 'ui.theme', 'flags.isReorderMode'].forEach(path => {
        App.subscribe(path, () => syncInput(path));
    });

    App.subscribe('modals.addView.context', (ctx) => {
        if (!ctx) return;
        const titleEl = document.getElementById('add-view-title');
        if (titleEl) titleEl.textContent = ctx.title || '';
        const seContainer = document.getElementById('add-view-se-container');
        if (seContainer) {
            const isSeries = ['Series', 'Documentary Series', 'TV Show'].includes(ctx.type);
            seContainer.style.display = isSeries ? 'flex' : 'none';
        }
    });

    App.subscribe('flags.isReorderMode', val => {
        const grid = document.getElementById('wl-folders-grid');
        if (grid) grid.classList.toggle('reorder-mode', val);
    });

    App.subscribe('flags.isItemsReorderMode', val => {
        const container = document.getElementById('wl-items-container');
        if (container) container.classList.toggle('reorder-items-mode', val);
    });

    App.subscribe('ui.helpPopoverVisible', (visible) => {
        const informer = document.getElementById('wl-stats-informer');
        if (informer) informer.classList.toggle('show', visible);
    });

    App.subscribe('ui.bottomNavVisible', (visible) => {
        const bn = document.getElementById('bottom-nav');
        if (bn) bn.style.display = visible ? 'flex' : 'none';
    });

    App.subscribe('ui.shareBtnVisible', (visible) => {
        const btn = document.getElementById('share-btn');
        if (btn) btn.classList.toggle('hidden', !visible);
    });

    // Реакция на изменение стека слоев для управления Bottom Nav
    App.subscribe('nav.layerStack', (stack) => {
        const isShared = App.getState('flags.isSharedMode');
        // Если слоев нет и мы не в режиме шаринга — показываем навигацию
        App.setState('ui.bottomNavVisible', stack.length === 0 && !isShared);
    });

    // Реакция на режим шаринга для кнопки Share
    App.subscribe('flags.isSharedMode', (isShared) => {
        App.setState('ui.shareBtnVisible', !isShared);
        // Также обновляем навигацию, если флаг изменился внезапно
        const stack = App.getState('nav.layerStack');
        App.setState('ui.bottomNavVisible', stack.length === 0 && !isShared);
    });

    App.subscribe('data.stats', (d) => {
        if (!d) return;
        
        // 1. Мета-данные и Счетчики
        if (typeof window.App.updateUserMeta === 'function') window.App.updateUserMeta(d.meta);
        if (typeof window.App.updateOverview === 'function') window.App.updateOverview(d.summary);
        if (typeof window.App.updateRatingsSection === 'function') window.App.updateRatingsSection(d.ratings);
        
        // 2. Списки (Actors, Directors, Writers, Countries, Binges)
        const categories = ['actors', 'directors', 'writers'];
        categories.forEach(cat => {
            const mode = App.getState(`ui.personTabs.${cat}`) || 'series';
            const listId = `${cat}-list`;
            if (d[cat] && d[cat][mode]) {
                window.App.fillList(listId, d[cat][mode], null, ['просмотр', 'просмотра', 'просмотров'], cat, mode);
            }
        });

        if (d.countries) window.App.fillList('countries-list', d.countries, window.App.Icons.globe, ['просмотр', 'просмотра', 'просмотров'], 'countries');
        if (d.binges) window.App.fillBinges(d.binges);

        // 3. Графики
        if (typeof window.App.renderCharts === 'function') window.App.renderCharts(d);
        
        // 4. Групповая статистика
        if (App.getState('ui.activeStatsTab') === 'group' && typeof window.App.renderGroup === 'function') {
            window.App.renderGroup(d);
        }
    });

    // Подписка на переключение табов людей (сериалы/фильмы)
    ['actors', 'directors', 'writers'].forEach(cat => {
        App.subscribe(`ui.personTabs.${cat}`, (mode) => {
            const d = App.getState('data.stats');
            if (d && d[cat] && d[cat][mode]) {
                window.App.fillList(`${cat}-list`, d[cat][mode], null, ['просмотр', 'просмотра', 'просмотров'], cat, mode);
            }
        });
    });

    // Подписка на активную вкладку статистики (Личная/Группа)
    App.subscribe('ui.activeStatsTab', (tab) => {
        document.querySelectorAll('.tab[data-tab]').forEach(el => {
            el.classList.toggle('on', el.dataset.tab === tab);
        });
        document.getElementById('sec-personal')?.classList.toggle('hidden', tab !== 'personal');
        document.getElementById('sec-group')?.classList.toggle('hidden', tab !== 'group');
        
        const d = App.getState('data.stats');
        if (tab === 'group' && d) window.App.renderGroup(d);
    });

    // Подписка на режим отображения истории (Сетка/Список)
    App.subscribe('ui.viewMode', (mode) => {
        const top = window.App.viewStack[window.App.viewStack.length - 1];
        if (top && top.context.type === 'history') {
            const container = top.el.querySelector('#layer-hist-container');
            if (container) container.innerHTML = '';
            App.setState('data.history.offset', 0);
            App.setState('data.history.lastGroupKey', null);
            window.App.renderHistoryBatchLayer();
        }
        localStorage.setItem('kp_view_mode', mode);
    });
}

/**
 * ГЛОБАЛЬНЫЙ ОБЪЕКТ ПРИЛОЖЕНИЯ
 */
window.App = window.App || {};
Object.assign(window.App, {
    State: stateInstance,
    getState: (p) => stateInstance.getState(p),
    setState: (p, v) => stateInstance.setState(p, v),
    subscribe: (p, c) => stateInstance.subscribe(p, c)
});

/**
 * ОБРАБОТЧИКИ СОБЫТИЙ (DOM -> STATE)
 */
document.addEventListener('DOMContentLoaded', () => {
    initUIEffects(window.App);
    stateInstance.syncAllBindings();

    // Слушаем изменения во всех инпутах с привязкой
    document.addEventListener('input', (e) => {
        const path = e.target.getAttribute('data-state-bind');
        if (!path) return;

        let value;
        if (e.target.type === 'checkbox') value = e.target.checked;
        else if (e.target.type === 'number') value = parseFloat(e.target.value);
        else value = e.target.value;

        window.App.setState(path, value);
    });

    // Специальная обработка для селектов/дат
    document.addEventListener('change', (e) => {
        const path = e.target.getAttribute('data-state-bind');
        if (path && (e.target.tagName === 'SELECT' || e.target.type === 'date')) {
            window.App.setState(path, e.target.value);
        }
    });
});
