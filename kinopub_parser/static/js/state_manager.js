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

    // --- ПУБЛИЧНЫЕ МЕТОДЫ ---

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
        const newValue = typeof valueOrFn === 'function' 
            ? valueOrFn(oldValue) 
            : valueOrFn;

        // Обновляем только если значение реально изменилось
        if (oldValue !== newValue) {
            target[lastKey] = newValue;
            this._emit(path, newValue);
            this.saveSessionDebounced();
        }
    }

    /**
     * Подписка на изменение пути
     * @returns {Function} Функция для отписки
     */
    subscribe(path, callback) {
        if (!this.listeners.has(path)) this.listeners.set(path, []);
        this.listeners.get(path).push(callback);
        
        // Сразу вызываем колбэк с текущим значением (начальная синхронизация)
        callback(this.getState(path));

        return () => {
            const filtered = this.listeners.get(path).filter(cb => cb !== callback);
            this.listeners.set(path, filtered);
        };
    }

    /**
     * Принудительная синхронизация всех элементов с data-state-bind
     */
    syncAllBindings() {
        document.querySelectorAll('[data-state-bind]').forEach(el => {
            const path = el.getAttribute('data-state-bind');
            this._updateElementValue(el, this.getState(path));
        });
    }

    // --- ПРИВАТНЫЕ МЕТОДЫ ---

    _emit(path, value) {
        if (this.listeners.has(path)) {
            this.listeners.get(path).forEach(cb => cb(value));
        }

        const parts = path.split('.');
        if (parts.length > 1) {
            // Идем вверх по дереву и уведомляем всех слушателей wildcard
            // Пример: если изменилось 'modals.rateShow.isOpen', 
            // уведомим 'modals.rateShow.*' и 'modals.*'
            for (let i = 1; i < parts.length; i++) {
                const parentPath = parts.slice(0, -i).join('.') + '.*';
                if (this.listeners.has(parentPath)) {
                    const subState = this.getState(parts.slice(0, -i).join('.'));
                    this.listeners.get(parentPath).forEach(cb => cb(subState));
                }
            }
        }
    }

    _updateElementValue(el, val) {
        if (val === undefined || val === null) return;
        
        if (el.type === 'checkbox') {
            el.checked = !!val;
        } else if (el.type === 'radio') {
            el.checked = (el.value === String(val));
        } else {
            if (el.value !== String(val)) el.value = val;
        }
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

/**
 * КОНФИГУРАЦИЯ И ИНИЦИАЛИЗАЦИЯ
 */

const DEFAULT_APP_STATE = {
    ui: {
        isLoading: true, // Добавлено состояние загрузки
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
    data: {
        wishlistFolders: [],
        activeWlFolderId: null
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
    // Эффект лоадера и видимости приложения
    App.subscribe('ui.isLoading', (loading) => {
        const loader = document.getElementById('loader');
        const app = document.getElementById('app');

        if (loading) {
            if (loader) {
                loader.classList.remove('hidden');
                loader.style.opacity = '1';
            }
        } else {
            if (loader) {
                loader.style.opacity = '0';
                setTimeout(() => {
                    if (!App.getState('ui.isLoading')) {
                        loader.classList.add('hidden');
                    }
                }, 400);
            }
            // Главное исправление: показываем приложение, когда загрузка завершена
            if (app) {
                app.classList.remove('hidden');
            }
        }
    });

    // Тема
    App.subscribe('ui.theme', (val) => {
        document.body.classList.toggle('light', val === 'light');
        document.querySelectorAll('.js-theme-toggle').forEach(btn => {
            if (window.App.Icons) {
                btn.innerHTML = val === 'dark' ? window.App.Icons.moon : window.App.Icons.sun;
            }
        });
    });

    // Режимы редактирования
    App.subscribe('flags.isReorderMode', val => {
        const grid = document.getElementById('wl-folders-grid');
        if (grid) grid.classList.toggle('reorder-mode', val);
    });

    App.subscribe('flags.isItemsReorderMode', val => {
        const container = document.getElementById('wl-items-container');
        if (container) container.classList.toggle('reorder-items-mode', val);
    });

    // Вкладки статистики
    App.subscribe('ui.activeStatsTab', val => {
        if (typeof window.App.mainTab === 'function') {
            window.App.mainTab(val, true);
        }
    });

    // Автоматическая синхронизация всех data-state-bind элементов (входящая)
    // Мы подписываемся на "изменение чего угодно", чтобы обновить инпуты
    // В продакшене лучше подписаться на конкретные ветки для перфоманса
    const syncInput = (path) => {
        document.querySelectorAll(`[data-state-bind="${path}"]`).forEach(el => {
            stateInstance._updateElementValue(el, stateInstance.getState(path));
        });
    };

    // Регистрируем базовые пути для авто-синхронизации инпутов
    ['forms.search.query', 'ui.theme', 'flags.isReorderMode'].forEach(path => {
        App.subscribe(path, () => syncInput(path));
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
