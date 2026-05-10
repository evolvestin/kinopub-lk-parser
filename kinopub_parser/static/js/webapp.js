window.App = window.App || {};

const tg = window.Telegram?.WebApp;

let chR = null;
let D = null, curYear = null, isDark = true;
let chM = null, chW = null, chG = {}, lastScrollPos = 0;

let isSharedMode = false;
let SharedDataMap = {};
let availableYears = [];
let activeMainView = 'search';
let toastTimer = null;

let curHistData = [], curHistType = '';
let currentHistoryOffset = 0;
const historyBatchSize = 80;
let historyObserver = null;
let isRenderingBatch = false;
let viewMode = localStorage.getItem('kp_view_mode') || 'grid';
let isHistoryEditMode = false;
let searchTimer = null;

let viewStack = []; 

let addViewData = {
    showId: null,
    type: null,
    mode: 'exact'
};
const UserAvatarColors = ['#3498db', '#9b59b6', '#f1c40f', '#e67e22', '#e74c3c', '#1abc9c', '#34495e', '#2ecc71'];
const fSizeAx = Math.max(10, Math.min(13, window.innerWidth * 0.03));

Object.assign(window.App, {
    isSyncingHash: false,

    SHOW_TYPE_RU: {
        'Series': 'Сериал',
        'Movie': 'Фильм',
        'Concert': 'Концерт',
        'Documentary Movie': 'Док. фильм',
        'Documentary Series': 'Док. сериал',
        'TV Show': 'ТВ-шоу',
        '3D Movie': '3D фильм',
    },

    SHOW_STATUS_RU: {
        'Finished': 'Завершен',
        'Ongoing': 'В эфире',
        'Filming': 'Съемки',
        'Post Production': 'Постпродакшн',
        'Pre Production': 'Препродакшн',
    },

    RU_MONTHS: [
        'Январь',
        'Февраль',
        'Март',
        'Апрель',
        'Май',
        'Июнь',
        'Июль',
        'Август',
        'Сентябрь',
        'Октябрь',
        'Ноябрь',
        'Декабрь',
    ],

    plural: function(n, forms) {
        let n10 = Math.abs(n) % 10;
        let n100 = Math.abs(n) % 100;
        if (n100 >= 11 && n100 <= 14) return forms[2];
        if (n10 === 1) return forms[0];
        if (n10 >= 2 && n10 <= 4) return forms[1];
        return forms[2];
    },

    getUserColor: function(id) {
        if (id === 0) return 'var(--bg-input)';
        return UserAvatarColors[(id - 1) % UserAvatarColors.length];
    },

    toggleTheme: function() {
        isDark = !isDark;
        document.body.classList.toggle('light', !isDark);
        document.querySelectorAll('.js-theme-toggle').forEach(btn => {
            btn.innerHTML = isDark ? window.App.Icons.moon : window.App.Icons.sun;
        });
        localStorage.setItem('kt', isDark ? 'd' : 'l');
        
        window.App.State.setState('ui.theme', isDark ? 'dark' : 'light');
        
        if (D) this.renderCharts();
    },
    MONTHS: [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ],

    Icons: {
        folder: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>',
        heart: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>',
        clock: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle style="fill:none;" cx="12" cy="12" r="10"></circle><polyline style="fill:none;" points="12 6 12 12 16 14"></polyline></svg>',
        edit: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path style="fill:none;" d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>',
        trash: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline style="fill:none;" points="3 6 5 6 21 6"></polyline><path style="fill:none;" d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>',
        gear: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle style="fill:none;" cx="12" cy="12" r="3"></circle><path style="fill:none;" d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>',
        search: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle style="fill:none;" cx="10.5" cy="10.5" r="7.5"></circle><line style="fill:none;" x1="21" y1="21" x2="15.8" y2="15.8"></line></svg>',
        reorder: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M12 5v14M8 9l4-4 4 4M8 15l4 4 4-4"></path></svg>',
        moon: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>',
        sun: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle style="fill:none;" cx="12" cy="12" r="5"></circle><line style="fill:none;" x1="12" y1="1" x2="12" y2="3"></line><line style="fill:none;" x1="12" y1="21" x2="12" y2="23"></line><line style="fill:none;" x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line style="fill:none;" x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line style="fill:none;" x1="1" y1="12" x2="3" y2="12"></line><line style="fill:none;" x1="21" y1="12" x2="23" y2="12"></line><line style="fill:none;" x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line style="fill:none;" x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>',
        user: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle style="fill:none;" cx="12" cy="7" r="4"></circle></svg>',
        users: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle style="fill:none;" cx="9" cy="7" r="4"></circle><path style="fill:none;" d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path style="fill:none;" d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>',
        dash: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect style="fill:none;" x="3" y="3" width="7" height="9" rx="1"></rect><rect style="fill:none;" x="14" y="3" width="7" height="5" rx="1"></rect><rect style="fill:none;" x="14" y="12" width="7" height="9" rx="1"></rect><rect style="fill:none;" x="3" y="16" width="7" height="5" rx="1"></rect></svg>',
        time: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle style="fill:none;" cx="12" cy="12" r="10"></circle><polyline style="fill:none;" points="12 6 12 12 16 14"></polyline></svg>',
        cal: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect style="fill:none;" x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line style="fill:none;" x1="16" y1="2" x2="16" y2="6"></line><line style="fill:none;" x1="8" y1="2" x2="8" y2="6"></line><line style="fill:none;" x1="3" y1="10" x2="21" y2="10"></line></svg>',
        tv: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect style="fill:none;" x="2" y="7" width="20" height="15" rx="2" ry="2"></rect><polyline style="fill:none;" points="17 2 12 7 7 2"></polyline></svg>',
        film: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect style="fill:none;" x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line style="fill:none;" x1="7" y1="2" x2="7" y2="22"></line><line style="fill:none;" x1="17" y1="2" x2="17" y2="22"></line><line style="fill:none;" x1="2" y1="12" x2="22" y2="12"></line><line style="fill:none;" x1="2" y1="7" x2="7" y2="7"></line><line style="fill:none;" x1="2" y1="17" x2="7" y2="17"></line><line style="fill:none;" x1="17" y1="17" x2="22" y2="17"></line><line style="fill:none;" x1="17" y1="7" x2="22" y2="7"></line></svg>',
        chart: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line style="fill:none;" x1="12" y1="20" x2="12" y2="10"></line><line style="fill:none;" x1="18" y1="20" x2="18" y2="4"></line><line style="fill:none;" x1="6" y1="20" x2="6" y2="16"></line></svg>',
        masks: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M2 12c0 5.5 4.5 10 10 10s10-4.5 10-10S17.5 2 12 2 2 6.5 2 12z"></path><path style="fill:none;" d="M8 10h.01"></path><path style="fill:none;" d="M16 10h.01"></path><path style="fill:none;" d="M9 15c.5 1.5 1.5 2 3 2s2.5-.5 3-2"></path></svg>',
        star: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon style="fill:none;" points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>',
        globe: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle style="fill:none;" cx="12" cy="12" r="10"></circle><line style="fill:none;" x1="2" y1="12" x2="22" y2="12"></line><path style="fill:none;" d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>',
        bolt: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon style="fill:none;" points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>',
        flame: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"></path></svg>',
        check: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline style="fill:none;" points="20 6 9 17 4 12"></polyline></svg>',
        days: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect style="fill:none;" x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line style="fill:none;" x1="16" y1="2" x2="16" y2="6"></line><line style="fill:none;" x1="8" y1="2" x2="8" y2="6"></line><line style="fill:none;" x1="3" y1="10" x2="21" y2="10"></line><path style="fill:none;" d="M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01M16 18h.01"></path></svg>',
        grid: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect style="fill:none;" x="3" y="3" width="7" height="7"></rect><rect style="fill:none;" x="14" y="3" width="7" height="7"></rect><rect style="fill:none;" x="14" y="14" width="7" height="7"></rect><rect style="fill:none;" x="3" y="14" width="7" height="7"></rect></svg>',
        list: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line style="fill:none;" x1="8" y1="6" x2="21" y2="6"></line><line style="fill:none;" x1="8" y1="12" x2="21" y2="12"></line><line style="fill:none;" x1="8" y1="18" x2="21" y2="18"></line><line style="fill:none;" x1="3" y1="6" x2="3.01" y2="6"></line><line style="fill:none;" x1="3" y1="12" x2="3.01" y2="12"></line><line style="fill:none;" x1="3" y1="18" x2="3.01" y2="18"></line></svg>',
        nav_stats: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line style="fill:none;" x1="18" y1="20" x2="18" y2="10"></line><line style="fill:none;" x1="12" y1="20" x2="12" y2="4"></line><line style="fill:none;" x1="6" y1="20" x2="6" y2="14"></line></svg>',
        bookmark: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>',
        bookmark_plus: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path><line style="fill:none;" x1="12" y1="7" x2="12" y2="13"></line><line style="fill:none;" x1="9" y1="10" x2="15" y2="10"></line></svg>',
        grip: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle style="fill:none;" cx="9" cy="12" r="1"></circle><circle style="fill:none;" cx="9" cy="5" r="1"></circle><circle style="fill:none;" cx="9" cy="19" r="1"></circle><circle style="fill:none;" cx="15" cy="12" r="1"></circle><circle style="fill:none;" cx="15" cy="5" r="1"></circle><circle style="fill:none;" cx="15" cy="19" r="1"></circle></svg>',
        play_circle: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle style="fill:none;" cx="12" cy="12" r="10"></circle><polygon style="fill:none;" points="10 8 16 12 10 16 10 8"></polygon></svg>',
        video: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon style="fill:none;" points="23 7 16 12 23 17 23 7"></polygon><rect style="fill:none;" x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>',
        award: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle style="fill:none;" cx="12" cy="8" r="7"></circle><polyline style="fill:none;" points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"></polyline></svg>',
        eye: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle style="fill:none;" cx="12" cy="12" r="3"></circle></svg>',
        smile: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle style="fill:none;" cx="12" cy="12" r="10"></circle><path style="fill:none;" d="M8 14s1.5 2 4 2 4-2 4-2"></path><line style="fill:none;" x1="9" y1="9" x2="9.01" y2="9"></line><line style="fill:none;" x1="15" y1="9" x2="15.01" y2="9"></line></svg>',
        frown: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle style="fill:none;" cx="12" cy="12" r="10"></circle><path style="fill:none;" d="M16 16s-1.5-2-4-2-4 2-4 2"></path><line style="fill:none;" x1="9" y1="9" x2="9.01" y2="9"></line><line style="fill:none;" x1="15" y1="9" x2="15.01" y2="9"></line></svg>',
        ticket: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"></path><line style="fill:none;" x1="13" y1="5" x2="13" y2="19"></line></svg>',
        monitor: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect style="fill:none;" x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line style="fill:none;" x1="8" y1="21" x2="16" y2="21"></line><line style="fill:none;" x1="12" y1="17" x2="12" y2="21"></line></svg>',
        music: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M9 18V5l12-2v13"></path><circle style="fill:none;" cx="6" cy="18" r="3"></circle><circle style="fill:none;" cx="18" cy="16" r="3"></circle></svg>',
        zap: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon style="fill:none;" points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>',
        coffee: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M18 8h1a4 4 0 0 1 0 8h-1"></path><path style="fill:none;" d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"></path><line style="fill:none;" x1="6" y1="1" x2="6" y2="4"></line><line style="fill:none;" x1="10" y1="1" x2="10" y2="4"></line><line style="fill:none;" x1="14" y1="1" x2="14" y2="4"></line></svg>',
        ghost: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M9 10h.01"></path><path style="fill:none;" d="M15 10h.01"></path><path style="fill:none;" d="M12 2a8 8 0 0 0-8 8v12l3-3 2.5 2.5L12 19l2.5 2.5L17 19l3 3V10a8 8 0 0 0-8-8z"></path></svg>',
        skull: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M9 14h.01"></path><path style="fill:none;" d="M15 14h.01"></path><path style="fill:none;" d="M12 2a8 8 0 0 0-8 8v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7a8 8 0 0 0-8-8z"></path><path style="fill:none;" d="M10 22v-3h4v3"></path></svg>',
        rocket: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path style="fill:none;" d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path><path style="fill:none;" d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 22 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22 0 0 1-4 2z"></path><path style="fill:none;" d="M9 12H4s.55-3.03 2-5.03a12 12 0 0 1 3-3"></path><path style="fill:none;" d="M12 15v5s3.03-.55 5.03-2a12 12 0 0 0 3-3"></path></svg>',
        target: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle style="fill:none;" cx="12" cy="12" r="10"></circle><circle style="fill:none;" cx="12" cy="12" r="6"></circle><circle style="fill:none;" cx="12" cy="12" r="2"></circle></svg>',
        done: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline style="fill:none;" points="20 6 9 17 4 12"></polyline></svg>',
        minus: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line style="fill:none;" x1="5" y1="12" x2="19" y2="12"></line></svg>',
        chevron_down: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline style="fill:none;" points="6 9 12 15 18 9"></polyline></svg>',
        sort_arrow: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line style="fill:none;" x1="12" y1="5" x2="12" y2="19"></line><polyline style="fill:none;" points="19 12 12 19 5 12"></polyline></svg>',
        help: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle style="fill:none;" cx="12" cy="12" r="10"></circle><path style="fill:none;" d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line style="fill:none;" x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
        person_placeholder: '<svg viewBox="0 0 2048 2048" xmlns="http://www.w3.org/2000/svg"><path transform="translate(994,64)" d="m0 0h61l40 2 36 3 39 5 35 6 38 8 43 11 42 13 42 15 39 16 26 12 21 10 19 10 29 16 23 14 17 11 24 16 17 12 12 9 13 10 15 12 11 9 28 24 4 3v2l4 2 10 10 8 7 31 31 7 8 16 17 9 11 13 15 10 13 11 14 15 20 13 18 11 17 13 20 9 15 15 26 12 23 10 19 14 29 12 28 14 36 14 41 9 30 12 48 7 35 8 49 4 35 3 40 1 29v33l-1 37-3 47-5 43-8 47-8 38-13 50-15 47-13 34-13 32-11 24-12 25-17 33-10 17-12 20-14 22-10 15-20 28-12 17-13 16-9 11-13 15-9 10-7 8-12 13-15 16-21 21h-2v2h-2v2l-8 7-13 12-11 9-10 9-13 10-13 11-17 13-18 13-30 20-19 12-25 15-18 10-24 13-32 16-34 15-27 11-36 13-45 14-56 14-36 7-44 7-32 4-35 3-35 2h-68l-46-3-49-5-47-8-43-9-45-12-38-12-36-13-30-12-36-16-56-27-15-9-25-16-19-12-10-7-12-8-14-10-17-13-28-22-13-11-10-9-8-7-10-9-15-14-39-39-7-8-15-16-7-8-12-14-14-17-15-20-14-19-13-19-19-29-15-25-16-28-19-38-13-28-15-36-9-24-12-36-9-30-11-44-9-42-7-44-5-41-3-37-1-19v-64l2-37 4-39 5-37 8-45 8-37 13-49 17-52 14-36 12-28 13-28 15-30 11-20 16-27 8-13 19-29 10-14 9-13 11-15 8-11 11-13 9-11 9-10 9-11 9-10 7-8 6-7h2l2-4 39-39 8-7 11-10 11-9 15-13 14-11 16-13 18-13 16-11 20-14 19-12 20-12 17-10 23-13 38-19 27-12 27-11 29-11 36-12 34-10 44-11 47-9 47-7 46-4z" fill="currentColor"/><path transform="translate(993,543)" d="m0 0h65l45 3 21 2 21 4 29 10 26 11 33 16 16 8 19 10 23 14 16 12 15 13 15 14 21 21 6 5 7 8 23 23v2h2l7 8 12 14 11 15 12 21 14 26 16 33 16 37 12 36 3 16 3 35 1 22v70l-2 45-3 31-4 17-11 31-13 30-17 35-14 27-14 24-10 14-12 14-9 9-7 8-17 17-1 2h-2v2l-8 7-20 20-8 7-14 14-11 9-9 7-17 10-42 22-31 15-34 14-33 11-24 4-36 3-47 2h-32l-46-2-36-3-21-5-34-13-21-9-20-9-19-10-9-4h-3l-8 16-11 18-9 16-14 24-17 29-13 22-11 19-17 29-15 25-17 29-18 30-16 27-15 25-15 26-10 17-10 18-13 25-8 18-2 1-10-6v-22l-1-58-1-96v-550l2-122 2-52 3-34 3-15 6-18 11-29 16-34 14-28 13-22 11-17 6-11 9-13 9-11h2l2-4 6-6h2l2-4 56-56h2v-2l8-7 8-8 11-9 15-10 22-13 23-12 17-9 26-12 37-14 21-7 25-4 23-2z" fill="#CAD0D8"/><path transform="translate(1014,895)" d="m0 0h16l19 3 20 6 16 7 14 8 13 11 11 12 9 14 11 23 5 15 2 10 1 12v13l-2 17-4 16-7 18-10 18-11 12-12 12-15 10-21 10-20 6-12 2-11 1h-10l-21-3-16-5-21-10-13-9-16-15-11-14-7-12-8-20-4-15-2-11-1-16 2-18 5-20 8-20 7-12 9-12 12-12 18-13 19-10 18-6z" fill="currentColor"/></svg>',
    },

    render: function() {
        if (!D?.meta) return;
        const n = D.meta.name || 'Пользователь';
        const nameEl = document.getElementById('user-name');
        if (nameEl) {
            nameEl.textContent = n;
            requestAnimationFrame(() => this.fitText(nameEl));
        }
        
        const avEl = document.getElementById('avatar');
        if (D.meta.is_anonymous) {
            const myId = D.meta.id || 0;
            if (myId > 0) {
                avEl.innerHTML = `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:${this.getUserColor(myId)};color:#fff;font-weight:900;">${myId}</div>`;
            } else {
                avEl.innerHTML = `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:var(--bg-input);color:var(--text-muted);">${window.App.Icons.user}</div>`;
            }
        } else if (D.meta.photo_url) {
            avEl.innerHTML = `<img src="${D.meta.photo_url}" alt="A">`;
        } else {
            const u = tg?.initDataUnsafe?.user;
            if (!isSharedMode && u && u.photo_url) avEl.innerHTML = `<img src="${u.photo_url}" alt="A">`;
            else avEl.textContent = n.charAt(0).toUpperCase();
        }

        document.getElementById('period-label').textContent = D.summary?.period_label || '';
        window.App.renderYears();

        const s = D.summary || {};
        const vViews = s.total_views || 0, vEp = s.total_episodes || 0, vMov = s.total_movies || 0, vSer = s.unique_series || 0;
        
        const toggle = (id, show) => document.getElementById(id)?.classList.toggle('hidden', !show);

        const hasGroup = !!D.group;
        toggle('main-tabs', hasGroup);

        toggle('label-overview', true);
        toggle('grid-overview', true);

        document.getElementById('s-time').textContent  = s.duration_display || '0м';
        document.getElementById('s-views').textContent = vViews + ' ' + this.plural(vViews, ['просмотр', 'просмотра', 'просмотров']);
        document.getElementById('s-act').textContent   = (s.activity_percent||0) + '%';
        document.getElementById('s-daily').textContent = '~' + (s.daily_average_min||0) + ' мин/день';
        document.getElementById('s-ep').textContent = vEp;
        const epLbl = document.getElementById('s-ep').nextElementSibling;
        if (epLbl) epLbl.textContent = this.plural(vEp, ['Эпизод', 'Эпизода', 'Эпизодов']);
        const serInfo = vSer + ' ' + this.plural(vSer, ['сериал', 'сериала', 'сериалов']);
        document.getElementById('s-ser').textContent = serInfo + ' · ' + (s.series_duration || '0м');
        document.getElementById('s-mov').textContent = vMov;
        const movLbl = document.getElementById('s-mov').nextElementSibling;
        if (movLbl) movLbl.textContent = this.plural(vMov, ['Фильм', 'Фильма', 'Фильмов']);
        document.getElementById('s-uni').textContent = s.movies_duration || '0м';
        
        document.getElementById('s-wl-added').textContent = s.wishlist_added || 0;
        document.getElementById('s-wl-watched').textContent = s.wishlist_watched || 0;

        const showWelcome = vViews === 0;
        let welcomeEl = document.getElementById('welcome-empty-state');
        if (showWelcome) {
            if (!welcomeEl) {
                welcomeEl = document.createElement('div');
                welcomeEl.id = 'welcome-empty-state';
                welcomeEl.className = 'card anim-item';
                welcomeEl.innerHTML = `<div class="empty"><div class="icon">${window.App.Icons.tv}</div>Здесь будет ваша статистика, когда вы начнете смотреть кино.</div>`;
                document.getElementById('sec-personal').appendChild(welcomeEl);
            }
        } else if (welcomeEl) {
            welcomeEl.remove();
        }

        const hasDynamics = D.monthly_chart?.views?.some(v => v > 0);
        toggle('card-dynamics', hasDynamics);

        const hasWeekday = D.weekday_chart?.data?.some(v => v > 0);
        toggle('card-weekday', hasWeekday);

        const hasHeatmap = D.heatmap?.length > 0;
        toggle('card-heatmap', hasHeatmap);
        if (hasHeatmap) window.App.renderHeatmap();

        const hasGenres = D.genres?.length > 0;
        toggle('card-genres', hasGenres);
        
        const hasActors = (D.actors?.series?.length || D.actors?.others?.length);
        toggle('card-actors', hasActors);
        if (hasActors) window.App.fillList('actors-list', D.actors.series, null, ['просмотр', 'просмотра', 'просмотров'], 'actors', 'series');
        
        const hasDirectors = (D.directors?.series?.length || D.directors?.others?.length);
        toggle('card-directors', hasDirectors);
        if (hasDirectors) window.App.fillList('directors-list', D.directors.series, null, ['просмотр', 'просмотра', 'просмотров'], 'directors', 'series');

        const hasWriters = (D.writers?.series?.length || D.writers?.others?.length);
        toggle('card-writers', hasWriters);
        if (hasWriters) window.App.fillList('writers-list', D.writers.series, null, ['просмотр', 'просмотра', 'просмотров'], 'writers', 'series');
        
        const hasCountries = D.countries?.length > 0;
        toggle('card-countries', hasCountries);
        if (hasCountries) window.App.fillList('countries-list', D.countries, window.App.Icons.globe, ['просмотр', 'просмотра', 'просмотров'], 'countries');
        
        const hasBinges = D.binges?.length > 0;
        toggle('card-binges', hasBinges);
        if (hasBinges) window.App.fillBinges();

        const rt = D.ratings;
        const hasRatings = rt && rt.total > 0;
        toggle('ratings-box', hasRatings);

        if (hasRatings) {
            const ratingPalette = ['#f85149', '#f85149', '#e67e22', '#e67e22', '#d29922', '#d29922', '#388bfd', '#388bfd', '#2ea043', '#39d353'];
            const colorIdx = Math.max(0, Math.min(9, Math.floor(rt.avg) - 1));
            const scoreColor = ratingPalette[colorIdx];
            const avgEl = document.getElementById('cr-avg');
            avgEl.innerHTML = `${rt.avg.toFixed(1)}<span>/ 10</span>`;
            avgEl.style.color = scoreColor;
            document.getElementById('cr-total').innerHTML = `${rt.total}<br><span style="font-size: 11px; opacity: 0.7;">${this.plural(rt.total, ['оценка', 'оценки', 'оценок'])}</span>`;
            const badge = document.getElementById('cr-badge');
            if (rt.avg >= 8.5) { badge.textContent = 'Восторженный зритель'; badge.style.background = 'rgba(46, 204, 113, 0.15)'; badge.style.color = '#2ecc71'; }
            else if (rt.avg >= 7.0) { badge.textContent = 'Позитивный критик'; badge.style.background = 'rgba(56, 139, 253, 0.15)'; badge.style.color = '#60a5fa'; }
            else if (rt.avg >= 5.5) { badge.textContent = 'Объективный судья'; badge.style.background = 'rgba(210, 153, 34, 0.15)'; badge.style.color = '#d29922'; }
            else { badge.textContent = 'Суровый критик'; badge.style.background = 'rgba(248, 81, 73, 0.15)'; badge.style.color = '#e74c3c'; }
            window.App.renderRatingsDist();
        }

        toggle('tab-group-btn', !!D.group);
        window.App.renderGroup();
        this.renderCharts();
    },
    submitShare: submitShare,
    mainTab: function(t) { 
        document.querySelectorAll('#main-tabs .tab').forEach(b=>b.classList.toggle('on', b.dataset.tab===t)); 
        document.getElementById('sec-personal').classList.toggle('hidden', t!=='personal'); 
        document.getElementById('sec-group').classList.toggle('hidden', t!=='group'); 
    },
    pickYear: async y => {
        const cur = window.App.State.getState('nav.query.y');

        if (cur === y) return;

        window.App.State.setState('nav.query.y', y);
        window.App.markYear();

        if (isSharedMode) {
            D = SharedDataMap[y];
            window.App.render();
        } else {
            const cached = window.App.Data.getFromCache(y);

            if (cached) {
                D = cached;
                window.App.render();
                window.App.getScrollContainer().scrollTop = 0;
            } else {
                await window.App.load(y);
            }
        }

        window.App.Router.updateUrl();
    },
    openShowLayer: async function(showId, fromRouter = false) {
        document.getElementById('loader').classList.remove('hidden');
        document.getElementById('loader').style.opacity = '1';

        try {
            const r = await fetch(`/api/webapp/show/${showId}/?init_data=${encodeURIComponent(tg?.initData || '')}`);
            if (!r.ok) throw new Error('Not found');
            const show = await r.json();

            window.App._activeShowHistory = show.view_history || [];

            let crewHtml = '';
            if (show.crew && show.crew.length > 0) {
                show.crew.forEach((group, index) => {
                    crewHtml += `
                    <div class="label" style="${index === 0 ? '' : 'padding-top:0'}"><div class="icon" id="ic-users" style="color:#d29922"></div>${group.profession}</div>
                    <div class="h-scroll-container" style="padding-bottom:16px;">
                        ${group.persons.map(p => {
                            const fb = p.fallback_photo_url ? `'${p.fallback_photo_url}'` : 'null';
                            const safeName = p.name.replace(/'/g, "\\'");
                            const imgHtml = p.photo_url 
                                ? `<img src="${p.photo_url}" class="person-avatar" style="object-fit:cover;" 
                                    onerror="window.App.handleImgErr(this, ${fb}, '${safeName}')"
                                    onload="window.handleKpPlaceholder(this, '${safeName}')">` 
                                : `<div class="person-avatar">${Icons.person_placeholder}</div>`;
                            return `
                            <div class="person-pill" onclick="window.App.openCollectionLayer('person', ${p.id}, '${safeName}')">
                                ${imgHtml}
                                <div class="person-name">${p.name}</div>
                            </div>`;
                        }).join('')}
                    </div>`;
                });
                crewHtml += '<div style="height: 12px;"></div>';
            }

            let genresHtml = '';
            if (show.genres && show.genres.length > 0) {
                genresHtml = `
                <div class="label" style="padding-top:0"><div class="icon" id="it-star-internal" style="color:var(--info)"></div>Жанры</div>
                <div class="h-scroll-container" style="padding-bottom:30px;">
                    ${show.genres.map(g => `<div class="genre-pill" onclick="window.App.openCollectionLayer('genre', ${g.id}, '${g.name}')">${g.name}</div>`).join('')}
                </div>`;
            }

            const fallbackUrl = show.poster_medium || '';
            const posterUrl = show.poster_large || fallbackUrl;
            const bgUrl = posterUrl || 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';

            const preloadUrls = [];
            if (posterUrl) preloadUrls.push(posterUrl);
            if (show.crew && show.crew.length > 0) {
                const firstGroup = show.crew[0];
                firstGroup.persons.slice(0, 6).forEach(p => {
                    if (p.photo_url) preloadUrls.push(p.photo_url);
                });
            }

            if (preloadUrls.length > 0) {
                await Promise.race([
                    Promise.all(preloadUrls.map(url => new Promise(res => {
                        const img = new Image();
                        img.onload = res;
                        img.onerror = res;
                        img.src = url;
                    }))),
                    new Promise(res => setTimeout(res, 1500))
                ]);
            }

            const safeTitle = show.title.replace(/'/g, "\\'");
            const rateVal = show.personal_rating ? show.personal_rating : 'null';
            
            let countriesMetaHtml = '';
            if (show.countries && show.countries.length > 0) {
                countriesMetaHtml = `<div class="show-meta-tags" style="animation-delay: 0.3s">` + 
                    show.countries.map(c => {
                        const safeCountryName = c.name.replace(/'/g, "\\'");
                        return `<div class="sm-tag clickable" onclick="window.App.openCollectionLayer('country', ${c.id}, '${safeCountryName}')">${c.emoji ? c.emoji + ' ' : ''}${c.name}</div>`;
                    }).join('') + `</div>`;
            }

            let lastViewHtml = '';
            if (show.last_view) {
                lastViewHtml = `<div class="sm-tag clickable" style="background:var(--accent-dim); color:var(--accent); border-color:var(--accent);" 
                    onclick="window.App.openHistoryLayer('show_history', '${safeTitle}', null, null, window.App._activeShowHistory)">
                    ${Icons.eye} Просмотр: ${show.last_view.display}
                </div>`;
            }

            const html = `
                ${window.App.getLayerHeader('О шоу')}
                <div class="hero-container">
                    <div class="hero-bg" style="background-image: url('${bgUrl}')"></div>
                    <div class="hero-gradient"></div>
                    <div style="position: relative; z-index: 3; height: 85%; max-width: 65%; display: flex; align-items: flex-end;">
                        ${posterUrl ? `<img src="${posterUrl}" class="hero-poster" style="max-width: 100%; height: 100%; margin: 0; box-shadow: none;" alt="poster">` : ''}
                        <button class="wishlist-add-btn detail-wishlist-btn anim-item" style="animation-delay: 0.6s;" onclick="window.App.showFolderModal(${show.id}, '${safeTitle}')">${Icons.bookmark_plus}</button>
                        <button class="detail-add-view-btn anim-item" style="animation-delay: 0.7s;" onclick="window.App.openAddViewModal(${show.id}, '${safeTitle}', '${show.type}')">
                            ${Icons.eye}
                        </button>
                        <button class="detail-add-view-btn detail-rate-btn anim-item" style="animation-delay: 0.8s;" onclick="window.App.openRateModal(${show.id}, '${safeTitle}', ${rateVal}, '${show.type}')">
                            ${Icons.star}
                        </button>
                    </div>
                </div>
                
                <div class="show-info">
                    <div class="show-title">${show.title}</div>
                    ${show.original_title && show.original_title !== show.title ? `<div class="show-orig">${show.original_title}</div>` : ''}
                    
                    ${countriesMetaHtml}

                    <div class="show-meta-tags" style="animation-delay: 0.35s">
                        <div class="sm-tag">${show.year || '?'}</div>
                        <div class="sm-tag" style="color: var(--info); border-color: var(--info-dim); background: var(--info-dim)">${window.SHOW_TYPE_RU[show.type] || show.type || 'Show'}</div>
                        ${show.status ? `<div class="sm-tag">${window.SHOW_STATUS_RU[show.status] || show.status}</div>` : ''}
                    </div>

                    <div class="show-meta-tags" style="animation-delay: 0.4s">
                        ${show.kinopoisk_rating ? `<div class="sm-tag" style="background:rgba(241, 90, 36, 0.15); color:#f15a24; border:none">KP ${show.kinopoisk_rating}</div>` : ''}
                        ${show.imdb_rating ? `<div class="sm-tag" style="background:rgba(245, 197, 24, 0.15); color:#f5c518; border:none">IMDb ${show.imdb_rating}</div>` : ''}
                        ${show.internal_rating ? `<div class="sm-tag" style="background:var(--accent-dim); color:var(--accent); border:none">★ ${show.internal_rating.toFixed(1)}</div>` : ''}
                    </div>

                    ${lastViewHtml ? `<div class="show-meta-tags" style="animation-delay: 0.45s">${lastViewHtml}</div>` : ''}
                </div>

                ${show.plot ? `<div class="plot-box">${show.plot}</div>` : ''}

                ${genresHtml}
                ${crewHtml}
            `;

            const currentTop = viewStack[viewStack.length - 1];
            const isRefresh = currentTop && currentTop.context.type === 'show' && currentTop.context.showId == showId;

            window.App.pushLayer(html, { 
                type: 'show', 
                showId: showId, 
                replace: isRefresh,
                fromRouter: fromRouter
            });
            return true;
        } catch (e) {
            window.App.showToast('Не удалось загрузить данные шоу');
            return false;
        } finally {
            window.App.hideLoader();
        }
    },
    doSearch: async function (q) {
        clearTimeout(searchTimer);
        const resEl = document.getElementById('search-results');
        if (q.length < 2) { 
            resEl.innerHTML = `<div class="empty"><div class="icon" style="font-size: 48px; opacity: 0.3; margin-bottom: 16px;">${Icons.search}</div>Введите название для поиска</div>`;
            return; 
        }
        
        resEl.innerHTML = '<div class="loader-inline"><div class="spinner" style="width:32px;height:32px;border-width:3px;"></div></div>';
        
        searchTimer = setTimeout(async () => {
            try {
                const r = await fetch('/api/webapp/search/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ query: q, init_data: tg?.initData || '' })
                });
                if (!r.ok) throw new Error('Ошибка сервера');
                const data = await r.json();
                window.App.renderSearchResults(data);
            } catch(e) {
                resEl.innerHTML = '<div class="empty">Ошибка при поиске</div>';
            }
        }, 500);
    },
    renderCharts: function() { 
        if (typeof Chart === 'undefined') return;
        
        // Используем requestAnimationFrame для плавности при быстром переключении
        requestAnimationFrame(() => {
            try {
                window.App.renderMonthly(); 
                window.App.renderWeekday(); 
                window.App.renderDonut('c-genre', 'legend-genre', D.genres, 'genres_top', D.summary.total_minutes_watched);
                if (D.group) {
                    window.App.renderDonut('c-group-genre', 'legend-group-genre', D.group.genres, 'group_genres_top', D.group.total_minutes_watched);
                }
            } catch (e) {
                console.error('Chart render error:', e);
            }
        });
    },
    Router: {
        parse() {
            const hash = window.location.hash.startsWith('#/') ? window.location.hash.slice(2) : '';
            const [pathStr, queryStr] = hash.split('?');
            const segments = pathStr ? pathStr.split('/') : [];
            const params = new URLSearchParams(queryStr || '');
            return { segments, params };
        },

        serialize() {
            let path = window.App.State.getState('nav.activeMainView') || 'search';
            
            viewStack.forEach(layer => {
                const ctx = layer.context;
                if (ctx.type === 'show') {
                    path += `/show/${ctx.showId}`;
                } else if (ctx.type === 'collection') {
                    path += `/${ctx.ctype}/${ctx.itemId}`;
                } else if (ctx.type === 'history') {
                    path += `/history/${ctx.htype || 'all'}`;
                }
            });

            const query = new URLSearchParams();
            const y = window.App.State.getState('nav.query.y');
            if (y && y !== 'all') query.set('y', y);
            
            const q = window.App.State.getState('forms.search.query');
            if (path.startsWith('search') && q) {
                query.set('q', q);
            }
            
            const qStr = query.toString();
            return '#/' + path + (qStr ? '?' + qStr : '');
        },

        updateUrl() {
            if (window.App.State.getState('flags.isSyncingHash')) return;
            const newHash = this.serialize();
            if (window.location.hash !== newHash) {
                history.pushState(null, "", newHash);
            }
        },

        async sync() {
            if (window.App.State.getState('flags.isSyncingHash')) return;
            window.App.State.setState('flags.isSyncingHash', true);

            const { segments, params } = this.parse();
            if (segments.length === 0) {
                window.App.State.setState('flags.isSyncingHash', false);
                return;
            }

            const targetMainView = segments[0];
            const year = params.get('y') || 'all';

            window.App.State.setState('nav.query.y', year);

            if (window.App.State.getState('nav.activeMainView') !== targetMainView) {
                // Закрываем все слои перед переключением корня
                while (viewStack.length > 0) {
                    const top = viewStack.pop();
                    top.el.remove();
                }
                window.App.switchMainView(targetMainView, true);
            }

            await window.App.load(year, false);
            window.App.markYear();

            const layerSegments = segments.slice(1);
            const targetDepth = Math.floor(layerSegments.length / 2);

            // Синхронизируем стек слоев
            while (viewStack.length > targetDepth) {
                const top = viewStack.pop();
                top.el.remove();
            }

            if (viewStack.length > 0) {
                viewStack[viewStack.length - 1].el.style.display = 'block';
            } else {
                if (!isSharedMode) document.getElementById('bottom-nav').style.display = 'flex';
            }

            window.App.State.setState('flags.isSyncingHash', false);
            this.updateUrl();
        }
    },
    switchMainView: function(view, fromRouter = false) {
        activeMainView = view;
        window.App.State.setState('nav.activeMainView', view);
        
        document.querySelectorAll('.view').forEach(el => {
            el.style.display = 'none';
            el.classList.remove('active-view');
        });

        const targetEl = document.getElementById(`view-${view}`);
        if (targetEl) {
            targetEl.style.display = view === 'search' ? 'flex' : 'block';
            targetEl.classList.add('active-view');
        }
        
        const savedScroll = window.App.State.getState(`ui.scrollPositions.${view}`) || 0;
        window.App.getScrollContainer().scrollTop = savedScroll;

        if (view === 'wishlist' && window.App.loadWishlist && !isSharedMode) {
            window.App.loadWishlist();
        }

        if (!fromRouter && !window.App.State.getState('flags.isSyncingHash')) {
            window.App.Router.updateUrl();
        }
    },
    load: async function(year, isBackground = false) {
        if (year === undefined || year === null) year = curYear;

        const cachedData = window.App.Data.getFromCache(year);
        if (cachedData) {
            if (!isBackground) {
                curYear = year;
                D = cachedData;
                window.App.render();
                window.App.hideLoader();
                return;
            }
        }

        if (!isBackground) {
            document.getElementById('loader').classList.remove('hidden');
            document.getElementById('loader').style.opacity = '1';
        }

        try {
            const p = year && year !== 'all' ? { period_type: 'year', period_value: year } : { period_type: 'year', period_value: 0 };
            
            const payload = { 
                ...p, 
                init_data: tg?.initData || '',
                screen_width: window.innerWidth,
                screen_height: window.innerHeight
            };

            const r = await fetch('/api/webapp/detailed_stats/', { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify(payload) 
            });
            
            if (!r.ok) throw new Error(`Server error: ${r.status}`);
            const j = await r.json();
            if (j.error) throw new Error(j.error);
            
            window.App.Data.saveToCache(year, j);
            
            if (!availableYears.length && j.meta?.years) {
                availableYears = [...j.meta.years];
                window.App.preloadAllPeriods();
            }

            if (!isBackground) {
                curYear = year;
                D = j;
                window.App.render();
            } else if (year === curYear) {
                D = j;
                window.App.render();
            }
        } catch (e) { 
            console.error('Load error:', e); 
            if (!isBackground) {
                document.getElementById('app').innerHTML = `<div style="padding: 40px; text-align:center;"><div style="font-size: 40px;">❌</div>Ошибка загрузки</div>`;
            }
        } finally { 
            if (!isBackground) window.App.hideLoader();
        }
    },
    openCasino: window.openCasino,
    closeCasino: window.closeCasino,
    resetCasino: window.resetCasino,
    getScrollContainer: function() {
        return document.getElementById('views-container');
    },
    fitText: function(el) {
        if (!el) return;
        el.style.fontSize = "";
        const styles = window.getComputedStyle(el);
        const limitWidth = el.clientWidth;
        const limitHeight = parseFloat(styles.maxHeight) || el.offsetHeight || 40;
        const isSingleLine = styles.whiteSpace === 'nowrap' || styles.webkitLineClamp === '1';
        let size = parseFloat(styles.fontSize);
        const minSize = 9;
        const originalMaxHeight = el.style.maxHeight;
        const originalClamp = el.style.webkitLineClamp;
        
        if (isSingleLine) {
            while (el.scrollWidth > limitWidth + 1 && size > minSize) {
                size -= 0.5;
                el.style.fontSize = size + "px";
            }
        } else {
            el.style.webkitLineClamp = "none";
            el.style.maxHeight = "none";
            while (el.scrollHeight > limitHeight + 1 && size > minSize) {
                size -= 0.5;
                el.style.fontSize = size + "px";
            }
            el.style.webkitLineClamp = originalClamp;
            el.style.maxHeight = originalMaxHeight;
        }
    },
    fitAll: function(selector, container = document) {
        const elements = container.querySelectorAll(selector);
        elements.forEach(el => this.fitText(el));
    },
    toggleHistoryEditMode: function() {
        const cur = window.App.State.getState('flags.isHistoryEditMode');
        window.App.State.setState('flags.isHistoryEditMode', !cur);
    },
    removeRatingItem: function(btn, payload) {
        const msg = "Удалить эту оценку?";
        const element = btn.closest('.grid-item-wrap') || btn.closest('.hist-item');
        const performDelete = async () => {
            if (element) {
                element.style.transition = 'all 0.3s ease';
                element.style.opacity = '0';
                element.style.transform = 'scale(0.8)';
                setTimeout(() => element.remove(), 300);
            }
            try {
                const r = await fetch('/api/webapp/delete_rating/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ init_data: tg?.initData || '', ...payload })
                });
                if (!r.ok) throw new Error('Ошибка API');
                window.App.Data.cache.clear();
                window.App.showToast('Оценка удалена');
                if (activeMainView === 'stats') window.App.load(curYear, true);
            } catch(e) {
                window.App.showToast('Не удалось удалить');
                if (element) {
                    element.style.opacity = '1';
                    element.style.transform = 'scale(1)';
                }
            }
        };
        if (window.Telegram?.WebApp?.showConfirm) {
            window.Telegram.WebApp.showConfirm(msg, (confirmed) => { if (confirmed) performDelete(); });
        } else {
            if (confirm(msg)) performDelete();
        }
    },
    startCasinoSpin: window.startCasinoSpin,
    removeHistoryItem: function(btn, payload) {
        const msg = "Удалить этот просмотр из вашей истории?";
        const element = btn.closest('.grid-item-wrap') || btn.closest('.hist-item');
        const performDelete = async () => {
            if (element) {
                element.style.transition = 'all 0.3s ease';
                element.style.opacity = '0';
                element.style.transform = 'scale(0.8)';
                setTimeout(() => element.remove(), 300);
            }
            try {
                const r = await fetch('/api/webapp/remove_view/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ init_data: tg?.initData || '', ...payload })
                });
                if (!r.ok) throw new Error('Ошибка API');
                window.App.Data.cache.clear();
                window.App.showToast('Просмотр удален');
            } catch(e) {
                window.App.showToast('Не удалось удалить');
                if (element) {
                    element.style.opacity = '1';
                    element.style.transform = 'scale(1)';
                }
            }
        };
        if (window.Telegram?.WebApp?.showConfirm) {
            window.Telegram.WebApp.showConfirm(msg, (confirmed) => { if (confirmed) performDelete(); });
        } else {
            if (confirm(msg)) performDelete();
        }
    },
    showStatsHelp: function(e) {
        if (e) { e.preventDefault(); e.stopPropagation(); }
        const informer = document.getElementById('wl-stats-informer');
        if (!informer) return;
        if (informer.classList.contains('show')) {
            informer.classList.remove('show');
            return;
        }
        informer.classList.add('show');
        const closeHandler = () => { informer.classList.remove('show'); document.removeEventListener('click', closeHandler); };
        setTimeout(() => document.addEventListener('click', closeHandler), 10);
    },
    closeItemDeleteModal: function() {
        window.App.State.setState('modals.wlDelete.isOpen', false);
        itemToDeleteId = null;
        itemToDeleteElement = null;
    },
    openAddViewModal: function(showId, title, type) {
        const draft = window.App.State.getState('forms.addView');
        window.App.State.setState('modals.addView', { isOpen: true, context: { showId, title, type }});
        
        document.getElementById('add-view-title').textContent = title;
        const isSeries = ['Series', 'Documentary Series', 'TV Show'].includes(type);
        document.getElementById('add-view-se-container').style.display = isSeries ? 'flex' : 'none';
        
        document.getElementById('add-view-season').value = draft.season || '';
        document.getElementById('add-view-episode').value = draft.episode || '';

        if (!draft.exact) {
            const today = new Date();
            const year = today.getFullYear();
            const month = String(today.getMonth() + 1).padStart(2, '0');
            const day = String(today.getDate()).padStart(2, '0');
            window.App.State.setState('forms.addView.exact', `${year}-${month}-${day}`);
            window.App.State.setState('forms.addView.month', `${year}-${month}`);
            window.App.State.setState('forms.addView.year', year);
            document.getElementById('add-view-exact').value = `${year}-${month}-${day}`;
            document.getElementById('add-view-month').value = `${year}-${month}`;
            document.getElementById('add-view-year').value = year;
        } else {
            document.getElementById('add-view-exact').value = draft.exact;
            document.getElementById('add-view-month').value = draft.month;
            document.getElementById('add-view-year').value = draft.year;
        }

        window.App.setAddViewMode(draft.dateMode || 'exact');
    },
    setAddViewMode: function(mode, btn) {
        window.App.State.setState('forms.addView.dateMode', mode);
        const btns = document.querySelectorAll('#add-view-modal .vt-btn');
        btns.forEach(b => b.classList.remove('active'));
        if (btn) btn.classList.add('active');
        else {
            const modeMap = {'exact': 0, 'month': 1, 'year': 2, 'unknown': 3};
            if (btns.length > 0 && modeMap[mode] !== undefined) btns[modeMap[mode]].classList.add('active');
        }

        document.getElementById('add-view-exact').style.display = mode === 'exact' ? 'block' : 'none';
        document.getElementById('add-view-month').style.display = mode === 'month' ? 'block' : 'none';
        document.getElementById('add-view-year').style.display = mode === 'year' ? 'block' : 'none';
        document.getElementById('add-view-unknown-text').style.display = mode === 'unknown' ? 'block' : 'none';
    },
    closeAddViewModal: function() {
        window.App.State.setState('modals.addView.isOpen', false);
    },
    submitAddView: async function() {
        const btn = document.getElementById('btn-add-view-submit');
        const origHtml = btn.innerHTML;
        const ctx = window.App.State.getState('modals.addView.context');
        const draft = window.App.State.getState('forms.addView');

        const isSeries = ['Series', 'Documentary Series', 'TV Show'].includes(ctx.type);
        let season = 0, episode = 0;
        if (isSeries) {
            season = parseInt(draft.season);
            episode = parseInt(draft.episode);
            if (!season || !episode) {
                window.App.showToast('Укажите сезон и эпизод');
                return;
            }
        }

        let dateVal = null;
        if (draft.dateMode === 'exact') dateVal = draft.exact;
        if (draft.dateMode === 'month') dateVal = draft.month;
        if (draft.dateMode === 'year') dateVal = draft.year;

        btn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px;margin:0;"></div>';
        btn.disabled = true;

        try {
            const r = await fetch('/api/webapp/add_view/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    init_data: tg?.initData || '',
                    show_id: ctx.showId,
                    season: season,
                    episode: episode,
                    date_mode: draft.dateMode,
                    date_val: dateVal
                })
            });
            const j = await r.json();
            if (j.error) throw new Error(j.error);

            window.App.showToast('Просмотр добавлен!');
            window.App.closeAddViewModal();
            window.App.Data.cache.clear();
            window.App.load(curYear);
        } catch(e) {
            window.App.showToast('Ошибка: ' + e.message);
        } finally {
            btn.innerHTML = origHtml;
            btn.disabled = false;
        }
    },
    restoreModals: function() {
        const modals = window.App.State.getState('modals');
        
        const origSave = window.App.State.saveSessionDebounced;
        window.App.State.saveSessionDebounced = () => {};

        if (modals.addView?.isOpen && modals.addView.context?.showId) {
            const ctx = modals.addView.context;
            window.App.openAddViewModal(ctx.showId, ctx.title, ctx.type);
        }
        if (modals.rateShow?.isOpen && modals.rateShow.context?.showId) {
            const ctx = modals.rateShow.context;
            window.App.openRateModal(ctx.showId, ctx.title, ctx.currentVal, ctx.showType);
            if (ctx.level) window.App.setRateLevel(ctx.level, ctx);
        }
        if (modals.wlEdit?.isOpen) {
            const ctx = modals.wlEdit.context;
            window.App.openFolderEditModal(ctx.isEdit, ctx.folderId);
        }
        if (modals.wlFolder?.isOpen && modals.wlFolder.context?.showId) {
            const ctx = modals.wlFolder.context;
            window.App.showFolderModal(ctx.showId, ctx.title);
        }
        if (modals.wlDelete?.isOpen && modals.wlDelete.context?.id) {
            window.App.confirmDeleteWlItem(modals.wlDelete.context.id);
        }
        if (modals.share?.isOpen) {
            window.App.openShareModal();
        }

        window.App.State.saveSessionDebounced = origSave;

        requestAnimationFrame(() => {
            window.App.State.applyStateToDOM();
        });
    },
    initIcons: function() {
        window.App.i('ic-search-nav', 'search'); window.App.i('ic-stats-nav', 'nav_stats');
        window.App.i('ic-wishlist-nav', 'bookmark');
        window.App.i('ic-bookmark', 'bookmark'); window.App.i('ic-check', 'check');
        window.App.i('wl-vt-grid', 'grid'); window.App.i('wl-vt-list', 'list');
        window.App.i('wl-edit-btn', 'gear');
        
        window.App.i('ic-user', 'user'); window.App.i('ic-users', 'users'); window.App.i('ic-dash', 'dash');
        window.App.i('ic-time', 'time'); window.App.i('ic-cal', 'cal'); window.App.i('ic-tv', 'tv'); window.App.i('ic-film', 'film');
        window.App.i('ic-chart-internal', 'chart'); window.App.i('ic-flame-internal', 'flame');
        window.App.i('it-gen-internal', 'masks'); window.App.i('it-act-internal', 'masks'); 
        window.App.i('it-dir-internal', 'film'); window.App.i('it-wri-internal', 'list');
        window.App.i('it-cou-internal', 'globe'); window.App.i('it-bin-internal', 'bolt');
        window.App.i('it-star-internal', 'star'); window.App.i('ic-weekday-internal', 'days');

        window.App.i('ic-stat-history', 'chart'); window.App.i('ic-stat-parser', 'zap');
        window.App.i('ic-stat-shows', 'play_circle'); window.App.i('ic-stat-ratings', 'star');
        window.App.i('ic-stat-durations', 'time'); window.App.i('ic-stat-photos', 'user');
        window.App.i('ic-stat-tg', 'check'); window.App.i('ic-stat-users', 'users');
        window.App.i('ic-stat-errors', 'ghost');

        window.App.i('ic-met-total-shows', 'tv'); window.App.i('ic-met-missing-year', 'cal');
        window.App.i('ic-met-missing-status', 'target'); window.App.i('ic-met-collisions', 'edit');
        window.App.i('ic-met-missing-durations', 'time'); window.App.i('ic-met-missing-plot', 'list');
        window.App.i('ic-met-total-genres', 'masks'); window.App.i('ic-met-no-genres', 'frown');
        window.App.i('ic-met-unmapped-genres', 'skull'); window.App.i('ic-met-missing-kp', 'frown');
        window.App.i('ic-met-has-kp', 'smile'); window.App.i('ic-met-missing-imdb', 'frown');
        window.App.i('ic-met-has-imdb', 'smile'); window.App.i('ic-met-total-countries', 'globe');
        window.App.i('ic-met-no-countries', 'minus'); window.App.i('ic-met-missing-country-meta', 'target');
        window.App.i('ic-met-duplicate-photo', 'users'); window.App.i('ic-met-persons-by-type', 'user');
        window.App.i('ic-met-persons-avatar', 'eye'); window.App.i('ic-met-professions', 'rocket');
        window.App.i('ic-met-en-professions', 'gear'); window.App.i('ic-met-unused-persons', 'trash');
        
        const casinoBtn = document.getElementById('wl-casino-btn');
        if (casinoBtn) casinoBtn.innerHTML = '🎰';
        
        const reorderBtn = document.getElementById('wl-reorder-btn');
        if (reorderBtn) reorderBtn.innerHTML = window.App.Icons.reorder;

        const itemsReorderBtn = document.getElementById('wl-items-reorder-btn');
        if (itemsReorderBtn) itemsReorderBtn.innerHTML = window.App.Icons.reorder;

        const currentTheme = window.App.State.getState('ui.theme') || (document.body.classList.contains('light') ? 'light' : 'dark');
        document.querySelectorAll('.theme-btn, .js-theme-toggle').forEach(btn => {
            btn.innerHTML = currentTheme === 'dark' ? window.App.Icons.moon : window.App.Icons.sun;
        });

        document.querySelectorAll('.js-ic-help').forEach(el => {
            el.innerHTML = window.App.Icons.help;
        });
    },
    init: async function() {
        if (window.IS_ADMIN_DASHBOARD) return;

        window.App.State.subscribe('ui.theme', (theme) => {
            isDark = theme === 'dark';
            document.body.classList.toggle('light', !isDark);
            document.querySelectorAll('.theme-btn, .js-theme-toggle').forEach(btn => {
                btn.innerHTML = isDark ? window.App.Icons.moon : window.App.Icons.sun;
            });
            if (D) window.App.renderCharts();
        });

        const modalMap = {
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

        Object.entries(modalMap).forEach(([stateKey, elId]) => {
            window.App.State.subscribe(`modals.${stateKey}.isOpen`, (isOpen) => {
                const el = document.getElementById(elId);
                if (el) el.classList.toggle('show', isOpen);
            });
        });

        const scrollHandler = window.App.State._debounce((e) => {
            const target = e.target;
            if (target.id === 'views-container') {
                window.App.State.setState(`ui.scrollPositions.${window.App.State.getState('nav.activeMainView')}`, target.scrollTop);
            } else if (target.classList.contains('layer')) {
                window.App.State.setState(`ui.scrollPositions.layer_${viewStack.length}`, target.scrollTop);
            }
        }, 150);

        document.getElementById('views-container').addEventListener('scroll', scrollHandler);
        document.getElementById('dynamic-layers').addEventListener('scroll', scrollHandler, true);

        window.App.initIcons();
        window.App.State.applyStateToDOM();

        window.App.State.setState('flags.isSyncingHash', true);

        const { segments } = window.App.Router.parse();
        const sharedIdFromUrl = new URLSearchParams(window.location.search).get('shared_id');
        const startParam = tg?.initDataUnsafe?.start_param || '';

        let initialView = 'search';
        if (sharedIdFromUrl || startParam.startsWith('stat_')) {
            initialView = 'stats';
            isSharedMode = true;
        } else if (segments.length > 0) {
            initialView = segments[0];
        } else {
            initialView = window.App.State.getState('nav.activeMainView') || 'search';
        }

        window.App.switchMainView(initialView, true);

        if (isSharedMode) {
            document.body.classList.add('has-banner');
            document.getElementById('share-btn').classList.add('hidden');
            document.getElementById('bottom-nav').style.display = 'none';
            
            const bannerContainer = document.getElementById('shared-banner-container');
            bannerContainer.innerHTML = `<div class="shared-banner">Вы просматриваете чужую статистику</div>`;
            
            const sid = sharedIdFromUrl || startParam.replace('stat_', '');
            await window.App.loadShared(sid);
        } else {
            await window.App.load(window.App.State.getState('nav.query.y') || 'all');
            
            const role = D?.meta?.role || 'guest';
            document.getElementById('bottom-nav').style.display = 'flex';
            document.body.classList.add('has-nav');
            if (role === 'guest') document.getElementById('bn-stats').classList.add('hidden');

            const savedStack = window.App.State.getState('nav.layerStack') || [];
            if (savedStack.length > 0) {
                for (const ctx of savedStack) {
                    if (ctx.type === 'show') await window.App.openShowLayer(ctx.showId, true);
                    else if (ctx.type === 'history') window.App.openHistoryLayer(ctx.htype, ctx.title, ctx.extraId, ctx.extraDate, ctx.extraKey, ctx.extraIndex, true);
                    else if (['person', 'genre', 'country'].includes(ctx.type)) await window.App.openCollectionLayer(ctx.ctype, ctx.itemId, ctx.titleFallback, true);
                }
            } else if (segments.length > 1) {
                const layerSegments = segments.slice(1);
                const historyTitles = {
                    'all': 'Вся история',
                    'movies': 'Фильмы',
                    'episodes': 'Эпизоды',
                    'wishlist_watched': 'Избранное',
                    'casino': 'История рулетки'
                };

                for (let i = 0; i < Math.floor(layerSegments.length / 2); i++) {
                    const type = layerSegments[i * 2];
                    const id = layerSegments[i * 2 + 1];
                    if (type === 'show') await window.App.openShowLayer(id, true);
                    else if (type === 'history') window.App.openHistoryLayer(id, historyTitles[id] || 'История', null, null, null, null, true);
                    else if (['person', 'genre', 'country'].includes(type)) await window.App.openCollectionLayer(type, id, '', true);
                }
            }
        }

        const savedSearchQuery = window.App.State.getState('forms.search.query');
        if (savedSearchQuery && savedSearchQuery.length >= 2) {
            window.App.doSearch(savedSearchQuery);
        }

        const currentTheme = window.App.State.getState('ui.theme');
        document.querySelectorAll('.theme-btn, .js-theme-toggle').forEach(btn => {
            btn.innerHTML = currentTheme === 'dark' ? window.App.Icons.moon : window.App.Icons.sun;
        });

        window.App.State.setState('flags.isSyncingHash', false);
        window.App.Router.updateUrl();
        window.App.restoreModals();
    },

    renderSearchResults: function(data) {
        let html = '';
        
        if (data.persons?.length) {
            html += `<div class="label"><div class="icon" style="color:#d29922">${Icons.users}</div>Люди</div>`;
            html += '<div class="h-scroll-container" style="padding-bottom:16px;">';
            data.persons.forEach(p => {
                const fb = p.fallback_photo_url ? `'${p.fallback_photo_url}'` : 'null';
                const safeName = p.name.replace(/'/g, "\\'");
                const img = p.photo_url 
                    ? `<img src="${p.photo_url}" class="person-avatar" style="object-fit:cover;" 
                        onerror="window.App.handleImgErr(this, ${fb}, '${safeName}')" 
                        onload="window.handleKpPlaceholder(this, '${safeName}')">` 
                    : `<div class="person-avatar">${Icons.person_placeholder}</div>`;
                html += `<div class="person-pill" onclick="window.App.openCollectionLayer('person', ${p.id}, '${safeName}')">${img}<div class="person-name">${p.name}</div></div>`;
            });
            html += '</div>';
        }
        
        if (data.shows?.length) {
            html += `<div class="label"><div class="icon" style="color:var(--info)">${Icons.film}</div>Фильмы и Сериалы</div>`;
            html += '<div class="hist-grid" style="padding:0 16px;">';
            data.shows.forEach(s => {
                const poster = s.poster_url ? `<img src="${s.poster_url}" class="grid-poster" loading="lazy">` : '<div class="grid-poster"></div>';
                const safeTitle = s.title.replace(/'/g, "\\'");
                
                let badgesHtml = '';
                if (s.user_rating) {
                    badgesHtml = `<span class="rating-badge" style="background:rgba(0,0,0,0.6);border:none;">${Icons.star}${s.user_rating}</span>`;
                }

                html += `<div class="grid-item-wrap anim-item" onclick="window.App.openShowLayer(${s.id})">
                    <div class="grid-item">
                        ${poster}
                        <div class="grid-badges">${badgesHtml}</div>
                        ${s.year ? `<div class="grid-year">${s.year}</div>` : ''}
                        <button class="wishlist-add-btn" onclick="event.stopPropagation(); window.App.showFolderModal(${s.id}, '${safeTitle}')">${Icons.bookmark_plus}</button>
                    </div>
                    <div class="grid-below-title">${s.title}</div>
                </div>`;
            });
            html += '</div>';
        }
        
        if (!data.shows?.length && !data.persons?.length) {
            html = `<div class="empty"><div class="icon">${Icons.dash}</div>Ничего не найдено</div>`;
        }

        const resultsContainer = document.getElementById('search-results');
        resultsContainer.innerHTML = html;
        
        document.getElementById('search-results').innerHTML = html;
        requestAnimationFrame(() => {
            window.App.fitAll('.grid-below-title', resultsContainer);
        });
    },

    i: function(id, name) {
        const el = document.getElementById(id);

        if (el) {
            el.innerHTML = window.App.Icons[name];
        }
    },

    cc: function() {
        const t = isDark ? 'rgba(229, 231, 235, .8)' : 'rgba(31, 35, 40, .8)';
        const g = isDark ? 'rgba(255, 255, 255, .05)' : 'rgba(0, 0, 0, .05)';
        const b = isDark ? '#2d333b' : '#d0d7de';
        return { t, g, b, a: '#2ecc71', ab: isDark ? 'rgba(46, 204, 113, .2)' : 'rgba(46, 204, 113, .15)', i: '#60a5fa', ib: isDark ? 'rgba(96, 165, 250, .2)' : 'rgba(96, 165, 250, .15)' };
    },

    handleKpPlaceholder: function(img, name) {
        // Проверка на специфические размеры заглушки Кинопоиска (no-poster.gif)
        // Эти размеры определены в ходе исследования: 208x304
        if (img.naturalWidth === 208 && img.naturalHeight === 304) {
            window.App.handleImgErr(img, null, name);
        }
    },

    Data: {
        cache: new Map(),
        isPreloading: false,
        
        getCacheKey(year) {
            const uid = D?.meta?.id || 'anon';
            return `ks_cache_${uid}_${year || 'all'}`;
        },

        saveToCache(year, data) {
            if (window.IS_DEBUG) return;
            const key = this.getCacheKey(year);
            this.cache.set(key, data);
            try {
                sessionStorage.setItem(key, JSON.stringify({
                    data: data,
                    ts: Date.now()
                }));
            } catch (e) { console.warn('Cache save failed', e); }
        },

        getFromCache(year) {
            if (window.IS_DEBUG) return null;
            const key = this.getCacheKey(year);
            if (this.cache.has(key)) return this.cache.get(key);
            
            const stored = sessionStorage.getItem(key);
            if (stored) {
                const parsed = JSON.parse(stored);
                // Кэш валиден 30 минут в рамках сессии
                if (Date.now() - parsed.ts < 30 * 60 * 1000) {
                    this.cache.set(key, parsed.data);
                    return parsed.data;
                }
            }
            return null;
        }
    },

    handleImgErr: function(img, fallbackUrl, name) {
        if (fallbackUrl && !img.dataset.fallbackTried) {
            img.dataset.fallbackTried = 'true';
            img.src = fallbackUrl;
        } else {
            const wrapper = document.createElement('div');
            wrapper.className = (img.className || '') + ' is-placeholder';
            wrapper.style.cssText = img.style.cssText;
            wrapper.innerHTML = window.App.Icons.person_placeholder;
            img.replaceWith(wrapper);
        }
    },

    loadShared: async function (statId) {
        document.getElementById('loader').classList.remove('hidden');
        try {
            const r = await fetch(`/api/webapp/shared_stats/${statId}/`);
            if (!r.ok) throw new Error(`Ошибка HTTP сервера: ${r.status}`);
            const j = await r.json();
            if (j.error) throw new Error(j.error);
            
            SharedDataMap = j.data;
            availableYears = j.metadata.years;
            curYear = availableYears[0];
            D = SharedDataMap[curYear];
            
            window.App.render();
        } catch(e) { 
            console.error(e); 
            document.getElementById('app').innerHTML = `<div style="padding: 40px; text-align:center; font-size: 16px; color: var(--text-primary);"><div style="font-size: 40px; margin-bottom: 10px;">❌</div>Слепок не найден или произошла ошибка:<br><br><span style="color:var(--danger);">${e.message}</span></div>`;
            document.getElementById('app').classList.remove('hidden');
        } finally {
            window.App.hideLoader();
        }
    },

    preloadAllPeriods: async function() {
        if (window.App.Data.isPreloading || window.IS_DEBUG) return;
        window.App.Data.isPreloading = true;

        const yearsToLoad = availableYears.filter(y => y !== curYear);
        
        for (const year of yearsToLoad) {
            if (!window.App.Data.getFromCache(year)) {
                await new Promise(res => setTimeout(res, 1200));
                await window.App.load(year, true);
            }
        }
    },

    hideLoader: function() {
        document.getElementById('loader').style.opacity = '0';
        setTimeout(() => document.getElementById('loader').classList.add('hidden'), 400);
        document.getElementById('app').classList.remove('hidden'); 
    },

    switchPersonTab: function(category, mode, btn) {
        const container = btn.closest('.view-toggle');
        container.querySelectorAll('.vt-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        const data = D[category][mode];
        window.App.fillList(`${category}-list`, data, null, ['просмотр', 'просмотра', 'просмотров'], category, mode);
    },

    renderRatingsDist: function() {
        if (typeof Chart === 'undefined') return;
        
        const canvas = document.getElementById('c-ratings-dist');
        const ctx = canvas.getContext('2d');
        if (chR) chR.destroy();
        const dist = D.ratings.distribution;
        if (!dist || dist.length === 0) return;
        const c = window.App.cc();
        const ratingPalette = ['#f85149', '#f85149', '#e67e22', '#e67e22', '#d29922', '#d29922', '#388bfd', '#388bfd', '#2ea043', '#39d353'];

        chR = new Chart(ctx, {
            type: 'bar',
            data: { labels: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'], datasets: [{ data: dist, backgroundColor: ratingPalette, hoverBackgroundColor: ratingPalette, borderRadius: 6, borderSkipped: false, borderWidth: 0 }] },
            options: {
                responsive: true, maintainAspectRatio: false,
                animation: { duration: 1000, easing: 'easeOutBack', delay: (context) => context.type === 'data' && context.mode === 'default' && !context.active ? context.dataIndex * 80 : 0 },
                onHover: (event, activeElements) => { event.native.target.style.cursor = activeElements.length ? 'pointer' : 'default'; },
                onClick: (event, activeElements) => { if (activeElements.length > 0) window.App.openHistoryLayer('rating_filter', 'Оценка: ' + (activeElements[0].index + 1), null, null, null, activeElements[0].index + 1); },
                plugins: {
                    legend: { display: false },
                    tooltip: { backgroundColor: isDark ? 'rgba(22, 27, 34, 0.95)' : 'rgba(255, 255, 255, 0.95)', titleColor: isDark ? '#f0f6fc' : '#1f2328', bodyColor: isDark ? '#8b949e' : '#59636e', borderColor: c.b, borderWidth: 1, cornerRadius: 10, padding: 12, displayColors: false, callbacks: { title: (ctx) => `Оценка: ${ctx[0].label}`, label: (ctx) => ` ${ctx.parsed.y} ${window.App.plural(ctx.parsed.y, ['оценка', 'оценки', 'оценок'])}` } }
                },
                scales: { x: { ticks: { color: c.t, font: { size: fSizeAx, weight: '600' } }, grid: { display: false } }, y: { display: false, beginAtZero: true } }
            }
        });
    },

    renderYears: function() {
        const c = document.getElementById('years');
        const yrs = isSharedMode ? availableYears : (D.meta?.years || []);
        
        if (yrs.length <= 1) {
            c.classList.add('hidden');
            return;
        }
        c.classList.remove('hidden');

        let h = '';
        if (!isSharedMode || yrs.includes('all')) {
            h += '<button class="yr clickable" onclick="window.App.pickYear(\'all\')">Всё время</button>';
        }
        
        yrs.filter(y => y !== 'all').forEach(y => { 
            h += `<button class="yr clickable" onclick="window.App.pickYear('${y}')">${y}</button>`; 
        });
        c.innerHTML = h;
        window.App.markYear();
    },

    markYear: function() {
        const y = window.App.State.getState('nav.query.y');
        document.querySelectorAll('#years .yr').forEach(b => {
            const v = b.textContent.trim();
            const isAllTime = y === 'all' || !y;
            const targetStr = isAllTime ? 'Всё время' : String(y);
            b.classList.toggle('on', v === targetStr);
        });
    },

    showToast: function(text) {
        let el = document.getElementById('toast-msg');
        if (!el) { el = document.createElement('div'); el.id = 'toast-msg'; el.className = 'toast'; document.body.appendChild(el); }
        el.textContent = text; el.classList.add('show');
        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(() => { el.classList.remove('show'); }, 2000);
    },

    initGlobalHeatmapZoom: function() {
        const viewport = document.getElementById('heatmaps-wrapper');
        const content = document.getElementById('hm-zoom-content');
        if (!viewport || !content) return;

        viewport.style.overflow = 'hidden';
        viewport.style.touchAction = 'none'; 
        content.style.transformOrigin = '0 0';

        let scale = 1, translateX = 0, translateY = 0;
        let startScale = 1, startDist = 0, startMidX = 0, startMidY = 0, startTranslateX = 0, startTranslateY = 0;
        let isZooming = false, isPanning = false;

        const updateTransform = () => { content.style.transform = `translate3d(${translateX}px, ${translateY}px, 0) scale(${scale})`; };

        viewport.addEventListener('touchstart', (e) => {
            const t = e.touches;
            if (t.length === 1) { isPanning = true; isZooming = false; startMidX = t[0].clientX; startMidY = t[0].clientY; startTranslateX = translateX; startTranslateY = translateY; } 
            else if (t.length === 2) { isZooming = true; isPanning = false; startDist = Math.hypot(t[1].clientX - t[0].clientX, t[1].clientY - t[0].clientY); startScale = scale; startMidX = (t[0].clientX + t[1].clientX) / 2; startMidY = (t[0].clientY + t[1].clientY) / 2; startTranslateX = translateX; startTranslateY = translateY; }
        }, { passive: false });

        viewport.addEventListener('touchmove', (e) => {
            const t = e.touches; const rect = viewport.getBoundingClientRect();
            if (isZooming && t.length === 2) {
                e.preventDefault();
                const currentDist = Math.hypot(t[1].clientX - t[0].clientX, t[1].clientY - t[0].clientY);
                const newScale = Math.min(Math.max(1, (currentDist / startDist) * startScale), 4);
                const currentMidX = (t[0].clientX + t[1].clientX) / 2, currentMidY = (t[0].clientY + t[1].clientY) / 2;
                const mouseX = startMidX - rect.left, mouseY = startMidY - rect.top;
                const scaleRatio = newScale / startScale;
                translateX = currentMidX - rect.left - (mouseX - startTranslateX) * scaleRatio;
                translateY = currentMidY - rect.top - (mouseY - startTranslateY) * scaleRatio;
                scale = newScale; updateTransform();
            } else if (isPanning && t.length === 1) {
                e.preventDefault();
                const deltaX = t[0].clientX - startMidX, deltaY = t[0].clientY - startMidY;
                translateX = startTranslateX + deltaX; translateY = startTranslateY + deltaY;
                if (scale > 1) {
                    const minX = rect.width - (content.offsetWidth * scale), minY = rect.height - (content.offsetHeight * scale);
                    translateX = Math.min(0, Math.max(minX, translateX)); translateY = Math.min(0, Math.max(minY, translateY));
                } else { translateX = 0; translateY = 0; }
                updateTransform();
            }
        }, { passive: false });

        viewport.addEventListener('touchend', (e) => {
            if (e.touches.length === 0) {
                isZooming = false; isPanning = false;
                if (scale < 1.01) { scale = 1; translateX = 0; translateY = 0; content.style.transition = 'transform 0.3s cubic-bezier(0.25, 1, 0.5, 1)'; updateTransform(); setTimeout(() => content.style.transition = '', 300); }
            } else if (e.touches.length === 1) {
                isZooming = false; isPanning = true; startMidX = e.touches[0].clientX; startMidY = e.touches[0].clientY; startTranslateX = translateX; startTranslateY = translateY;
            }
        }, { passive: true });
    },

    renderHeatmap: function() {
        const el = document.getElementById('heatmaps-wrapper'); 
        el.innerHTML = '<div id="hm-zoom-content"></div>';
        const zoomContent = document.getElementById('hm-zoom-content');
        if (!D.heatmap?.length) { el.innerHTML = `<div class="empty"><div class="icon">${Icons.cal}</div>Нет данных</div>`; return; }
        
        const fragment = document.createDocumentFragment();
        const dayLabels = ['Пн', '', 'Ср', '', 'Пт', '', 'Вс'];
        
        D.heatmap.forEach((hItem, index) => {
            const yr = hItem.year; const data = hItem.data; const offset = (new Date(yr, 0, 1).getDay() + 6) % 7; const totalColumns = Math.ceil((offset + data.length) / 7);
            const block = document.createElement('div'); block.className = 'hm-zoom-area'; if (index > 0) block.style.marginTop = '20px';
            if (D.heatmap.length > 1) {
                const title = document.createElement('div'); title.style.fontSize = '13px'; title.style.fontWeight = '800'; title.style.color = 'var(--text-muted)'; title.style.marginBottom = '8px'; title.textContent = yr; block.appendChild(title);
            }
            const wrapper = document.createElement('div'); wrapper.className = 'hm-wrapper';
            const hm = document.createElement('div'); hm.className = 'hm'; hm.style.gridTemplateColumns = `max-content repeat(${totalColumns}, minmax(0, 1fr))`;
            
            dayLabels.forEach(lbl => { const l = document.createElement('div'); l.className = 'hc-label'; l.textContent = lbl; hm.appendChild(l); });
            for (let i = 0; i < offset; i++) { const d = document.createElement('div'); d.className = 'hc'; d.style.opacity = '0'; d.style.pointerEvents = 'none'; hm.appendChild(d); }
            
            let curr = new Date(yr, 0, 1);
            data.forEach(v => { 
                const d = document.createElement('div'); 
                const y = curr.getFullYear(), m = String(curr.getMonth() + 1).padStart(2, '0'), day = String(curr.getDate()).padStart(2, '0');
                const currStr = `${y}-${m}-${day}`, displayDate = `${day}.${m}.${y}`;
                d.className = 'hc clickable' + (v ? ' h' + v : ''); 
                if (v > 0) { d.setAttribute('onclick', `window.App.openHistoryLayer('day', '${displayDate}', null, '${currStr}')`); } else { d.setAttribute('onclick', `window.App.showToast('${displayDate}: просмотров нет')`); }
                hm.appendChild(d); curr.setDate(curr.getDate() + 1);
            });
            wrapper.appendChild(hm); block.appendChild(wrapper); fragment.appendChild(block);
        });
        zoomContent.appendChild(fragment); window.App.initGlobalHeatmapZoom();
    },

    fillList: function(id, items, ico, unit, categoryKey, mode = 'series') {
        const el = document.getElementById(id);
        if (!el) return;
        if (!items?.length) {
            el.innerHTML = '<div class="empty" style="padding: 20px 0;"><div class="icon" style="font-size:24px;">' + Icons.dash + '</div>Нет данных</div>';
            return;
        }
        let html = '';
        items.forEach((it, i) => {
            const cnt = it.count || it.views || 0, sub = it.sub || (it.shows ? `${it.shows} ${window.App.plural(it.shows, ['шоу', 'шоу', 'шоу'])}` : '');
            const lbl = Array.isArray(unit) ? `${cnt} ${window.App.plural(cnt, unit)}` : (unit ? `${cnt} ${unit}` : cnt);
            const delay = (i + 1) * 0.05;
            
            const safeName = it.name.replace(/'/g, "\\'").replace(/"/g, "&quot;");
            let visual = '';
            if (it.photo_url) {
                const fb = it.fallback_photo_url ? `'${it.fallback_photo_url}'` : 'null';
                visual = `<img src="${it.photo_url}" style="width:clamp(24px, 6vw, 32px);height:clamp(24px, 6vw, 32px);border-radius:50%;object-fit:cover;margin-right:6px;vertical-align:middle;display:inline-block;" 
                    onerror="window.App.handleImgErr(this, ${fb}, '${safeName}')"
                    onload="window.handleKpPlaceholder(this, '${safeName}')">`;
            } else if (it.emoji) {
                visual = `<span style="font-size:clamp(18px,5vw,22px);line-height:1;margin-right:6px;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.1))">${it.emoji}</span>`;
            } else if (ico) {
                visual = `<div class="icon" style="color:var(--text-muted);display:inline-block;vertical-align:middle;margin-right:6px;">${ico}</div>`;
            }

            const histKey = ['actors', 'directors', 'writers'].includes(categoryKey) ? `${categoryKey}_${mode}` : categoryKey;
            D[histKey] = items;

            html += `<div class="li li-clickable anim-list-item clickable" onclick="window.App.openHistoryLayer('filter', '${safeName}', null, null, '${histKey}', ${i})" style="animation-delay:${delay}s"><div class="li-l"><span class="li-rank">${i+1}</span><div><div class="li-name">${visual} ${it.name}</div>${sub?`<div class="li-sub">${sub}</div>`:''}</div></div><span class="li-r" style="color:var(--info)">${lbl}</span></div>`;
        });
        el.innerHTML = html;
    },

    fillBinges: function() {
        const el = document.getElementById('binges-list');
        if (!D.binges?.length) return;
        let html = '';
        D.binges.forEach((b, i) => {
            const delay = (i + 1) * 0.05, safeTitle = b.show_title.replace(/'/g, "\\'").replace(/"/g, "&quot;");
            const posterHtml = b.poster_url ? `<img src="${b.poster_url}" style="width:clamp(36px, 10vw, 44px);height:clamp(54px, 15vw, 66px);border-radius:6px;object-fit:cover;flex-shrink:0;background:var(--bg-input);border:1px solid var(--border);box-shadow:0 2px 6px rgba(0,0,0,0.1);" onerror="this.style.display='none'">` : `<div style="width:clamp(36px, 10vw, 44px);height:clamp(54px, 15vw, 66px);border-radius:6px;flex-shrink:0;background:var(--bg-input);border:1px solid var(--border);"></div>`;
            html += `<div class="li li-clickable anim-list-item clickable" style="animation-delay:${delay}s" onclick="window.App.openHistoryLayer('binge', '${safeTitle}', ${b.show_id}, '${b.date}')"><div class="li-l">${posterHtml}<div><div class="li-name">${b.show_title}</div><div class="li-sub">${b.date}</div></div></div><span class="li-r" style="color:var(--info)">${b.count} ${window.App.plural(b.count, ['эпизод', 'эпизода', 'эпизодов'])}</span></div>`;
        });
        el.innerHTML = html;
    },

    getCtxGradient: function(ctx, colorStart, colorEnd) {
        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, colorStart);
        gradient.addColorStop(1, colorEnd);
        return gradient;
    },

    renderMonthly: function() {
        const canvas = document.getElementById('c-monthly'), ctx = canvas.getContext('2d');
        if (chM) chM.destroy();
        const ch = D.monthly_chart; if (!ch?.labels?.length) return;
        const c = window.App.cc();
        let fillGradient = window.App.getCtxGradient(ctx, isDark?'rgba(35, 134, 54, 0.4)':'rgba(46, 160, 67, 0.3)', 'rgba(35, 134, 54, 0.0)'), lineGradient = ctx.createLinearGradient(0, 0, canvas.width || 400, 0);
        lineGradient.addColorStop(0, '#2ea043'); lineGradient.addColorStop(1, '#3fb950');
        
        let labelFontSize = fSizeAx;
        if (ch.labels.length > 12) labelFontSize = Math.max(8, fSizeAx - 2);

        chM = new Chart(ctx, { 
            type:'line', 
            data:{ labels:ch.labels, datasets:[{ label: ' Просмотры', data: ch.views, backgroundColor: fillGradient, borderColor: lineGradient, borderWidth: 3, tension: 0.4, fill: true, yAxisID: 'y', pointBackgroundColor: isDark ? '#0d1117' : '#ffffff', pointBorderColor: '#3fb950', pointBorderWidth: 2, pointRadius: 4, pointHoverRadius: 6 }, { label: ' Часы', data: ch.hours, backgroundColor: 'transparent', borderColor: c.i, borderWidth: 2, borderDash: [5, 5], tension: 0.4, fill: false, yAxisID: 'y1', pointBackgroundColor: isDark ? '#0d1117' : '#ffffff', pointBorderColor: c.i, pointRadius: 0, pointHoverRadius: 5 }] },
            options:{ responsive:true, maintainAspectRatio:false, animation: { duration: 1500, easing: 'easeOutQuart' }, plugins:{ legend: { display: true, position: 'top', labels: { color: c.t, usePointStyle: true, boxWidth: 8, padding: 15, font: { size: fSizeAx, family: 'system-ui' } } }, tooltip: { backgroundColor: isDark ? 'rgba(22, 27, 34, 0.95)' : 'rgba(255, 255, 255, 0.95)', titleColor: isDark ? '#f0f6fc' : '#1f2328', bodyColor: isDark ? '#8b949e' : '#59636e', borderColor: c.b, borderWidth: 1, padding: 12, cornerRadius: 8, displayColors: true, boxPadding: 6, bodySpacing: 8, titleSpacing: 10 } }, interaction: { mode: 'index', intersect: false }, scales:{ x:{ ticks:{color:c.t, font:{size:labelFontSize}, maxRotation: 45, minRotation: 0}, grid:{display:false} }, y:{ type: 'linear', display: true, position: 'left', ticks:{color:c.a,font:{size:fSizeAx}}, grid:{color:c.g}, beginAtZero:true }, y1: { type: 'linear', display: true, position: 'right', ticks:{color:c.i,font:{size:fSizeAx}}, grid:{drawOnChartArea: false}, beginAtZero:true } } } 
        });
    },

    renderWeekday: function() {
        const canvas = document.getElementById('c-weekday'), ctx = canvas.getContext('2d');
        if (chW) chW.destroy();
        const ch = D.weekday_chart; if (!ch?.labels?.length) return;
        const c = window.App.cc(), totalViews = ch.data.reduce((a, b) => a + b, 0);
        let barGradient = window.App.getCtxGradient(ctx, '#2ea043', '#238636'), weGradient = window.App.getCtxGradient(ctx, '#388bfd', '#1f6feb');
        chW = new Chart(ctx, { 
            type: 'bar', 
            data: { labels: ch.labels, datasets: [{ data: ch.data, backgroundColor: ch.data.map((_, i) => i >= 5 ? weGradient : barGradient), hoverBackgroundColor: ch.data.map((_, i) => i >= 5 ? '#60a5fa' : '#39d353'), borderRadius: 8, borderSkipped: false, borderWidth: 0, hoverBorderWidth: 0 }] },
            options: { 
                responsive: true, maintainAspectRatio: false, 
                animation: { duration: 1000, easing: 'easeOutBack', delay: (context) => context.type === 'data' && context.mode === 'default' && !context.active ? context.dataIndex * 100 : 0 }, 
                onClick: (event, activeElements) => {
                    if (activeElements.length > 0) {
                        const idx = activeElements[0].index;
                        window.App.openHistoryLayer('weekday', ch.labels[idx], null, null, null, idx);
                    }
                },
                onHover: (event, activeElements) => { event.native.target.style.cursor = activeElements.length ? 'pointer' : 'default'; },
                plugins: { legend: { display: false }, tooltip: { backgroundColor: isDark ? 'rgba(22, 27, 34, 0.95)' : 'rgba(255, 255, 255, 0.95)', titleColor: isDark ? '#f0f6fc' : '#1f2328', bodyColor: isDark ? '#8b949e' : '#59636e', borderColor: c.b, borderWidth: 1, cornerRadius: 10, padding: 12, displayColors: false, callbacks: { label: (context) => { const val = context.parsed.y; const pct = totalViews > 0 ? Math.round((val / totalViews) * 100) : 0; return ` ${val} ${window.App.plural(val, ['просмотр', 'просмотра', 'просмотров'])} (${pct}%)`; } } } }, 
                scales: { x: { ticks: { color: c.t, font: { size: fSizeAx, weight: '600' } }, grid: { display: false } }, y: { ticks: { color: c.t, font: { size: fSizeAx }, precision: 0 }, grid: { color: c.g }, beginAtZero: true, border: { display: false } } } 
            } 
        });
    },

    renderDonut: function(canvasId, legendId, sourceData, dataKey, totalMinutesWatched) {
        const canvas = document.getElementById(canvasId); if (!canvas) return;
        const ctx = canvas.getContext('2d'), legendEl = document.getElementById(legendId);
        if (chG[canvasId]) chG[canvasId].destroy(); if (!sourceData?.length) return;
        const c = window.App.cc();
        let top = JSON.parse(JSON.stringify(sourceData)).slice(0, 10);
        const totalMinutesSum = sourceData.reduce((acc, g) => acc + g.minutes, 0), topMinutes = top.reduce((acc, g) => acc + g.minutes, 0);
        if (totalMinutesSum > topMinutes) { const others = sourceData.slice(10); top.push({ name: 'Другие', minutes: totalMinutesSum - topMinutes, count: 0, show_ids: [...new Set(others.flatMap(g => g.show_ids || []))] }); }
        const totalHours = Math.floor(totalMinutesWatched / 60);
        const pal = ['#2ea043', '#388bfd', '#f85149', '#d29922', '#a371f7', '#1abc9c', '#e67e22', '#9b59b6', '#00d2ff', '#16a085', '#27ae60', '#2980b9'];
        const values = top.map(g => (g.minutes / totalMinutesSum) * 100), percents = values.map(v => Math.round(v));
        const centerTextPlugin = { id: 'centerText', afterDraw: (chart) => { const { ctx, chartArea: { top, height, left, width } } = chart; ctx.save(); const centerX = left + width / 2, centerY = top + height / 2; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.font = '900 34px system-ui'; ctx.fillStyle = c.t; ctx.fillText(totalHours, centerX, centerY - 8); ctx.font = 'bold 10px system-ui'; ctx.fillStyle = isDark ? '#6e7681' : '#8c959f'; ctx.letterSpacing = '1px'; ctx.fillText('ЧАСОВ ВСЕГО', centerX, centerY + 22); ctx.restore(); } };
        chG[canvasId] = new Chart(ctx, { 
            type: 'doughnut', plugins: [ChartDataLabels, centerTextPlugin],
            data: { labels: top.map(g => g.name), datasets: [{ data: top.map(g => g.minutes), backgroundColor: top.map((_, i) => pal[i % pal.length]), borderWidth: 0, hoverOffset: 15, borderRadius: 6, spacing: top.length === 1 ? 0 : 3, weight: 1 }] },
            options: { responsive: true, maintainAspectRatio: false, cutout: '50%', layout: { padding: 15 }, animation: { animateRotate: true, duration: 1200, easing: 'easeOutQuart' }, onHover: (event, activeElements) => { event.native.target.style.cursor = activeElements.length ? 'pointer' : 'default'; }, onClick: (event, activeElements) => { if (activeElements.length > 0) window.App.openHistoryLayer('filter', top[activeElements[0].index].name, null, null, dataKey, activeElements[0].index); }, plugins: { datalabels: { color: '#fff', font: { weight: '800', size: 10 }, formatter: (value, context) => percents[context.dataIndex] > 5 ? percents[context.dataIndex] + '%' : '', display: 'auto' }, tooltip: { enabled: true, callbacks: { label: (context) => { const val = context.parsed, h = Math.floor(val/60), m = val%60; return ` ${h}ч ${m}м (${percents[context.dataIndex]}%)`; } } }, legend: { display: false } } } 
        });
        D[dataKey] = top;
        legendEl.innerHTML = top.map((g, i) => `<div class="legend-item" onclick="window.App.openHistoryLayer('filter', '${g.name.replace(/'/g, "\\'")}', null, null, '${dataKey}', ${i})" onmouseenter="window.App.highlightSegment('${canvasId}', ${i}, true)" onmouseleave="window.App.highlightSegment('${canvasId}', ${i}, false)"><div class="legend-dot" style="background:${pal[i % pal.length]}"></div><div class="legend-name">${g.name}</div><div class="legend-val">${Math.floor(g.minutes / 60) > 0 ? `${Math.floor(g.minutes / 60)}ч ${g.minutes % 60}м` : `${g.minutes % 60}м`} (${percents[i]}%)</div></div>`).join('');
    },

    highlightSegment: function(canvasId, index, active) {
        const chart = chG[canvasId];
        if (!chart) return;

        if (active) {
            chart.setActiveElements([{ datasetIndex: 0, index }]);
            chart.tooltip.setActiveElements(
                [{ datasetIndex: 0, index }],
                { x: 0, y: 0 }
            );
        } else {
            chart.setActiveElements([]);
            chart.tooltip.setActiveElements([], { x: 0, y: 0 });
        }

        chart.update();
    },

    openHistoryLayer: function(type, title, extraId, extraDate, extraKey, extraIndex, fromRouter = false) {
        curHistType = type;
        isHistoryEditMode = false;
        
        if (type === 'all') { 
            curHistData = [...D.history_movies, ...D.history_episodes].sort((a, b) => b.view_date.localeCompare(a.view_date)); 
        } 
        else if (type === 'casino') {
            curHistData = D.casino_history;
        }
        else if (type === 'day') { 
            curHistData = [...D.history_movies, ...D.history_episodes].filter(i => i.view_date === extraDate); 
        } 
        else if (type === 'binge') { 
            curHistData = D.history_episodes.filter(i => i.show_id === extraId && i.view_date === extraDate).sort((a, b) => { 
                if (a.season_number !== b.season_number) return a.season_number - b.season_number; 
                return a.episode_number - b.episode_number; 
            }); 
        } 
        else if (type === 'ratings') { 
            curHistData = D.ratings.history; 
        } 
        else if (type === 'movies') { 
            curHistData = D.history_movies; 
        } 
        else if (type === 'episodes') { 
            curHistData = D.history_episodes; 
        } 
        else if (type === 'wishlist_watched') {
            curHistData = D.wishlist_watched_items || [];
        }
        else if (type === 'show_history') {
            curHistData = extraKey; 
        }
        else if (type === 'filter') { 
            const sourcePool = extraKey.startsWith('group') ? [...D.group.history_movies, ...D.group.history_episodes] : [...D.history_movies, ...D.history_episodes]; 
            const allowedIds = D[extraKey][extraIndex].show_ids || []; 
            curHistData = sourcePool.filter(i => allowedIds.includes(i.show_id)).sort((a, b) => b.view_date.localeCompare(a.view_date)); 
        } 
        else if (type === 'group_member') { 
            const member = D.group.members[extraIndex]; 
            curHistData = [...D.group.history_movies, ...D.group.history_episodes].filter(item => item.user_ids.includes(member.id)).sort((a, b) => b.view_date.localeCompare(a.view_date)); 
        } 
        else if (type === 'weekday') { 
            curHistData = [...D.history_movies, ...D.history_episodes].filter(item => { 
                const date = new Date(item.view_date); 
                const jsDay = date.getDay(); 
                return (jsDay === 0 ? 6 : jsDay - 1) === extraIndex; 
            }).sort((a, b) => b.view_date.localeCompare(a.view_date)); 
        } 
        else if (type === 'rating_filter') { 
            curHistData = D.ratings.history.filter(item => { 
                let b = Math.floor(item.rating); 
                if (b < 1) b = 1; 
                return b === extraIndex; 
            }); 
            curHistType = 'ratings'; 
        }

        let grouping = 'none';
        const len = curHistData.length;
        if (len >= 300) grouping = 'month';
        else if (len >= 50) grouping = 'year';

        let headerSectionHtml = '';
        const isPersonCategory = extraKey && typeof extraKey === 'string' && (extraKey.startsWith('actors') || extraKey.startsWith('directors') || extraKey.startsWith('writers'));
        
        if (type === 'filter' && isPersonCategory) {
            const p = D[extraKey][extraIndex];
            const safeName = p.name.replace(/'/g, "\\'");
            const fb = p.fallback_photo_url ? `'${p.fallback_photo_url}'` : 'null';
            const imgHtml = p.photo_url 
                ? `<img src="${p.photo_url}" class="person-avatar" style="width:60px; height:60px; object-fit:cover; flex-shrink:0;" onerror="window.App.handleImgErr(this, ${fb}, '${safeName}')">`
                : `<div class="person-avatar" style="width:60px; height:60px; flex-shrink:0; font-size:24px;">${p.name.charAt(0)}</div>`;
            
            let profLabel = '';
            if (extraKey.startsWith('actors')) profLabel = 'Актёр';
            else if (extraKey.startsWith('directors')) profLabel = 'Режиссёр';
            else if (extraKey.startsWith('writers')) profLabel = 'Сценарист';
            
            headerSectionHtml = `
                <div class="card anim-item clickable" onclick="window.App.openCollectionLayer('person', ${p.id}, '${safeName}')" style="display:flex; align-items:center; gap:16px; margin:12px 16px; padding:16px; border-radius:20px; background:var(--bg-card); box-shadow:var(--shadow-sm); position:relative;">
                    ${imgHtml}
                    <div style="min-width:0; flex:1;">
                        <div style="font-size:20px; font-weight:900; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; letter-spacing:-0.5px;">${p.name}</div>
                        <div style="font-size:13px; color:var(--text-muted); font-weight:600; margin-top:4px; letter-spacing:0.3px;">${profLabel}</div>
                    </div>
                    <div style="color:var(--text-muted); opacity:0.5;">
                        <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none"><path d="M9 18l6-6-6-6"/></svg>
                    </div>
                </div>`;
        } else if (type === 'filter' && extraKey === 'countries') {
            const c = D[extraKey][extraIndex];
            const flag = c.emoji ? `<span style="margin-right:10px; font-size: 1.2em;">${c.emoji}</span>` : '';
            headerSectionHtml = `<div class="label"><div class="icon" style="color:var(--info)">${Icons.globe}</div>${flag}${c.name}</div>`;
        } else if (type === 'filter' && (extraKey === 'genres_top' || extraKey === 'group_genres_top')) {
            headerSectionHtml = `<div class="label"><div class="icon" style="color:var(--info)">${Icons.masks}</div>Жанр: ${title}</div>`;
        }

        const deleteBtnVisible = (!isSharedMode && type !== 'ratings');
        const deleteToggleBtn = deleteBtnVisible ? `<button class="wl-edit-btn" id="hist-del-toggle" onclick="window.App.toggleHistoryEditMode()">${Icons.trash}</button>` : '';

        const headerHtml = `
        <div class="layer-header" id="layer-header-node">
            <div style="flex-shrink: 0;">
                <button onclick="window.App.popLayer()" class="tab clickable" style="background:var(--bg-input); color:var(--text-primary); margin:0; display:inline-flex; border:none; padding:8px 12px; flex-shrink:0;">
                    <svg viewBox="0 0 24 24" width="18" height="18" style="margin-right:4px;"><path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg> Назад
                </button>
            </div>
            <div class="layer-header-center" style="flex: 1; min-width: 0; max-width: 60%;">
                <div class="layer-title-main">${title}</div>
                <div class="layer-group-label" id="sticky-group-text"></div>
            </div>
            <div style="display: flex; align-items: center; gap: 8px; flex-shrink: 0; justify-content: flex-end;">
                ${deleteToggleBtn}
                <div class="view-toggle" style="margin:0; padding:2px; flex-shrink: 0;">
                    <button class="vt-btn ${viewMode === 'grid' ? 'active' : ''}" onclick="window.App.setViewModeLayer('grid')">${Icons.grid}</button>
                    <button class="vt-btn ${viewMode === 'list' ? 'active' : ''}" onclick="window.App.setViewModeLayer('list')">${Icons.list}</button>
                </div>
            </div>
        </div>`;

        const bodyHtml = `
            ${headerHtml}
            ${headerSectionHtml}
            <div id="layer-hist-container" style="padding: 16px;"></div>
            <div id="layer-hist-sentinel" style="height: 100px; width: 100%; margin-top: -100px; pointer-events: none;"></div>
        `;

        window.App.pushLayer(bodyHtml, { 
            type: 'history', 
            htype: type,
            title: title,
            extraId: extraId,
            extraDate: extraDate,
            extraKey: extraKey,
            extraIndex: extraIndex,
            grouping: grouping,
            lastGroupKey: null,
            fromRouter: fromRouter
        });
        
        currentHistoryOffset = 0;
        
        const topLayer = viewStack[viewStack.length - 1];
        
        const mainTitleEl = topLayer.el.querySelector('.layer-title-main');
        if (mainTitleEl) {
            setTimeout(() => {
                window.App.fitText(mainTitleEl);
            }, 50);
        }

        if (historyObserver) historyObserver.disconnect();
        historyObserver = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting) window.App.renderHistoryBatchLayer();
        }, { root: topLayer.el, rootMargin: '1000px' });
        
        const sentinel = topLayer.el.querySelector('#layer-hist-sentinel');
        if (sentinel) historyObserver.observe(sentinel);

        window.App.renderHistoryBatchLayer();

        if (grouping !== 'none') {
            window.App.initStickyGroupObserver();
        }
    },

    setViewModeLayer: function(mode) {
        viewMode = mode;
        localStorage.setItem('kp_view_mode', mode);

        const top = viewStack[viewStack.length - 1];

        if (top && top.context.type === 'history') {
            const btns = top.el.querySelectorAll('.vt-btn');

            btns[0].classList.toggle('active', mode === 'grid');
            btns[1].classList.toggle('active', mode === 'list');

            currentHistoryOffset = 0;

            top.el.querySelector('#layer-hist-container').innerHTML = '';

            if (historyObserver) historyObserver.disconnect();

            window.App.renderHistoryBatchLayer();
        }
    },

    getHistoryItemHtml: function(item, idx, type, mode) {
        const sid = item.show_id;
        const delay = (idx % 100) * 0.05;
        const animClass = 'anim-item';
        const style = `style="animation-delay: ${delay}s"`;

        const title = item.show__title || item.title;
        const originalTitle = item.show__original_title || item.original_title;
        const itemYear = item.show__year || item.year;
        const displayDate = item.view_date || item.date;
        const rating = item.user_rating || item.rating;
        
        const sNum = item.season_number || item.season;
        const eNum = item.episode_number || item.episode;

        let deleteBtn = '';
        if (!isSharedMode && type !== 'ratings' && type !== 'wishlist_watched' && type !== 'casino') {
            const itemData = JSON.stringify({ view_history_id: item.id }).replace(/"/g, '&quot;');
            deleteBtn = `<div class="wl-delete-badge" style="background:var(--danger);" 
                onclick="event.stopPropagation(); window.App.removeHistoryItem(this, ${itemData})">${Icons.minus}</div>`;
        } else if (!isSharedMode && type === 'ratings') {
            const rateData = JSON.stringify({ 
                show_id: sid, 
                season: sNum, 
                episode: eNum 
            }).replace(/"/g, '&quot;');
            deleteBtn = `<div class="wl-delete-badge" style="background:var(--danger);" 
                onclick="event.stopPropagation(); window.App.removeRatingItem(this, ${rateData})">${Icons.minus}</div>`;
        } else if (type === 'wishlist_watched') {
            deleteBtn = `<div class="wl-delete-badge" style="background:var(--danger);" 
                onclick="event.stopPropagation(); window.App.removeWlStatItem(${item.wl_item_id}, this.closest('.grid-item-wrap') || this.closest('.hist-item'))">${Icons.minus}</div>`;
        }

        if (mode === 'list') {
            const poster = item.poster_url ? `<img src="${item.poster_url}" class="hist-poster" loading="lazy">` : `<div class="hist-poster"></div>`;
            
            let metaHtml = '';
            if (sNum > 0) metaHtml += `<span class="hist-badge">s${sNum}e${eNum.toString().padStart(2,'0')}</span>`;
            if (rating) metaHtml += `<span class="rating-badge">${Icons.star}${rating}</span>`;
            
            const viewers = (item.user_names && item.user_names.length > 1) ? `<div class="li-sub" style="font-size:11px;">👥 ${item.user_names.join(', ')}</div>` : '';
            const origTitleHtml = (originalTitle && originalTitle !== title) ? `<div class="hist-orig">${originalTitle}</div>` : '';

            return `
                <div class="hist-item clickable ${animClass}" ${style} data-id="${item.id}" onclick="if(!isHistoryEditMode) window.App.openShowLayer(${sid})">
                    ${deleteBtn}
                    ${poster}
                    <div class="hist-info">
                        <div class="hist-title">${title}</div>
                        ${origTitleHtml}
                        <div class="hist-meta">${metaHtml}<span>${displayDate}</span></div>
                        ${viewers}
                    </div>
                </div>`;
        } else {
            const mediumPoster = item.poster_url ? item.poster_url.replace('/small/', '/medium/') : '';
            const posterHtml = mediumPoster ? `<img src="${mediumPoster}" class="grid-poster" loading="lazy">` : '<div class="grid-poster"></div>';
            const yearHtml = itemYear ? `<div class="grid-year">${itemYear}</div>` : '';
            
            let badgesHtml = '';
            if (sNum > 0) badgesHtml += `<span class="hist-badge" style="background:rgba(0,0,0,0.6);border:none;">s${sNum}e${eNum.toString().padStart(2,'0')}</span>`;
            if (rating) badgesHtml += `<span class="rating-badge" style="background:rgba(0,0,0,0.6);border:none;">${Icons.star}${rating}</span>`;
            
            let usersHtml = '';
            if (item.user_names && item.user_names.length > 0) {
                let avatars = '';
                for (let i = 0; i < item.user_names.length; i++) {
                    const name = item.user_names[i] || '?';
                    const photo = item.user_photos && item.user_photos[i];
                    const userId = (item.user_ids && item.user_ids[i]);
                    if (photo) avatars += `<img src="${photo}" class="grid-user-avatar">`;
                    else avatars += `<div class="grid-user-avatar" style="background:${window.App.getUserColor(userId || 0)};">${isSharedMode && userId > 0 ? userId : name.charAt(0).toUpperCase()}</div>`;
                }
                usersHtml = `<div class="grid-users">${avatars}</div>`;
            }

            return `
                <div class="grid-item-wrap ${animClass}" ${style} data-id="${item.id}" onclick="if(!isHistoryEditMode) window.App.openShowLayer(${sid})">
                    ${deleteBtn}
                    <div class="grid-item">
                        ${posterHtml}${yearHtml}
                        <div class="grid-badges">${badgesHtml}</div>
                        <div class="grid-overlay">${usersHtml}<div class="grid-date">${displayDate}</div></div>
                    </div>
                    <div class="grid-below-title">${title}</div>
                </div>`;
        }
    },

    renderHistoryBatchLayer: function() {
        // 1. Проверки на вход
        if (isRenderingBatch || currentHistoryOffset >= curHistData.length) return;
        
        const topLayer = viewStack[viewStack.length - 1];
        if (!topLayer || topLayer.context.type !== 'history') return;
        
        const container = topLayer.el.querySelector('#layer-hist-container');
        if (!container) return;

        isRenderingBatch = true;
        
        // 2. Подготовка данных
        const start = currentHistoryOffset;
        const end = start + historyBatchSize;
        const batch = curHistData.slice(start, end);
        currentHistoryOffset = end; 

        if (curHistData.length === 0) {
            container.innerHTML = `<div class="empty"><div class="icon">${Icons.dash}</div>Нет данных</div>`;
            isRenderingBatch = false;
            return;
        }

        // 3. Генерация HTML
        const grouping = topLayer.context.grouping;
        let html = '';
        
        batch.forEach((item, idx) => {
            if (grouping !== 'none') {
                const dateStr = item.view_date || item.date;
                if (dateStr) {
                    const dateObj = new Date(dateStr);
                    let groupKey = '';
                    if (grouping === 'month') {
                        groupKey = `${RU_MONTHS[dateObj.getMonth()]} ${dateObj.getFullYear()}`;
                    } else if (grouping === 'year') {
                        groupKey = `${dateObj.getFullYear()}`;
                    }

                    if (groupKey && groupKey !== topLayer.context.lastGroupKey) {
                        topLayer.context.lastGroupKey = groupKey;
                        html += `
                            <div class="hist-group-divider anim-item" data-label="${groupKey}">
                                <span class="hist-group-divider-text">${groupKey}</span>
                            </div>`;
                    }
                }
            }
            html += window.App.getHistoryItemHtml(item, start + idx, curHistType, viewMode);
        });
        
        // 4. Вставка в DOM
        if (start === 0) {
            const wrapClass = viewMode === 'list' ? 'card' : 'hist-grid';
            const wrapStyle = viewMode === 'list' ? 'margin:0; padding:0; border:none; background:transparent;' : '';
            container.innerHTML = `<div class="${wrapClass}" style="${wrapStyle}">${html}</div>`;
        } else {
            const target = container.querySelector('.card') || container.querySelector('.hist-grid');
            if (target) target.insertAdjacentHTML('beforeend', html);
        }

        // 5. Финализация (один раз в следующем кадре)
        requestAnimationFrame(() => {
            // Подгоняем размеры заголовков
            window.App.fitAll('.grid-below-title', container);
            window.App.fitAll('.hist-title', container);

            // Если есть группировка, вызываем scroll для корректного отображения "липких" заголовков
            if (grouping !== 'none') {
                topLayer.el.dispatchEvent(new Event('scroll'));
            }

            // Отключаем обсервер, если данные кончились
            if (currentHistoryOffset >= curHistData.length && historyObserver) {
                historyObserver.disconnect();
            }

            // Снимаем блокировку рендеринга строго в конце
            isRenderingBatch = false;
        });
    },

    initStickyGroupObserver: function() {
        const topLayer = viewStack[viewStack.length - 1];
        if (!topLayer) return;

        const header = topLayer.el.querySelector('#layer-header-node');
        const label = topLayer.el.querySelector('#sticky-group-text');
        const container = topLayer.el; 

        const updateStickyHeader = () => {
            const dividers = Array.from(container.querySelectorAll('.hist-group-divider'));
            const headerHeight = 64; 
            const scrollTop = container.scrollTop;

            let activeDivider = null;

            for (let i = dividers.length - 1; i >= 0; i--) {
                const div = dividers[i];
                if (div.offsetTop <= scrollTop + headerHeight + 5) {
                    activeDivider = div;
                    break;
                }
            }

            if (activeDivider) {
                const groupText = activeDivider.dataset.label;
                if (label.textContent !== groupText) {
                    label.textContent = groupText;
                    window.App.fitText(label);
                }

                const isDividerUnderHeader = activeDivider.offsetTop <= scrollTop + (headerHeight / 2);
                header.classList.toggle('has-group', isDividerUnderHeader);
            } else {
                header.classList.remove('has-group');
            }
        };

        container.addEventListener('scroll', updateStickyHeader, { passive: true });
        updateStickyHeader();
    },

    openCollectionLayer: async function(type, id, titleFallback, fromRouter = false) {
        document.getElementById('loader').classList.remove('hidden');
        document.getElementById('loader').style.opacity = '1';

        try {
            const r = await fetch(`/api/webapp/collection/${type}/${id}/?init_data=${encodeURIComponent(tg?.initData || '')}`);
            if (!r.ok) throw new Error('Not found');
            const data = await r.json();

            let gridHtml = data.items.map(item => {
                const mediumPoster = item.poster_url || '';
                const posterHtml = mediumPoster ? `<img src="${mediumPoster}" class="grid-poster" loading="lazy">` : '<div class="grid-poster"></div>';
                
                let ratingBadge = '';
                if (item.user_rating) {
                    ratingBadge = `<div class="rating-badge" style="position:absolute; top:8px; left:8px; z-index:5; background:rgba(0,0,0,0.6); border:1px solid rgba(255,255,255,0.1); color:var(--accent);">${Icons.star}${item.user_rating}</div>`;
                }

                return `
                <div class="grid-item-wrap anim-item" onclick="window.App.openShowLayer(${item.id})">
                    <div class="grid-item">
                        ${posterHtml}
                        ${ratingBadge}
                        ${item.year ? `<div class="grid-year">${item.year}</div>` : ''}
                    </div>
                    <div class="grid-below-title">${item.title}</div>
                </div>`;
            }).join('');

            if (data.items.length === 0) {
                gridHtml = `<div class="empty" style="grid-column: 1/-1"><div class="icon">${Icons.film}</div>Пусто</div>`;
            }

            let headerSectionHtml = '';
            if (data.person_info) {
                const p = data.person_info;
                const fb = p.fallback_photo_url ? `'${p.fallback_photo_url}'` : 'null';
                const safeName = titleFallback.replace(/'/g, "\\'");
                const imgHtml = p.photo_url 
                    ? `<img src="${p.photo_url}" class="person-avatar" style="width:60px; height:60px; object-fit:cover; flex-shrink:0;" 
                        onerror="window.App.handleImgErr(this, ${fb}, '${safeName}')"
                        onload="window.handleKpPlaceholder(this, '${safeName}')">`
                    : `<div class="person-avatar" style="width:60px; height:60px; flex-shrink:0;">${window.App.Icons.person_placeholder}</div>`;
                
                const profsHtml = p.professions && p.professions.length > 0 
                    ? `<div style="font-size:13px; color:var(--text-muted); font-weight:600; margin-top:4px; letter-spacing:0.3px;">${p.professions.join(' · ')}</div>`
                    : '';

                headerSectionHtml = `
                    <div class="card anim-item" style="display:flex; align-items:center; gap:16px; margin:12px 16px; padding:16px; border-radius:20px; background:var(--bg-card); box-shadow:var(--shadow-sm);">
                        ${imgHtml}
                        <div style="min-width:0; flex:1;">
                            <div style="font-size:20px; font-weight:900; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; letter-spacing:-0.5px;">${titleFallback}</div>
                            ${profsHtml}
                        </div>
                    </div>`;
            } else {
                headerSectionHtml = `<div class="label"><div class="icon" style="color:var(--info)">${window.App.Icons.star}</div>${data.title || titleFallback}</div>`;
            }

            const html = `
                ${window.App.getLayerHeader(data.title || titleFallback)}
                ${headerSectionHtml}
                <div class="hist-grid" style="padding: 0 16px;">
                    ${gridHtml}
                </div>
            `;

            window.App.pushLayer(html, { 
                type: 'collection', 
                ctype: type, 
                itemId: id,
                titleFallback: titleFallback,
                fromRouter: fromRouter 
            });
            return true;
        } catch (e) {
            window.App.showToast('Не удалось загрузить данные коллекции');
            return false;
        } finally {
            window.App.hideLoader();
        }
    },

    pushLayer: function(htmlContent, contextData = {}) {
        const isSync = contextData.fromRouter || false;

        if (contextData.replace && viewStack.length > 0) {
            const top = viewStack[viewStack.length - 1];
            top.el.innerHTML = htmlContent;
            top.context = contextData;
            top.el.scrollTop = 0;
            
            const stackData = viewStack.map(item => item.context);
            window.App.State.setState('nav.layerStack', stackData);
            return;
        }

        const layer = document.createElement('div');
        layer.className = 'layer';
        layer.innerHTML = htmlContent;
        document.getElementById('dynamic-layers').appendChild(layer);
        
        if (viewStack.length > 0) {
            viewStack[viewStack.length - 1].el.style.display = 'none';
        }
        
        document.getElementById('bottom-nav').style.display = 'none';

        viewStack.push({ el: layer, context: contextData });
        
        const stackData = viewStack.map(item => item.context);
        window.App.State.setState('nav.layerStack', stackData);

        if (tg?.BackButton) { 
            tg.BackButton.show(); 
            tg.BackButton.onClick(window.App.popLayer); 
        }

        if (!isSync) {
            window.App.Router.updateUrl();
        }
    },

    popLayer: function() {
        if (viewStack.length > 0) {
            history.back();
        }
    },

    getLayerHeader: function(title) {
        return `
        <div class="layer-header">
            <div>
                <button onclick="window.App.popLayer()" class="tab clickable" style="background:var(--bg-input); color:var(--text-primary); margin:0; display:inline-flex; border:none; padding:8px 16px; margin-right: 12px;">
                    <svg viewBox="0 0 24 24" width="18" height="18" style="margin-right:6px;"><path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg> Назад
                </button>
            </div>
            <div class="layer-header-center">
                <div class="layer-title-main">${title}</div>
            </div>
            <div></div>
        </div>`;
    },

    renderGroup: function() {
        const el = document.getElementById('group-root');
        if (!D.group) { 
            el.innerHTML = `<div class="card hoverable"><div class="empty"><div class="icon" style="font-size:clamp(36px, 10vw, 48px);line-height:1;color:var(--text-muted)">${window.App.Icons.users}</div>Вы не состоите в группе</div></div>`; 
            return; 
        }
        
        const g = D.group, p = D.summary;
        const subjectLabel = isSharedMode ? D.meta.name : 'Вы';
        
        const rows = [ 
            { lb:'Просмотры', i:window.App.Icons.tv, y:p.total_views, gv:g.total_views }, 
            { lb:'Эпизоды', i:window.App.Icons.film, y:p.total_episodes, gv:g.total_episodes }, 
            { lb:'Фильмы', i:window.App.Icons.time, y:p.total_movies, gv:g.total_movies }, 
            { lb:'Уникальных', i:window.App.Icons.star, y:p.unique_shows, gv:g.unique_shows } 
        ];
        
        let hasDiff = false;
        const cmpH = rows.map((r, idx) => { 
            const d = r.y - r.gv; 
            let dh = d===0 ? `<span class="cmp-d d-eq"><div class="icon" style="font-size:clamp(12px, 3.2vw, 14px);display:inline-block;vertical-align:middle;line-height:1">${window.App.Icons.check}</div> Мэтч</span>` : (hasDiff = true, `<span class="cmp-d ${d>0?'d-up':'d-dn'}">${d>0?'+':''}${d}</span>`); 
            return `<div class="cmp anim-item" style="animation-delay:${(idx+1)*0.05}s"><span class="cmp-lb"><div class="icon" style="font-size:clamp(16px, 4.5vw, 20px);line-height:1;color:var(--text-muted)">${r.i}</div>${r.lb}</span><div class="cmp-vs"><span class="cmp-v cmp-you">${r.y}</span><span style="color:var(--text-muted);font-size:clamp(11px, 3vw, 13px)">vs</span><span class="cmp-v cmp-grp">${r.gv}</span>${dh}</div></div>`; 
        }).join('');
        
        const mx = Math.max(...g.members.map(m=>m.views),1);
        const mbH = g.members.map((m, idx) => `<div class="mb anim-list-item clickable" onclick="window.App.openHistoryLayer('group_member', '${m.name.replace(/'/g, "\\'")}', null, null, null, ${idx})" style="animation-delay:${(idx+1)*0.05}s"><span class="mb-n">${m.name}</span><div class="mb-t"><div class="mb-f" style="width:${(m.views/mx)*100}%"></div></div><span class="mb-c">${m.views}</span></div>`).join('');
        let gGenH = g.genres?.length ? `<div class="card hoverable anim-item" style="animation-delay:0.3s"><div class="label"><div class="icon" style="font-size:clamp(16px, 4.5vw, 18px);line-height:1">${window.App.Icons.masks}</div>Жанры группы</div><div class="chart-box" style="height:380px;"><canvas id="c-group-genre"></canvas></div><div id="legend-group-genre" class="legend-grid"></div></div>` : '';
        const membersLabel = `${g.members_count} ${window.App.plural(g.members_count, ['участник', 'участника', 'участников'])}`;
        
        el.innerHTML = `
            <div class="card hoverable anim-item">
                <div style="display:flex;align-items:center;gap:16px">
                    <div class="icon" style="font-size:clamp(28px, 8vw, 36px);line-height:1;color:var(--info);filter:drop-shadow(0 4px 8px rgba(56, 139, 253, 0.3))">${window.App.Icons.users}</div>
                    <div>
                        <div style="font-size:clamp(16px, 4.5vw, 20px);font-weight:800;color:var(--text-primary)">${g.group_name}</div>
                        <div style="font-size:clamp(12px, 3.2vw, 14px);color:var(--text-muted);font-weight:600;margin-top:2px;">${membersLabel} · ${g.duration_display}</div>
                    </div>
                </div>
            </div>
            <div class="card hoverable anim-item" style="animation-delay:0.1s">
                <div class="label more-pad"><div class="icon" style="font-size:clamp(16px, 4.5vw, 18px);line-height:1">${window.App.Icons.chart}</div>${subjectLabel} vs Группа</div>
                <div style="display:flex;justify-content:space-between;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--border)">
                    <span style="font-size:clamp(12px, 3.2vw, 14px);font-weight:800;color:var(--accent);letter-spacing:0.5px;text-transform:uppercase;">👤 ${subjectLabel}</span>
                    <span style="font-size:clamp(12px, 3.2vw, 14px);font-weight:800;color:var(--info);letter-spacing:0.5px;text-transform:uppercase;">👥 Группа</span>
                </div>
                ${!hasDiff?`<div style="text-align:center;padding:16px 0;font-size:clamp(15px, 4 vw, 18px);color:var(--accent);font-weight:800;display:flex;align-items:center;justify-content:center;gap:8px;animation:pulse 2s infinite;"><div class="icon" style="font-size:clamp(20px, 6vw, 24px);line-height:1">${window.App.Icons.check}</div> Полный мэтч!</div>`:''}
                ${cmpH}
            </div>
            <div class="card hoverable anim-item" style="animation-delay:0.2s">
                <div class="label more-pad"><div class="icon" style="font-size:clamp(16px, 4.5vw, 18px);line-height:1">${window.App.Icons.user}</div>Участники</div>
                ${mbH}
            </div>
            ${gGenH}`;
    },
    openShareModal: function() {
        window.App.State.setState('modals.share.isOpen', true)

        const grid = document.getElementById('share-years-grid');
        grid.innerHTML = '';
        
        const hasAll = availableYears.includes('all');
        grid.innerHTML = `<label><input type="checkbox" class="yr-chk-input" value="all" checked><div class="yr-chk-btn">Всё время</div></label>`;
        
        availableYears.filter(y => y !== 'all').forEach(y => {
            grid.innerHTML += `<label><input type="checkbox" class="yr-chk-input" value="${y}"><div class="yr-chk-btn">${y}</div></label>`;
        });

        const hasGroup = !!D.group;
        const groupWrap = document.getElementById('sh-group-wrap');
        const anonGroupWrap = document.getElementById('sh-anon-group-wrap');
        if (hasGroup) {
            groupWrap.style.display = 'flex';
            anonGroupWrap.style.display = 'flex';
            document.getElementById('sh-inc-group').checked = true;
        } else {
            groupWrap.style.display = 'none';
            anonGroupWrap.style.display = 'none';
            document.getElementById('sh-inc-group').checked = false;
        }

        document.getElementById('sh-anon-user').checked = false;
        document.getElementById('sh-anon-group').checked = false;

        window.App.toggleGroupOpts();
        document.getElementById('share-modal').classList.add('show');
    },

    closeShareModal: function() {
        window.App.State.setState('modals.share.isOpen', false)
        document.getElementById('share-modal').classList.remove('show');
    },

    toggleGroupOpts: function() {
        const incGroup = document.getElementById('sh-inc-group').checked;
        const anonGroupWrap = document.getElementById('sh-anon-group-wrap');

        if (!incGroup) {
            anonGroupWrap.style.opacity = '0.4';
            anonGroupWrap.style.pointerEvents = 'none';
        } else {
            anonGroupWrap.style.opacity = '1';
            anonGroupWrap.style.pointerEvents = 'auto';
        }
    },
    
});







async function submitShare() {
    const btn = document.getElementById('btn-do-share');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner" style="width:20px;height:20px;border-width:2px;border-color:rgba(255,255,255,0.3);border-top-color:#fff;"></div> Создание...';

    const checkedYears = Array.from(document.querySelectorAll('.yr-chk-input:checked')).map(el => el.value);
    
    if (checkedYears.length === 0) {
        window.App.showToast('Выберите хотя бы один период');
        btn.disabled = false;
        btn.innerHTML = 'Создать ссылку';
        return;
    }

    const config = {
        years: checkedYears,
        anon_user: document.getElementById('sh-anon-user').checked,
        include_group: document.getElementById('sh-inc-group').checked,
        anon_group: document.getElementById('sh-anon-group').checked
    };

    try {
        const r = await fetch('/api/webapp/bake_stats/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ config, init_data: tg?.initData||'' })
        });
        const j = await r.json();
        
        if (!r.ok || j.error) {
            window.App.showToast('Ошибка при создании слепка');
        } else {
            window.App.closeShareModal();
            if (tg) {
                tg.switchInlineQuery("share_" + j.id, ["users", "groups", "channels"]);
            }
        }
    } catch(e) {
        window.App.showToast('Сетевая ошибка');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg> Создать ссылку';
    }
}


document.getElementById('share-modal').addEventListener('click', (e) => {
    if (e.target.id === 'share-modal') {
        window.App.closeShareModal();
    }
});


document.addEventListener('DOMContentLoaded', () => {
    if (window.IS_ADMIN_DASHBOARD) return;
    if (typeof switchPeriod === 'function') switchPeriod('now');

    const modalCloseMap = {
        'details-modal': () => (typeof closeModal === 'function') && closeModal(),
        'wl-item-delete-modal': () => window.App.closeItemDeleteModal(),
        'add-view-modal': () => window.App.closeAddViewModal(),
        'wl-modal': () => window.App.closeFolderModal(),
        'wl-edit-modal': () => window.App.closeFolderEditModal(),
        'wl-limit-modal': () => window.App.closeLimitModal(),
        'casino-modal': () => window.App.closeCasino(),
        'rate-show-modal': () => window.App.closeRateModal()
    };

    Object.keys(modalCloseMap).forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('click', (e) => {
                if (e.target.id === id) modalCloseMap[id]();
            });
        }
    });
});


window.addEventListener('popstate', () => window.App.Router.sync());


const shareModalEl = document.getElementById('share-modal');
if (shareModalEl) {
    shareModalEl.addEventListener('click', (e) => {
        if (e.target.id === 'share-modal') {
            window.App.closeShareModal();
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener("DOMContentLoaded", () => { window.App.initIcons(); });
} else {
    window.App.initIcons();
}

if (tg) {
    tg.expand();
    if (tg.ready) tg.ready();
}


(function initTheme() {
    if (window.tg && tg.colorScheme === 'light') isDark = false;
    const stored = localStorage.getItem('kt');
    if (stored === 'l') isDark = false;
    if (stored === 'd') isDark = true;
    
    if (!isDark) document.body.classList.add('light');
})();