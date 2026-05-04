window.App = window.App || {};
window.handleImgErr = function (img, fallbackUrl, name) {
    if (fallbackUrl && !img.dataset.fallbackTried) {
        img.dataset.fallbackTried = 'true';
        img.src = fallbackUrl;
    } else {
        const div = document.createElement('div');
        div.className = img.className || '';
        div.style.cssText = img.style.cssText;
        div.style.display = 'inline-flex';
        div.style.alignItems = 'center';
        div.style.justifyContent = 'center';
        div.style.background = 'var(--bg-input)';
        div.style.color = 'var(--text-muted)';
        div.style.fontWeight = '800';
        
        if (!div.style.width && div.classList.contains('person-avatar')) {
            div.style.fontSize = '24px';
        }
        
        div.textContent = name ? name.charAt(0).toUpperCase() : '?';
        img.replaceWith(div);
    }
};

const Icons = {
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
    minus: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line></svg>',
    chevron_down: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>',
    sort_arrow: '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><polyline points="19 12 12 19 5 12"></polyline></svg>',
};

function i(id, name) { const el = document.getElementById(id); if (el) el.innerHTML = Icons[name]; }

function initIcons() {
    i('ic-user', 'user'); i('ic-users', 'users'); i('ic-dash', 'dash');
    i('ic-time', 'time'); i('ic-cal', 'cal'); i('ic-tv', 'tv'); i('ic-film', 'film');
    i('ic-chart-internal', 'chart'); i('ic-flame-internal', 'flame');
    i('it-gen-internal', 'masks'); i('it-act-internal', 'masks'); 
    i('it-dir-internal', 'film'); i('it-wri-internal', 'list');
    i('it-cou-internal', 'globe'); i('it-bin-internal', 'bolt');
    i('it-star-internal', 'star'); i('ic-weekday-internal', 'days');
    i('ic-search-nav', 'search'); i('ic-stats-nav', 'nav_stats');
    i('ic-wishlist-nav', 'bookmark');
    i('ic-bookmark', 'bookmark'); i('ic-check', 'check');
    i('wl-vt-grid', 'grid'); i('wl-vt-list', 'list');
    i('wl-edit-btn', 'gear');
    
    const casinoBtn = document.getElementById('wl-casino-btn');
    if (casinoBtn) casinoBtn.innerHTML = '🎰';
    
    const reorderBtn = document.getElementById('wl-reorder-btn');
    if (reorderBtn) reorderBtn.innerHTML = Icons.reorder;

    const itemsReorderBtn = document.getElementById('wl-items-reorder-btn');
    if (itemsReorderBtn) itemsReorderBtn.innerHTML = Icons.reorder;
}

if (document.readyState === 'loading') {
    document.addEventListener("DOMContentLoaded", () => { initIcons(); });
} else {
    initIcons();
}

const tg = window.Telegram?.WebApp;
if (tg) {
    tg.expand();
    if (tg.ready) tg.ready();
}

let chR = null;
let D = null, curYear = null, isDark = true;
let chM = null, chW = null, chG = {}, lastScrollPos = 0;

let isSharedMode = false;
let SharedDataMap = {};
let availableYears = [];
let activeMainView = 'search';

function toggleTheme() {
    isDark = !isDark;
    document.body.classList.toggle('light', !isDark);
    document.querySelectorAll('.js-theme-toggle').forEach(btn => btn.innerHTML = isDark ? Icons.moon : Icons.sun);
    localStorage.setItem('kt', isDark ? 'd' : 'l');
    if (D) renderCharts();
}

(function initTheme() {
    if (window.tg && tg.colorScheme === 'light') isDark = false;
    const stored = localStorage.getItem('kt');
    if (stored === 'l') isDark = false;
    if (stored === 'd') isDark = true;
    
    if (!isDark) document.body.classList.add('light');
})();

function cc() {
    const t = isDark ? 'rgba(229, 231, 235, .8)' : 'rgba(31, 35, 40, .8)';
    const g = isDark ? 'rgba(255, 255, 255, .05)' : 'rgba(0, 0, 0, .05)';
    const b = isDark ? '#2d333b' : '#d0d7de';
    return { t, g, b, a: '#2ecc71', ab: isDark ? 'rgba(46, 204, 113, .2)' : 'rgba(46, 204, 113, .15)', i: '#60a5fa', ib: isDark ? 'rgba(96, 165, 250, .2)' : 'rgba(96, 165, 250, .15)' };
}

async function init() {
    const startParam = tg?.initDataUnsafe?.start_param || '';
    const urlParams = new URLSearchParams(window.location.search);
    const sharedIdFromUrl = urlParams.get('shared_id');
    const showIdFromUrl = urlParams.get('show_id') || (startParam.startsWith('show_') ? startParam.replace('show_', '') : null);
    const viewFromUrl = urlParams.get('view');

    if (sharedIdFromUrl || startParam.startsWith('stat_')) {
        isSharedMode = true;
        document.body.classList.add('has-banner');
        
        document.getElementById('share-btn').classList.add('hidden');
        document.getElementById('bottom-nav').style.display = 'none';
        activeMainView = 'stats';
        switchMainView('stats');
        
        const bannerContainer = document.getElementById('shared-banner-container');
        bannerContainer.innerHTML = `<div class="shared-banner"><svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3"/></svg> Вы просматриваете чужую статистику</div>`;
        
        const sid = sharedIdFromUrl || startParam.replace('stat_', '');
        await loadShared(sid);
    } else {
        await load();
        
        const role = D?.meta?.role || 'guest';
        document.getElementById('bottom-nav').style.display = 'flex';
        document.body.classList.add('has-nav');
        if (role === 'guest') {
            document.getElementById('bn-stats').classList.add('hidden');
        }
        
        switchMainView(viewFromUrl || 'search');

        if (showIdFromUrl) {
            window.App.openShowLayer(showIdFromUrl);
        }
    }
}

function getScrollContainer() {
    return document.getElementById('views-container');
}

function switchMainView(view) {
    activeMainView = view;
    document.getElementById('view-search').style.display = view === 'search' ? 'flex' : 'none';
    document.getElementById('view-stats').style.display = view === 'stats' ? 'block' : 'none';
    document.getElementById('view-wishlist').style.display = view === 'wishlist' ? 'block' : 'none';
    
    document.getElementById('bn-search').classList.toggle('active', view === 'search');
    document.getElementById('bn-stats').classList.toggle('active', view === 'stats');
    document.getElementById('bn-wishlist').classList.toggle('active', view === 'wishlist');
    
    getScrollContainer().scrollTop = 0;

    if (view === 'wishlist' && window.App.loadWishlist) {
        const container = document.getElementById('wl-items-container');
        if (container) container.innerHTML = '';
        window.App.loadWishlist();
    }
}

let searchTimer = null;
async function doSearch(q) {
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
            renderSearchResults(data);
        } catch(e) {
            resEl.innerHTML = '<div class="empty">Ошибка при поиске</div>';
        }
    }, 500);
}

function renderSearchResults(data) {
    let html = '';
    
    if (data.persons?.length) {
        html += `<div class="label"><div class="icon" style="color:#d29922">${Icons.users}</div>Люди</div>`;
        html += '<div class="h-scroll-container" style="padding-bottom:16px;">';
        data.persons.forEach(p => {
            const fb = p.fallback_photo_url ? `'${p.fallback_photo_url}'` : 'null';
            const img = p.photo_url ? `<img src="${p.photo_url}" class="person-avatar" style="object-fit:cover;" onerror="window.handleImgErr(this, ${fb}, '${p.name.replace(/'/g, "\\'")}')">` : `<div class="person-avatar">${p.name.charAt(0)}</div>`;
            html += `<div class="person-pill" onclick="window.App.openCollectionLayer('person', ${p.id}, '${p.name.replace(/'/g, "\\'")}')">${img}<div class="person-name">${p.name}</div></div>`;
        });
        html += '</div>';
    }
    
    if (data.shows?.length) {
        html += `<div class="label"><div class="icon" style="color:var(--info)">${Icons.film}</div>Фильмы и Сериалы</div>`;
        html += '<div class="hist-grid" style="padding:0 16px;">';
        data.shows.forEach(s => {
            const poster = s.poster_url ? `<img src="${s.poster_url}" class="grid-poster" loading="lazy">` : '<div class="grid-poster"></div>';
            const safeTitle = s.title.replace(/'/g, "\\'");
            html += `<div class="grid-item-wrap anim-item" onclick="window.App.openShowLayer(${s.id})">
                <div class="grid-item">
                    ${poster}
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
    
    document.getElementById('search-results').innerHTML = html;
}

async function loadShared(statId) {
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
        
        render();
    } catch(e) { 
        console.error(e); 
        document.getElementById('app').innerHTML = `<div style="padding: 40px; text-align:center; font-size: 16px; color: var(--text-primary);"><div style="font-size: 40px; margin-bottom: 10px;">❌</div>Слепок не найден или произошла ошибка:<br><br><span style="color:var(--danger);">${e.message}</span></div>`;
        document.getElementById('app').classList.remove('hidden');
    } finally {
        hideLoader();
    }
}

async function load(year) {
    if (year === undefined || year === null) year = curYear;
    curYear = year;
    document.getElementById('loader').classList.remove('hidden');
    try {
        const p = year && year !== 'all' ? { period_type:'year', period_value: year } : { period_type:'year', period_value: 0 };
        const r = await fetch('/api/webapp/detailed_stats/', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ ...p, init_data: tg?.initData||'' }) });
        if (!r.ok) throw new Error(`Ошибка HTTP сервера: ${r.status}`);
        const j = await r.json();
        if (j.error) throw new Error(j.error);
        
        D = j;
        if (!availableYears.length && D.meta?.years) {
            availableYears = [...D.meta.years];
        }
        render();
    } catch(e) { 
        console.error('Load error:', e); 
        document.getElementById('app').innerHTML = `<div style="padding: 40px; text-align:center; font-size: 16px; color: var(--text-primary);"><div style="font-size: 40px; margin-bottom: 10px;">❌</div>Ошибка загрузки данных:<br><br><span style="color:var(--danger);">${e.message}</span></div>`;
        document.getElementById('app').classList.remove('hidden');
    } finally { 
        hideLoader();
    }
}

function hideLoader() {
    document.getElementById('loader').style.opacity = '0';
    setTimeout(() => document.getElementById('loader').classList.add('hidden'), 400);
    document.getElementById('app').classList.remove('hidden'); 
}

function plural(n, forms) {
    let n10 = Math.abs(n) % 10;
    let n100 = Math.abs(n) % 100;
    if (n100 >= 11 && n100 <= 14) return forms[2];
    if (n10 === 1) return forms[0];
    if (n10 >= 2 && n10 <= 4) return forms[1];
    return forms[2];
}

const UserAvatarColors = ['#3498db', '#9b59b6', '#f1c40f', '#e67e22', '#e74c3c', '#1abc9c', '#34495e', '#2ecc71'];

function getUserColor(id) {
    if (id === 0) return 'var(--bg-input)';
    return UserAvatarColors[(id - 1) % UserAvatarColors.length];
}

window.switchPersonTab = function(category, mode, btn) {
    const container = btn.closest('.view-toggle');
    container.querySelectorAll('.vt-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    
    const data = D[category][mode];
    fillList(`${category}-list`, data, null, ['просмотр', 'просмотра', 'просмотров'], category, mode);
};

function render() {
    if (!D?.meta) return;
    const n = D.meta.name || 'Пользователь';
    document.getElementById('user-name').textContent = n;
    
    const avEl = document.getElementById('avatar');
    if (D.meta.is_anonymous) {
        const myId = D.meta.id || 0;
        if (myId > 0) {
            avEl.innerHTML = `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:${getUserColor(myId)};color:#fff;font-weight:900;">${myId}</div>`;
        } else {
            avEl.innerHTML = `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:var(--bg-input);color:var(--text-muted);">${Icons.user}</div>`;
        }
    } else if (D.meta.photo_url) {
        avEl.innerHTML = `<img src="${D.meta.photo_url}" alt="A">`;
    } else {
        const u = tg?.initDataUnsafe?.user;
        if (!isSharedMode && u && u.photo_url) avEl.innerHTML = `<img src="${u.photo_url}" alt="A">`;
        else avEl.textContent = n.charAt(0).toUpperCase();
    }

    document.getElementById('period-label').textContent = D.summary?.period_label || '';
    renderYears();

    const s = D.summary || {};
    const vViews = s.total_views || 0, vEp = s.total_episodes || 0, vMov = s.total_movies || 0, vSer = s.unique_series || 0;
    
    const toggle = (id, show) => document.getElementById(id)?.classList.toggle('hidden', !show);

    const hasGroup = !!D.group;
    toggle('main-tabs', hasGroup);

    const userRole = String(D.meta.role || 'guest').toLowerCase();
    const isGuest = userRole === 'guest';
    
    const showOverview = !isGuest;
    toggle('label-overview', showOverview);
    toggle('grid-overview', showOverview);

    if (showOverview) {
        document.getElementById('s-time').textContent  = s.duration_display || '0м';
        document.getElementById('s-views').textContent = vViews + ' ' + plural(vViews, ['просмотр', 'просмотра', 'просмотров']);
        document.getElementById('s-act').textContent   = (s.activity_percent||0) + '%';
        document.getElementById('s-daily').textContent = '~' + (s.daily_average_min||0) + ' мин/день';
        document.getElementById('s-ep').textContent = vEp;
        const epLbl = document.getElementById('s-ep').nextElementSibling;
        if (epLbl) epLbl.textContent = plural(vEp, ['Эпизод', 'Эпизода', 'Эпизодов']);
        const serInfo = vSer + ' ' + plural(vSer, ['сериал', 'сериала', 'сериалов']);
        document.getElementById('s-ser').textContent = serInfo + ' · ' + (s.series_duration || '0м');
        document.getElementById('s-mov').textContent = vMov;
        const movLbl = document.getElementById('s-mov').nextElementSibling;
        if (movLbl) movLbl.textContent = plural(vMov, ['Фильм', 'Фильма', 'Фильмов']);
        document.getElementById('s-uni').textContent = s.movies_duration || '0м';
        
        document.getElementById('s-wl-added').textContent = s.wishlist_added || 0;
        document.getElementById('s-wl-watched').textContent = s.wishlist_watched || 0;
    }

    const showWelcome = !isGuest && vViews === 0;
    let welcomeEl = document.getElementById('welcome-empty-state');
    if (showWelcome) {
        if (!welcomeEl) {
            welcomeEl = document.createElement('div');
            welcomeEl.id = 'welcome-empty-state';
            welcomeEl.className = 'card anim-item';
            welcomeEl.innerHTML = `<div class="empty"><div class="icon">${Icons.tv}</div>Здесь будет ваша статистика, когда вы начнете смотреть кино.</div>`;
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
    if (hasHeatmap) renderHeatmap();

    const hasGenres = D.genres?.length > 0;
    toggle('card-genres', hasGenres);
    
    const hasActors = (D.actors?.series?.length || D.actors?.others?.length);
    toggle('card-actors', hasActors);
    if (hasActors) fillList('actors-list', D.actors.series, null, ['просмотр', 'просмотра', 'просмотров'], 'actors', 'series');
    
    const hasDirectors = (D.directors?.series?.length || D.directors?.others?.length);
    toggle('card-directors', hasDirectors);
    if (hasDirectors) fillList('directors-list', D.directors.series, null, ['просмотр', 'просмотра', 'просмотров'], 'directors', 'series');

    const hasWriters = (D.writers?.series?.length || D.writers?.others?.length);
    toggle('card-writers', hasWriters);
    if (hasWriters) fillList('writers-list', D.writers.series, null, ['просмотр', 'просмотра', 'просмотров'], 'writers', 'series');
    
    const hasCountries = D.countries?.length > 0;
    toggle('card-countries', hasCountries);
    if (hasCountries) fillList('countries-list', D.countries, Icons.globe, ['просмотр', 'просмотра', 'просмотров'], 'countries');
    
    const hasBinges = D.binges?.length > 0;
    toggle('card-binges', hasBinges);
    if (hasBinges) fillBinges();

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
        document.getElementById('cr-total').innerHTML = `${rt.total}<br><span style="font-size: 11px; opacity: 0.7;">${plural(rt.total, ['оценка', 'оценки', 'оценок'])}</span>`;
        const badge = document.getElementById('cr-badge');
        if (rt.avg >= 8.5) { badge.textContent = 'Восторженный зритель'; badge.style.background = 'rgba(46, 204, 113, 0.15)'; badge.style.color = '#2ecc71'; }
        else if (rt.avg >= 7.0) { badge.textContent = 'Позитивный критик'; badge.style.background = 'rgba(56, 139, 253, 0.15)'; badge.style.color = '#60a5fa'; }
        else if (rt.avg >= 5.5) { badge.textContent = 'Объективный судья'; badge.style.background = 'rgba(210, 153, 34, 0.15)'; badge.style.color = '#d29922'; }
        else { badge.textContent = 'Суровый критик'; badge.style.background = 'rgba(248, 81, 73, 0.15)'; badge.style.color = '#e74c3c'; }
        renderRatingsDist();
    }

    toggle('tab-group-btn', !!D.group);
    renderGroup();
    renderCharts();
}

function renderRatingsDist() {
    if (typeof Chart === 'undefined') return;
    
    const canvas = document.getElementById('c-ratings-dist');
    const ctx = canvas.getContext('2d');
    if (chR) chR.destroy();
    const dist = D.ratings.distribution;
    if (!dist || dist.length === 0) return;
    const c = cc();
    const ratingPalette = ['#f85149', '#f85149', '#e67e22', '#e67e22', '#d29922', '#d29922', '#388bfd', '#388bfd', '#2ea043', '#39d353'];

    chR = new Chart(ctx, {
        type: 'bar',
        data: { labels: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'], datasets: [{ data: dist, backgroundColor: ratingPalette, hoverBackgroundColor: ratingPalette, borderRadius: 6, borderSkipped: false, borderWidth: 0 }] },
        options: {
            responsive: true, maintainAspectRatio: false,
            animation: { duration: 1000, easing: 'easeOutBack', delay: (context) => context.type === 'data' && context.mode === 'default' && !context.active ? context.dataIndex * 80 : 0 },
            onHover: (event, activeElements) => { event.native.target.style.cursor = activeElements.length ? 'pointer' : 'default'; },
            onClick: (event, activeElements) => { if (activeElements.length > 0) window.openHistoryLayer('rating_filter', 'Оценка: ' + (activeElements[0].index + 1), null, null, null, activeElements[0].index + 1); },
            plugins: {
                legend: { display: false },
                tooltip: { backgroundColor: isDark ? 'rgba(22, 27, 34, 0.95)' : 'rgba(255, 255, 255, 0.95)', titleColor: isDark ? '#f0f6fc' : '#1f2328', bodyColor: isDark ? '#8b949e' : '#59636e', borderColor: c.b, borderWidth: 1, cornerRadius: 10, padding: 12, displayColors: false, callbacks: { title: (ctx) => `Оценка: ${ctx[0].label}`, label: (ctx) => ` ${ctx.parsed.y} ${plural(ctx.parsed.y, ['оценка', 'оценки', 'оценок'])}` } }
            },
            scales: { x: { ticks: { color: c.t, font: { size: fSizeAx, weight: '600' } }, grid: { display: false } }, y: { display: false, beginAtZero: true } }
        }
    });
}

function getRatingColor(rating) {
    if (rating >= 8.5) return 'linear-gradient(135deg, #2ecc71, #27ae60)';
    if (rating >= 7.0) return 'linear-gradient(135deg, #60a5fa, #3b82f6)';
    if (rating >= 5.5) return 'linear-gradient(135deg, #f1c40f, #d35400)';
    return 'linear-gradient(135deg, #e74c3c, #c0392b)';
}

function renderYears() {
    const c = document.getElementById('years');
    const yrs = isSharedMode ? availableYears : (D.meta?.years || []);
    
    if (yrs.length <= 1) {
        c.classList.add('hidden');
        return;
    }
    c.classList.remove('hidden');

    let h = '';
    if (!isSharedMode || yrs.includes('all')) {
        h += '<button class="yr clickable" onclick="pickYear(\'all\')">Всё время</button>';
    }
    
    yrs.filter(y => y !== 'all').forEach(y => { 
        h += `<button class="yr clickable" onclick="pickYear('${y}')">${y}</button>`; 
    });
    c.innerHTML = h;
    markYear();
}

function markYear() {
    document.querySelectorAll('#years .yr').forEach(b => {
        const v = b.textContent.trim();
        const isAllTime = curYear === 'all' || !curYear;
        const targetStr = isAllTime ? 'Всё время' : String(curYear);
        b.classList.toggle('on', v === targetStr);
    });
}

window.pickYear = y => { 
    curYear = y; 
    markYear(); 
    if (isSharedMode) {
        D = SharedDataMap[y];
        render();
    } else {
        load(y); 
    }
};

let toastTimer = null;
function showToast(text) {
    let el = document.getElementById('toast-msg');
    if (!el) { el = document.createElement('div'); el.id = 'toast-msg'; el.className = 'toast'; document.body.appendChild(el); }
    el.textContent = text; el.classList.add('show');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.classList.remove('show'); }, 2000);
}

function initGlobalHeatmapZoom() {
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
}

function renderHeatmap() {
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
            if (v > 0) { d.setAttribute('onclick', `window.openHistoryLayer('day', '${displayDate}', null, '${currStr}')`); } else { d.setAttribute('onclick', `showToast('${displayDate}: просмотров нет')`); }
            hm.appendChild(d); curr.setDate(curr.getDate() + 1);
        });
        wrapper.appendChild(hm); block.appendChild(wrapper); fragment.appendChild(block);
    });
    zoomContent.appendChild(fragment); initGlobalHeatmapZoom();
}

function fillList(id, items, ico, unit, categoryKey, mode = 'series') {
    const el = document.getElementById(id);
    if (!el) return;
    if (!items?.length) {
        el.innerHTML = '<div class="empty" style="padding: 20px 0;"><div class="icon" style="font-size:24px;">' + Icons.dash + '</div>Нет данных</div>';
        return;
    }
    let html = '';
    items.forEach((it, i) => {
        const cnt = it.count || it.views || 0, sub = it.sub || (it.shows ? `${it.shows} ${plural(it.shows, ['шоу', 'шоу', 'шоу'])}` : '');
        const lbl = Array.isArray(unit) ? `${cnt} ${plural(cnt, unit)}` : (unit ? `${cnt} ${unit}` : cnt);
        const delay = (i + 1) * 0.05;
        
        const safeName = it.name.replace(/'/g, "\\'").replace(/"/g, "&quot;");
        let visual = '';
        if (it.photo_url) {
            const fb = it.fallback_photo_url ? `'${it.fallback_photo_url}'` : 'null';
            visual = `<img src="${it.photo_url}" style="width:clamp(24px, 6vw, 32px);height:clamp(24px, 6vw, 32px);border-radius:50%;object-fit:cover;margin-right:6px;vertical-align:middle;display:inline-block;" onerror="window.handleImgErr(this, ${fb}, '${safeName}')">`;
        } else if (it.emoji) {
            visual = `<span style="font-size:clamp(18px,5vw,22px);line-height:1;margin-right:6px;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.1))">${it.emoji}</span>`;
        } else if (ico) {
            visual = `<div class="icon" style="color:var(--text-muted);display:inline-block;vertical-align:middle;margin-right:6px;">${ico}</div>`;
        }

        const histKey = ['actors', 'directors', 'writers'].includes(categoryKey) ? `${categoryKey}_${mode}` : categoryKey;
        D[histKey] = items;

        html += `<div class="li li-clickable anim-list-item clickable" onclick="window.openHistoryLayer('filter', '${safeName}', null, null, '${histKey}', ${i})" style="animation-delay:${delay}s"><div class="li-l"><span class="li-rank">${i+1}</span><div><div class="li-name">${visual} ${it.name}</div>${sub?`<div class="li-sub">${sub}</div>`:''}</div></div><span class="li-r" style="color:var(--info)">${lbl}</span></div>`;
    });
    el.innerHTML = html;
}

function fillBinges() {
    const el = document.getElementById('binges-list');
    if (!D.binges?.length) return;
    let html = '';
    D.binges.forEach((b, i) => {
        const delay = (i + 1) * 0.05, safeTitle = b.show_title.replace(/'/g, "\\'").replace(/"/g, "&quot;");
        const posterHtml = b.poster_url ? `<img src="${b.poster_url}" style="width:clamp(36px, 10vw, 44px);height:clamp(54px, 15vw, 66px);border-radius:6px;object-fit:cover;flex-shrink:0;background:var(--bg-input);border:1px solid var(--border);box-shadow:0 2px 6px rgba(0,0,0,0.1);" onerror="this.style.display='none'">` : `<div style="width:clamp(36px, 10vw, 44px);height:clamp(54px, 15vw, 66px);border-radius:6px;flex-shrink:0;background:var(--bg-input);border:1px solid var(--border);"></div>`;
        html += `<div class="li li-clickable anim-list-item clickable" style="animation-delay:${delay}s" onclick="window.openHistoryLayer('binge', '${safeTitle}', ${b.show_id}, '${b.date}')"><div class="li-l">${posterHtml}<div><div class="li-name">${b.show_title}</div><div class="li-sub">${b.date}</div></div></div><span class="li-r" style="color:var(--info)">${b.count} ${plural(b.count, ['эпизод', 'эпизода', 'эпизодов'])}</span></div>`;
    });
    el.innerHTML = html;
}

function renderCharts() { 
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js не загружен. Отрисовка графиков пропущена.');
        return;
    }
    try {
        renderMonthly(); 
        renderWeekday(); 
        renderDonut('c-genre', 'legend-genre', D.genres, 'genres_top', D.summary.total_minutes_watched);
        if (D.group) renderDonut('c-group-genre', 'legend-group-genre', D.group.genres, 'group_genres_top', D.group.total_minutes_watched);
    } catch (e) {
        console.error('Ошибка при отрисовке графиков:', e);
    }
}

const fSizeAx = Math.max(10, Math.min(13, window.innerWidth * 0.03));
function getCtxGradient(ctx, colorStart, colorEnd) { let gradient = ctx.createLinearGradient(0, 0, 0, 400); gradient.addColorStop(0, colorStart); gradient.addColorStop(1, colorEnd); return gradient; }

function renderMonthly() {
    const canvas = document.getElementById('c-monthly'), ctx = canvas.getContext('2d');
    if (chM) chM.destroy();
    const ch = D.monthly_chart; if (!ch?.labels?.length) return;
    const c = cc();
    let fillGradient = getCtxGradient(ctx, isDark?'rgba(35, 134, 54, 0.4)':'rgba(46, 160, 67, 0.3)', 'rgba(35, 134, 54, 0.0)'), lineGradient = ctx.createLinearGradient(0, 0, canvas.width || 400, 0);
    lineGradient.addColorStop(0, '#2ea043'); lineGradient.addColorStop(1, '#3fb950');
    
    let labelFontSize = fSizeAx;
    if (ch.labels.length > 12) labelFontSize = Math.max(8, fSizeAx - 2);

    chM = new Chart(ctx, { 
        type:'line', 
        data:{ labels:ch.labels, datasets:[{ label: ' Просмотры', data: ch.views, backgroundColor: fillGradient, borderColor: lineGradient, borderWidth: 3, tension: 0.4, fill: true, yAxisID: 'y', pointBackgroundColor: isDark ? '#0d1117' : '#ffffff', pointBorderColor: '#3fb950', pointBorderWidth: 2, pointRadius: 4, pointHoverRadius: 6 }, { label: ' Часы', data: ch.hours, backgroundColor: 'transparent', borderColor: c.i, borderWidth: 2, borderDash: [5, 5], tension: 0.4, fill: false, yAxisID: 'y1', pointBackgroundColor: isDark ? '#0d1117' : '#ffffff', pointBorderColor: c.i, pointRadius: 0, pointHoverRadius: 5 }] },
        options:{ responsive:true, maintainAspectRatio:false, animation: { duration: 1500, easing: 'easeOutQuart' }, plugins:{ legend: { display: true, position: 'top', labels: { color: c.t, usePointStyle: true, boxWidth: 8, padding: 15, font: { size: fSizeAx, family: 'system-ui' } } }, tooltip: { backgroundColor: isDark ? 'rgba(22, 27, 34, 0.95)' : 'rgba(255, 255, 255, 0.95)', titleColor: isDark ? '#f0f6fc' : '#1f2328', bodyColor: isDark ? '#8b949e' : '#59636e', borderColor: c.b, borderWidth: 1, padding: 12, cornerRadius: 8, displayColors: true, boxPadding: 6, bodySpacing: 8, titleSpacing: 10 } }, interaction: { mode: 'index', intersect: false }, scales:{ x:{ ticks:{color:c.t, font:{size:labelFontSize}, maxRotation: 45, minRotation: 0}, grid:{display:false} }, y:{ type: 'linear', display: true, position: 'left', ticks:{color:c.a,font:{size:fSizeAx}}, grid:{color:c.g}, beginAtZero:true }, y1: { type: 'linear', display: true, position: 'right', ticks:{color:c.i,font:{size:fSizeAx}}, grid:{drawOnChartArea: false}, beginAtZero:true } } } 
    });
}

function renderWeekday() {
    const canvas = document.getElementById('c-weekday'), ctx = canvas.getContext('2d');
    if (chW) chW.destroy();
    const ch = D.weekday_chart; if (!ch?.labels?.length) return;
    const c = cc(), totalViews = ch.data.reduce((a, b) => a + b, 0);
    let barGradient = getCtxGradient(ctx, '#2ea043', '#238636'), weGradient = getCtxGradient(ctx, '#388bfd', '#1f6feb');
    chW = new Chart(ctx, { 
        type: 'bar', 
        data: { labels: ch.labels, datasets: [{ data: ch.data, backgroundColor: ch.data.map((_, i) => i >= 5 ? weGradient : barGradient), hoverBackgroundColor: ch.data.map((_, i) => i >= 5 ? '#60a5fa' : '#39d353'), borderRadius: 8, borderSkipped: false, borderWidth: 0, hoverBorderWidth: 0 }] },
        options: { 
            responsive: true, maintainAspectRatio: false, 
            animation: { duration: 1000, easing: 'easeOutBack', delay: (context) => context.type === 'data' && context.mode === 'default' && !context.active ? context.dataIndex * 100 : 0 }, 
            onClick: (event, activeElements) => {
                if (activeElements.length > 0) {
                    const idx = activeElements[0].index;
                    window.openHistoryLayer('weekday', ch.labels[idx], null, null, null, idx);
                }
            },
            onHover: (event, activeElements) => { event.native.target.style.cursor = activeElements.length ? 'pointer' : 'default'; },
            plugins: { legend: { display: false }, tooltip: { backgroundColor: isDark ? 'rgba(22, 27, 34, 0.95)' : 'rgba(255, 255, 255, 0.95)', titleColor: isDark ? '#f0f6fc' : '#1f2328', bodyColor: isDark ? '#8b949e' : '#59636e', borderColor: c.b, borderWidth: 1, cornerRadius: 10, padding: 12, displayColors: false, callbacks: { label: (context) => { const val = context.parsed.y; const pct = totalViews > 0 ? Math.round((val / totalViews) * 100) : 0; return ` ${val} ${plural(val, ['просмотр', 'просмотра', 'просмотров'])} (${pct}%)`; } } } }, 
            scales: { x: { ticks: { color: c.t, font: { size: fSizeAx, weight: '600' } }, grid: { display: false } }, y: { ticks: { color: c.t, font: { size: fSizeAx }, precision: 0 }, grid: { color: c.g }, beginAtZero: true, border: { display: false } } } 
        } 
    });
}

function renderDonut(canvasId, legendId, sourceData, dataKey, totalMinutesWatched) {
    const canvas = document.getElementById(canvasId); if (!canvas) return;
    const ctx = canvas.getContext('2d'), legendEl = document.getElementById(legendId);
    if (chG[canvasId]) chG[canvasId].destroy(); if (!sourceData?.length) return;
    const c = cc();
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
        options: { responsive: true, maintainAspectRatio: false, cutout: '50%', layout: { padding: 15 }, animation: { animateRotate: true, duration: 1200, easing: 'easeOutQuart' }, onHover: (event, activeElements) => { event.native.target.style.cursor = activeElements.length ? 'pointer' : 'default'; }, onClick: (event, activeElements) => { if (activeElements.length > 0) window.openHistoryLayer('filter', top[activeElements[0].index].name, null, null, dataKey, activeElements[0].index); }, plugins: { datalabels: { color: '#fff', font: { weight: '800', size: 10 }, formatter: (value, context) => percents[context.dataIndex] > 5 ? percents[context.dataIndex] + '%' : '', display: 'auto' }, tooltip: { enabled: true, callbacks: { label: (context) => { const val = context.parsed, h = Math.floor(val/60), m = val%60; return ` ${h}ч ${m}м (${percents[context.dataIndex]}%)`; } } }, legend: { display: false } } } 
    });
    D[dataKey] = top;
    legendEl.innerHTML = top.map((g, i) => `<div class="legend-item" onclick="window.openHistoryLayer('filter', '${g.name.replace(/'/g, "\\'")}', null, null, '${dataKey}', ${i})" onmouseenter="highlightSegment('${canvasId}', ${i}, true)" onmouseleave="highlightSegment('${canvasId}', ${i}, false)"><div class="legend-dot" style="background:${pal[i % pal.length]}"></div><div class="legend-name">${g.name}</div><div class="legend-val">${Math.floor(g.minutes / 60) > 0 ? `${Math.floor(g.minutes / 60)}ч ${g.minutes % 60}м` : `${g.minutes % 60}м`} (${percents[i]}%)</div></div>`).join('');
}
window.highlightSegment = function(canvasId, index, active) { const chart = chG[canvasId]; if (!chart) return; if (active) { chart.setActiveElements([{ datasetIndex: 0, index: index }]); chart.tooltip.setActiveElements([{ datasetIndex: 0, index: index }], { x: 0, y: 0 }); } else { chart.setActiveElements([]); chart.tooltip.setActiveElements([], { x: 0, y: 0 }); } chart.update(); };
window.mainTab = function(t) { 
    document.querySelectorAll('#main-tabs .tab').forEach(b=>b.classList.toggle('on', b.dataset.tab===t)); 
    document.getElementById('sec-personal').classList.toggle('hidden', t!=='personal'); 
    document.getElementById('sec-group').classList.toggle('hidden', t!=='group'); 
};

let curHistData =[], curHistType = '';
let currentHistoryOffset = 0;
const historyBatchSize = 100;
let historyObserver = null;
let isRenderingBatch = false;
let viewMode = localStorage.getItem('kp_view_mode') || 'grid';

window.openHistoryLayer = function(type, title, extraId, extraDate, extraKey, extraIndex) {
    curHistType = type;
    
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

    let headerSectionHtml = '';
    const isPersonCategory = extraKey && (extraKey.startsWith('actors') || extraKey.startsWith('directors') || extraKey.startsWith('writers'));
    
    if (type === 'filter' && isPersonCategory) {
        const p = D[extraKey][extraIndex];
        const safeName = p.name.replace(/'/g, "\\'");
        const fb = p.fallback_photo_url ? `'${p.fallback_photo_url}'` : 'null';
        const imgHtml = p.photo_url 
            ? `<img src="${p.photo_url}" class="person-avatar" style="width:60px; height:60px; object-fit:cover; flex-shrink:0;" onerror="window.handleImgErr(this, ${fb}, '${safeName}')">`
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

    const headerHtml = `
    <div class="layer-header">
        <button onclick="popLayer()" class="tab clickable" style="background:var(--bg-input); color:var(--text-primary); margin:0; display:inline-flex; border:none; padding:8px 16px;">
            <svg viewBox="0 0 24 24" width="18" height="18" style="margin-right:6px;"><path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg> Назад
        </button>
        <span style="font-weight:800; color:var(--text-primary); font-size:16px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:50%;">${title}</span>
        <div class="view-toggle" style="margin:0; padding:2px;">
            <button class="vt-btn ${viewMode === 'grid' ? 'active' : ''}" onclick="window.App.setViewModeLayer('grid')">${Icons.grid}</button>
            <button class="vt-btn ${viewMode === 'list' ? 'active' : ''}" onclick="window.App.setViewModeLayer('list')">${Icons.list}</button>
        </div>
    </div>`;

    const bodyHtml = `
        ${headerHtml}
        ${headerSectionHtml}
        <div id="layer-hist-container" style="padding: 16px;"></div>
        <div id="layer-hist-sentinel" style="height: 40px; width: 100%;"></div>
    `;

    pushLayer(bodyHtml, { type: 'history' });
    currentHistoryOffset = 0;
    renderHistoryBatchLayer();
};

window.setViewModeLayer = function(mode) {
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
        renderHistoryBatchLayer();
    }
};

function getHistoryItemHtml(item, idx, type, mode) {
    const sid = item.show_id;
    const delay = (idx % 100) * 0.05;
    const animClass = 'anim-item';
    const style = `style="animation-delay: ${delay}s"`;

    if (mode === 'list') {
        if (type === 'ratings') {
            const origTitle = item.original_title && item.original_title !== item.title ? `<div class="hist-orig">${item.original_title}</div>` : '';
            const poster = item.poster_url ? `<img src="${item.poster_url}" class="hist-poster" loading="lazy">` : `<div class="hist-poster"></div>`;
            const rVal = Number.isInteger(item.rating) ? item.rating : item.rating.toFixed(1);
            const rColor = getRatingColor(item.rating);
            let seHtml = item.season && item.episode ? `<span class="hist-badge">s${item.season}e${item.episode.toString().padStart(2,'0')}</span>` : '';
            return `<div class="hist-item clickable ${animClass}" ${style} onclick="window.App.openShowLayer(${sid})">${poster}<div class="hist-info" style="flex:1;"><div class="hist-title">${item.title}</div>${origTitle}<div class="hist-meta">${seHtml}</div><div class="rating-time">${Icons.time} ${item.date}</div></div><div class="big-rating-badge" style="background: ${rColor};">${rVal}</div></div>`;
        } else {
            const poster = item.poster_url ? `<img src="${item.poster_url}" class="hist-poster" loading="lazy">` : `<div class="hist-poster"></div>`;
            let metaHtml = '';
            if (item.season_number > 0) metaHtml += `<span class="hist-badge">s${item.season_number}e${item.episode_number.toString().padStart(2,'0')}</span>`;
            if (item.user_rating) metaHtml += `<span class="rating-badge">${Icons.star}${item.user_rating}</span>`;
            const viewers = (item.user_names && item.user_names.length > 1) ? `<div class="li-sub" style="font-size:11px;">👥 ${item.user_names.join(', ')}</div>` : '';
            return `<div class="hist-item clickable ${animClass}" ${style} onclick="window.App.openShowLayer(${sid})">${poster}<div class="hist-info"><div class="hist-title">${item.show__title}</div><div class="hist-meta">${metaHtml}<span>${item.view_date}</span></div>${viewers}</div></div>`;
        }
    } else {
        const mediumPoster = item.poster_url ? item.poster_url.replace('/small/', '/medium/') : '';
        const posterHtml = mediumPoster ? `<img src="${mediumPoster}" class="grid-poster" loading="lazy">` : '<div class="grid-poster"></div>';
        const yearHtml = (item.year || item.show__year) ? `<div class="grid-year">${item.year || item.show__year}</div>` : '';
        
        if (type === 'ratings') {
            const rVal = Number.isInteger(item.rating) ? item.rating : item.rating.toFixed(1);
            return `<div class="grid-item-wrap ${animClass}" ${style} onclick="window.App.openShowLayer(${sid})"><div class="grid-item rating-card">${posterHtml}${yearHtml}<div class="big-rating-badge" style="background: ${getRatingColor(item.rating)};">${rVal}</div><div class="grid-overlay"><div class="grid-date">${item.date}</div></div></div><div class="grid-below-title">${item.title}</div></div>`;
        } else {
            let badgesHtml = '';
            if (item.season_number > 0) badgesHtml += `<span class="hist-badge" style="background:rgba(0,0,0,0.6);border:none;">s${item.season_number}e${item.episode_number.toString().padStart(2,'0')}</span>`;
            if (item.user_rating) badgesHtml += `<span class="rating-badge" style="background:rgba(0,0,0,0.6);border:none;">${Icons.star}${item.user_rating}</span>`;
            
            let usersHtml = '';
            if (item.user_names && item.user_names.length > 0) {
                let avatars = '';
                for (let i = 0; i < item.user_names.length; i++) {
                    const name = item.user_names[i] || '?';
                    const photo = item.user_photos && item.user_photos[i];
                    const userId = (item.user_ids && item.user_ids[i]);
                    if (photo) avatars += `<img src="${photo}" class="grid-user-avatar">`;
                    else avatars += `<div class="grid-user-avatar" style="background:${getUserColor(userId || 0)};">${isSharedMode && userId>0 ? userId : name.charAt(0).toUpperCase()}</div>`;
                }
                usersHtml = `<div class="grid-users">${avatars}</div>`;
            }
            return `<div class="grid-item-wrap ${animClass}" ${style} onclick="window.App.openShowLayer(${sid})"><div class="grid-item">${posterHtml}${yearHtml}<div class="grid-badges">${badgesHtml}</div><div class="grid-overlay">${usersHtml}<div class="grid-date">${item.view_date}</div></div></div><div class="grid-below-title">${item.show__title}</div></div>`;
        }
    }
}

function renderHistoryBatchLayer() {
    if (isRenderingBatch || currentHistoryOffset >= curHistData.length) return;
    isRenderingBatch = true;
    
    const topLayer = viewStack[viewStack.length - 1];
    if (!topLayer || topLayer.context.type !== 'history') {
        isRenderingBatch = false; return;
    }
    
    const container = topLayer.el.querySelector('#layer-hist-container');
    if (curHistData.length === 0) {
        container.innerHTML = `<div class="empty"><div class="icon">${Icons.dash}</div>Нет данных</div>`;
        isRenderingBatch = false; return;
    }

    const batch = curHistData.slice(currentHistoryOffset, currentHistoryOffset + historyBatchSize);
    let html = batch.map((item, idx) => getHistoryItemHtml(item, idx, curHistType, viewMode)).join('');
    
    if (currentHistoryOffset === 0 && viewMode === 'list') {
        container.innerHTML = '<div class="card" style="margin:0; padding:0; border:none; background:transparent;">' + html + '</div>';
    } else if (currentHistoryOffset === 0 && viewMode === 'grid') {
        container.innerHTML = '<div class="hist-grid">' + html + '</div>';
    } else {
        const target = container.querySelector('.card') || container.querySelector('.hist-grid');
        if (target) {
            target.insertAdjacentHTML('beforeend', html);
        }
    }

    currentHistoryOffset += historyBatchSize;
    isRenderingBatch = false;

    if (currentHistoryOffset < curHistData.length && currentHistoryOffset === historyBatchSize) {
        const sentinel = topLayer.el.querySelector('#layer-hist-sentinel');
        historyObserver = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting) renderHistoryBatchLayer();
        }, { rootMargin: '1000px' });
        if (sentinel) historyObserver.observe(sentinel);
    } else if (currentHistoryOffset >= curHistData.length && historyObserver) {
        historyObserver.disconnect();
    }
}

window.openShowLayer = async function(showId) {
    document.getElementById('loader').classList.remove('hidden');
    document.getElementById('loader').style.opacity = '1';

    try {
        const r = await fetch(`/api/webapp/show/${showId}/`);
        if (!r.ok) throw new Error('Not found');
        const show = await r.json();

        let crewHtml = '';
        if (show.crew && show.crew.length > 0) {
            show.crew.forEach((group, index) => {
                crewHtml += `
                <div class="label" style="${index === 0 ? '' : 'padding-top:0'}"><div class="icon" style="color:#d29922">${Icons.users}</div>${group.profession}</div>
                <div class="h-scroll-container" style="padding-bottom:16px;">
                    ${group.persons.map(p => {
                        const fb = p.fallback_photo_url ? `'${p.fallback_photo_url}'` : 'null';
                        const imgHtml = p.photo_url ? `<img src="${p.photo_url}" class="person-avatar" style="object-fit:cover;" onerror="window.handleImgErr(this, ${fb}, '${p.name.replace(/'/g, "\\'")}')">` : `<div class="person-avatar">${p.name.charAt(0)}</div>`;
                        return `
                        <div class="person-pill" onclick="window.App.openCollectionLayer('person', ${p.id}, '${p.name.replace(/'/g, "\\'")}')">
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
            <div class="label" style="padding-top:0"><div class="icon" style="color:var(--info)">${Icons.star}</div>Жанры</div>
            <div class="h-scroll-container">
                ${show.genres.map(g => `<div class="genre-pill" onclick="window.App.openCollectionLayer('genre', ${g.id}, '${g.name}')">${g.name}</div>`).join('')}
            </div>`;
        }

        let countriesHtml = '';
        if (show.countries && show.countries.length > 0) {
            countriesHtml = `
            <div class="label" style="padding-top:0"><div class="icon" style="color:#39d353">${Icons.globe}</div>Страны</div>
            <div class="h-scroll-container" style="padding-bottom:30px;">
                ${show.countries.map(c => `<div class="genre-pill" onclick="window.App.openCollectionLayer('country', ${c.id}, '${c.name}')">${c.emoji ? c.emoji + ' ' : ''}${c.name}</div>`).join('')}
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
        
        const html = `
            ${getLayerHeader('О шоу')}
            <div class="hero-container">
                <div class="hero-bg" style="background-image: url('${bgUrl}')"></div>
                <div class="hero-gradient"></div>
                <div style="position: relative; z-index: 3; height: 85%; max-width: 65%; display: flex; align-items: flex-end;">
                    ${posterUrl ? `<img src="${posterUrl}" class="hero-poster" style="max-width: 100%; height: 100%; margin: 0; box-shadow: none;" alt="poster">` : ''}
                    <button class="wishlist-add-btn detail-wishlist-btn anim-item" style="animation-delay: 0.6s;" onclick="window.App.showFolderModal(${show.id}, '${safeTitle}')">${Icons.bookmark_plus}</button>
                </div>
            </div>
            
            <div class="show-info">
                <div class="show-title">${show.title}</div>
                ${show.original_title && show.original_title !== show.title ? `<div class="show-orig">${show.original_title}</div>` : ''}
                
                <div class="show-meta-tags">
                    <div class="sm-tag">${show.year || '?'}</div>
                    <div class="sm-tag" style="color: var(--info); border-color: var(--info-dim); background: var(--info-dim)">${show.type || 'Show'}</div>
                    ${show.status ? `<div class="sm-tag">${show.status}</div>` : ''}
                </div>
                
                <div class="show-meta-tags" style="animation-delay: 0.35s">
                    ${show.kinopoisk_rating ? `<div class="sm-tag" style="background:rgba(241, 90, 36, 0.15); color:#f15a24; border:none">KP ${show.kinopoisk_rating}</div>` : ''}
                    ${show.imdb_rating ? `<div class="sm-tag" style="background:rgba(245, 197, 24, 0.15); color:#f5c518; border:none">IMDb ${show.imdb_rating}</div>` : ''}
                    ${show.internal_rating ? `<div class="sm-tag" style="background:var(--accent-dim); color:var(--accent); border:none">★ ${show.internal_rating.toFixed(1)}</div>` : ''}
                </div>
            </div>

            ${show.plot ? `<div class="plot-box">${show.plot}</div>` : ''}
            
            ${crewHtml}
            ${genresHtml}
            ${countriesHtml}
        `;

        pushLayer(html, { type: 'show' });
    } catch (e) {
        showToast('Не удалось загрузить данные шоу');
    } finally {
        hideLoader();
    }
};

window.openCollectionLayer = async function(type, id, titleFallback) {
    document.getElementById('loader').classList.remove('hidden');
    document.getElementById('loader').style.opacity = '1';

    try {
        const r = await fetch(`/api/webapp/collection/${type}/${id}/`);
        if (!r.ok) throw new Error('Not found');
        const data = await r.json();

        let gridHtml = data.items.map(item => {
            const mediumPoster = item.poster_url || '';
            const posterHtml = mediumPoster ? `<img src="${mediumPoster}" class="grid-poster" loading="lazy">` : '<div class="grid-poster"></div>';
            return `
            <div class="grid-item-wrap anim-item" onclick="window.App.openShowLayer(${item.id})">
                <div class="grid-item">
                    ${posterHtml}
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
                ? `<img src="${p.photo_url}" class="person-avatar" style="width:60px; height:60px; object-fit:cover; flex-shrink:0;" onerror="window.handleImgErr(this, ${fb}, '${safeName}')">`
                : `<div class="person-avatar" style="width:60px; height:60px; flex-shrink:0; font-size:24px;">${titleFallback.charAt(0)}</div>`;
            
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
            headerSectionHtml = `<div class="label"><div class="icon" style="color:var(--info)">${Icons.star}</div>${data.title || titleFallback}</div>`;
        }

        const html = `
            ${getLayerHeader(data.title || titleFallback)}
            ${headerSectionHtml}
            <div class="hist-grid" style="padding: 0 16px;">
                ${gridHtml}
            </div>
        `;

        pushLayer(html, { type: 'collection' });
    } catch (e) {
        showToast('Не удалось загрузить данные коллекции');
    } finally {
        hideLoader();
    }
};

let viewStack =[]; 

function pushLayer(htmlContent, contextData = {}) {
    const layer = document.createElement('div');
    layer.className = 'layer';
    layer.innerHTML = htmlContent;
    
    document.getElementById('dynamic-layers').appendChild(layer);
    
    const container = getScrollContainer();
    const prevScroll = container.scrollTop;
    
    if (viewStack.length > 0) {
        viewStack[viewStack.length - 1].scrollPos = prevScroll;
        viewStack[viewStack.length - 1].el.style.display = 'none';
    } else {
        lastScrollPos = prevScroll;
    }

    viewStack.push({ el: layer, context: contextData, scrollPos: 0 });
    
    if (tg?.BackButton) { 
        tg.BackButton.show(); 
        tg.BackButton.onClick(popLayer); 
    }
}

function popLayer() {
    if (viewStack.length === 0) return;
    
    const top = viewStack.pop();
    top.el.remove();

    if (viewStack.length > 0) {
        const prev = viewStack[viewStack.length - 1];
        prev.el.style.display = 'block';
        prev.el.scrollTop = prev.scrollPos;
    } else {
        document.getElementById('view-' + activeMainView).style.display = 'block';
        if (!isSharedMode) document.getElementById('bottom-nav').style.display = 'flex';
        
        getScrollContainer().scrollTop = lastScrollPos;
        
        if (tg?.BackButton) { 
            tg.BackButton.hide(); 
            tg.BackButton.offClick(popLayer); 
        }
    }
}

window.closeHistory = popLayer;

function getLayerHeader(title) {
    return `
    <div class="layer-header">
        <button onclick="popLayer()" class="tab clickable" style="background:var(--bg-input); color:var(--text-primary); margin:0; display:inline-flex; border:none; padding:8px 16px;">
            <svg viewBox="0 0 24 24" width="18" height="18" style="margin-right:6px;"><path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg> Назад
        </button>
        <span style="font-weight:800; color:var(--text-primary); font-size:16px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:50%;">${title}</span>
        <div style="width: 80px;"></div>
    </div>`;
}

function renderGroup() {
    const el = document.getElementById('group-root');
    if (!D.group) { 
        el.innerHTML = `<div class="card hoverable"><div class="empty"><div class="icon" style="font-size:clamp(36px, 10vw, 48px);line-height:1;color:var(--text-muted)">${Icons.users}</div>Вы не состоите в группе</div></div>`; 
        return; 
    }
    
    const g = D.group, p = D.summary;
    const subjectLabel = isSharedMode ? D.meta.name : 'Вы';
    
    const rows = [ 
        { lb:'Просмотры', i:Icons.tv, y:p.total_views, gv:g.total_views }, 
        { lb:'Эпизоды', i:Icons.film, y:p.total_episodes, gv:g.total_episodes }, 
        { lb:'Фильмы', i:Icons.time, y:p.total_movies, gv:g.total_movies }, 
        { lb:'Уникальных', i:Icons.star, y:p.unique_shows, gv:g.unique_shows } 
    ];
    
    let hasDiff = false;
    const cmpH = rows.map((r, idx) => { 
        const d = r.y - r.gv; 
        let dh = d===0 ? `<span class="cmp-d d-eq"><div class="icon" style="font-size:clamp(12px, 3.2vw, 14px);display:inline-block;vertical-align:middle;line-height:1">${Icons.check}</div> Мэтч</span>` : (hasDiff = true, `<span class="cmp-d ${d>0?'d-up':'d-dn'}">${d>0?'+':''}${d}</span>`); 
        return `<div class="cmp anim-item" style="animation-delay:${(idx+1)*0.05}s"><span class="cmp-lb"><div class="icon" style="font-size:clamp(16px, 4.5vw, 20px);line-height:1;color:var(--text-muted)">${r.i}</div>${r.lb}</span><div class="cmp-vs"><span class="cmp-v cmp-you">${r.y}</span><span style="color:var(--text-muted);font-size:clamp(11px, 3vw, 13px)">vs</span><span class="cmp-v cmp-grp">${r.gv}</span>${dh}</div></div>`; 
    }).join('');
    
    const mx = Math.max(...g.members.map(m=>m.views),1);
    const mbH = g.members.map((m, idx) => `<div class="mb anim-list-item clickable" onclick="window.openHistoryLayer('group_member', '${m.name.replace(/'/g, "\\'")}', null, null, null, ${idx})" style="animation-delay:${(idx+1)*0.05}s"><span class="mb-n">${m.name}</span><div class="mb-t"><div class="mb-f" style="width:${(m.views/mx)*100}%"></div></div><span class="mb-c">${m.views}</span></div>`).join('');
    let gGenH = g.genres?.length ? `<div class="card hoverable anim-item" style="animation-delay:0.3s"><div class="label"><div class="icon" style="font-size:clamp(16px, 4.5vw, 18px);line-height:1">${Icons.masks}</div>Жанры группы</div><div class="chart-box" style="height:380px;"><canvas id="c-group-genre"></canvas></div><div id="legend-group-genre" class="legend-grid"></div></div>` : '';
    const membersLabel = `${g.members_count} ${plural(g.members_count, ['участник', 'участника', 'участников'])}`;
    
    el.innerHTML = `
        <div class="card hoverable anim-item">
            <div style="display:flex;align-items:center;gap:16px">
                <div class="icon" style="font-size:clamp(28px, 8vw, 36px);line-height:1;color:var(--info);filter:drop-shadow(0 4px 8px rgba(56, 139, 253, 0.3))">${Icons.users}</div>
                <div>
                    <div style="font-size:clamp(16px, 4.5vw, 20px);font-weight:800;color:var(--text-primary)">${g.group_name}</div>
                    <div style="font-size:clamp(12px, 3.2vw, 14px);color:var(--text-muted);font-weight:600;margin-top:2px;">${membersLabel} · ${g.duration_display}</div>
                </div>
            </div>
        </div>
        <div class="card hoverable anim-item" style="animation-delay:0.1s">
            <div class="label more-pad"><div class="icon" style="font-size:clamp(16px, 4.5vw, 18px);line-height:1">${Icons.chart}</div>${subjectLabel} vs Группа</div>
            <div style="display:flex;justify-content:space-between;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--border)">
                <span style="font-size:clamp(12px, 3.2vw, 14px);font-weight:800;color:var(--accent);letter-spacing:0.5px;text-transform:uppercase;">👤 ${subjectLabel}</span>
                <span style="font-size:clamp(12px, 3.2vw, 14px);font-weight:800;color:var(--info);letter-spacing:0.5px;text-transform:uppercase;">👥 Группа</span>
            </div>
            ${!hasDiff?`<div style="text-align:center;padding:16px 0;font-size:clamp(15px, 4 vw, 18px);color:var(--accent);font-weight:800;display:flex;align-items:center;justify-content:center;gap:8px;animation:pulse 2s infinite;"><div class="icon" style="font-size:clamp(20px, 6vw, 24px);line-height:1">${Icons.check}</div> Полный мэтч!</div>`:''}
            ${cmpH}
        </div>
        <div class="card hoverable anim-item" style="animation-delay:0.2s">
            <div class="label more-pad"><div class="icon" style="font-size:clamp(16px, 4.5vw, 18px);line-height:1">${Icons.user}</div>Участники</div>
            ${mbH}
        </div>
        ${gGenH}`;
}

function openShareModal() {
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

    toggleGroupOpts();
    document.getElementById('share-modal').classList.add('show');
}

document.getElementById('share-modal').addEventListener('click', (e) => {
    if (e.target.id === 'share-modal') {
        closeShareModal();
    }
});

function closeShareModal() {
    document.getElementById('share-modal').classList.remove('show');
}

function toggleGroupOpts() {
    const incGroup = document.getElementById('sh-inc-group').checked;
    const anonGroupWrap = document.getElementById('sh-anon-group-wrap');
    if (!incGroup) {
        anonGroupWrap.style.opacity = '0.4';
        anonGroupWrap.style.pointerEvents = 'none';
    } else {
        anonGroupWrap.style.opacity = '1';
        anonGroupWrap.style.pointerEvents = 'auto';
    }
}

async function submitShare() {
    const btn = document.getElementById('btn-do-share');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner" style="width:20px;height:20px;border-width:2px;border-color:rgba(255,255,255,0.3);border-top-color:#fff;"></div> Создание...';

    const checkedYears = Array.from(document.querySelectorAll('.yr-chk-input:checked')).map(el => el.value);
    
    if (checkedYears.length === 0) {
        showToast('Выберите хотя бы один период');
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
            showToast('Ошибка при создании слепка');
        } else {
            closeShareModal();
            if (tg) {
                tg.switchInlineQuery("share_" + j.id, ["users", "groups", "channels"]);
            }
        }
    } catch(e) {
        showToast('Сетевая ошибка');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg> Создать ссылку';
    }
}

window.App = {
    ...window.App,
    toggleTheme: toggleTheme,
    openShareModal: openShareModal,
    closeShareModal: closeShareModal,
    toggleGroupOpts: toggleGroupOpts,
    submitShare: submitShare,
    mainTab: mainTab,
    pickYear: pickYear,
    openHistory: window.openHistoryLayer,
    openHistoryLayer: window.openHistoryLayer,
    closeHistory: popLayer,
    setViewMode: window.setViewModeLayer,
    setViewModeLayer: window.setViewModeLayer,
    openShowLayer: window.openShowLayer,
    openCollectionLayer: window.openCollectionLayer,
    doSearch: doSearch,
    switchMainView: switchMainView,
    openCasino: window.openCasino,
    closeCasino: window.closeCasino,
    resetCasino: window.resetCasino,
    startCasinoSpin: window.startCasinoSpin,
};

window.init = async function() {
    // 1. Устанавливаем иконки темы
    document.querySelectorAll('.theme-btn').forEach(btn => {
        btn.innerHTML = isDark ? Icons.moon : Icons.sun;
    });

    // 2. Инициализируем иконки интерфейса
    initIcons();

    // 3. Запускаем основную логику загрузки данных
    const startParam = tg?.initDataUnsafe?.start_param || '';
    const urlParams = new URLSearchParams(window.location.search);
    const sharedIdFromUrl = urlParams.get('shared_id');
    const showIdFromUrl = urlParams.get('show_id') || (startParam.startsWith('show_') ? startParam.replace('show_', '') : null);
    const viewFromUrl = urlParams.get('view');

    if (sharedIdFromUrl || startParam.startsWith('stat_')) {
        isSharedMode = true;
        document.body.classList.add('has-banner');
        document.getElementById('share-btn').classList.add('hidden');
        document.getElementById('bottom-nav').style.display = 'none';
        switchMainView('stats');
        
        const sid = sharedIdFromUrl || startParam.replace('stat_', '');
        await loadShared(sid);
    } else {
        await load();
        const role = D?.meta?.role || 'guest';
        document.getElementById('bottom-nav').style.display = 'flex';
        document.body.classList.add('has-nav');
        if (role === 'guest') document.getElementById('bn-stats').classList.add('hidden');
        
        switchMainView(viewFromUrl || 'search');
        if (showIdFromUrl) window.App.openShowLayer(showIdFromUrl);
    }
};