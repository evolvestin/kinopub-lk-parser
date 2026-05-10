window.App = window.App || {};

class StateManager {
    constructor() {
        this.listeners = {};
        this.saveSessionDebounced = this._debounce(() => this.saveSessionState(), 300);

        this.defaultState = {
            ui: {
                activeTabs: {},
                scrollPositions: {},
                theme: 'dark',
                viewMode: 'grid',
                sortMode: 'default'
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
                addView: { season: '', episode: '', dateMode: 'exact', exact: '', month: '', year: '' },
                wlEdit: { name: '', color: '', icon: '' }
            },
            flags: {
                isReorderMode: false,
                isItemsReorderMode: false,
                isHistoryEditMode: false,
                isSyncingHash: false
            },
            nav: {
                activeMainView: 'search',
                query: { y: 'all', folderId: null }
            }
        };

        this.state = this._mergeObjects({}, this.defaultState);
        this.loadSessionState();
        this.loadPersistentState();
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

        if (target[lastKey] !== value) {
            target[lastKey] = value;
            this.emit(path, value);
            this.saveSessionDebounced();
            this._checkAndSavePersistent(path, value);
        }
    }

    applyStateToDOM() {
        document.querySelectorAll('[data-state-bind]').forEach(el => {
            const path = el.getAttribute('data-state-bind');
            const val = this.getState(path);
            if (val !== undefined && val !== null) {
                if (el.type === 'checkbox') el.checked = !!val;
                else el.value = val;
            }
        });
    }

    subscribe(path, callback) {
        if (!this.listeners[path]) {
            this.listeners[path] = [];
        }
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
            if (this.listeners[`${currentPath}.*`]) {
                this.listeners[`${currentPath}.*`].forEach(cb => cb(this.getState(currentPath)));
            }
        }
    }

    loadSessionState() {
        try {
            const saved = sessionStorage.getItem('kp_app_state');
            if (saved) {
                const parsed = JSON.parse(saved);
                this.state.forms = this._mergeObjects(this.state.forms, parsed.forms || {});
                this.state.ui.scrollPositions = parsed.ui?.scrollPositions || {};
                if (parsed.nav) {
                    this.state.nav.query = this._mergeObjects(this.state.nav.query, parsed.nav.query || {});
                }
            }
        } catch (e) {}
    }

    saveSessionState() {
        try {
            const toSave = {
                forms: this.state.forms,
                ui: { scrollPositions: this.state.ui.scrollPositions },
                nav: { query: this.state.nav.query }
            };
            sessionStorage.setItem('kp_app_state', JSON.stringify(toSave));
        } catch (e) {}
    }

    loadPersistentState() {
        const theme = localStorage.getItem('kt') === 'l' ? 'light' : 'dark';
        this.setState('ui.theme', theme);

        const viewMode = localStorage.getItem('kp_view_mode') || 'grid';
        this.setState('ui.viewMode', viewMode);

        const sortMode = localStorage.getItem('wl_sort_mode') || 'default';
        this.setState('ui.sortMode', sortMode);
    }

    _checkAndSavePersistent(path, value) {
        if (path === 'ui.theme') {
            localStorage.setItem('kt', value === 'light' ? 'l' : 'd');
        } else if (path === 'ui.viewMode') {
            localStorage.setItem('kp_view_mode', value);
        } else if (path === 'ui.sortMode') {
            localStorage.setItem('wl_sort_mode', value);
        }
    }

    _mergeObjects(target, source) {
        for (const key of Object.keys(source)) {
            if (source[key] instanceof Object && key in target && !Array.isArray(source[key])) {
                Object.assign(target[key], this._mergeObjects(target[key], source[key]));
            } else {
                target[key] = source[key];
            }
        }
        return target;
    }

    _debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
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