window.App = window.App || {};

Object.assign(window.App, {
    folderLongPressTimer: null,
    isFolderLongPress: false,

    activeWlFolderId: null,
    wlFoldersSortable: null,
    wlItemsSortable: null,

    wishlistFolders: [],
    itemToDeleteId: null,
    itemToDeleteElement: null,

    editFolderMode: 'create',
    activeShowForWishlist: null,

    FOLDER_COLORS: [
        '#388bfd',
        '#2ecc71',
        '#e74c3c',
        '#f1c40f',
        '#9b59b6',
        '#e67e22',
        '#1abc9c',
        '#95a5a6',
        '#fd79a8',
    ],

    FOLDER_ICONS: [
        // Ряд 1: Базовые и системные (папки, избранное, поиск)
        'bookmark', 'folder', 'heart', 'star', 'bookmark_plus', 'check', 'search',

        // Ряд 2: Кино и просмотр (основная тематика сервиса)
        'film', 'video', 'play_circle', 'tv', 'monitor', 'ticket', 'award',

        // Ряд 3: Персонажи и настроение (социальное и эмоции)
        'user', 'users', 'smile', 'frown', 'music', 'coffee', 'globe',

        // Ряд 4: Экшен, триллер, вайб (динамика и жанровость)
        'zap', 'flame', 'rocket', 'eye', 'ghost', 'skull', 'trash',

        // Ряд 5: Планирование и статистика (время и списки)
        'clock', 'cal', 'days', 'list', 'target', 'chart', 'help'
    ],

    handleFolderPointerDown: function(id) {
        if (window.App.getState('flags.isReorderMode')) return;

        window.App.isFolderLongPress = false;
        window.App.folderLongPressTimer = setTimeout(() => {
            window.App.isFolderLongPress = true;
            window.App.openFolderEditModal(true, id);
            if (window.navigator.vibrate) window.navigator.vibrate(50);
        }, 600);
    },

    handleFolderPointerUp: function() {
        clearTimeout(window.App.folderLongPressTimer);
    },

    sendWishlistAction: async function(action, payload = {}) {
        const r = await fetch('/api/webapp/wishlist/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                action,
                ...payload,
                init_data: tg?.initData || '',
            }),
        });

        if (!r.ok) {
            throw new Error('Network response error');
        }

        return r.json();
    },

    renderColorPicker: function(activeColor) {
        const cont = document.getElementById('wl-color-picker');

        cont.innerHTML = window.App.FOLDER_COLORS.map(c => `
            <div 
                class="wl-color-btn ${c === activeColor ? 'active' : ''}" 
                style="background-color: ${c}" 
                onclick="window.App.selectFolderColor('${c}')">
            </div>
        `).join('');
    },

    renderIconPicker: function(activeIcon) {
        const cont = document.getElementById('wl-icon-picker');

        cont.innerHTML = window.App.FOLDER_ICONS.map(i => `
            <div 
                class="wl-icon-btn ${i === activeIcon ? 'active' : ''}" 
                onclick="window.App.selectFolderIcon('${i}')">
                ${window.App.Icons[i]}
            </div>
        `).join('');
    },

    renderWishlistFolders: function() {
        const grid = document.getElementById('wl-folders-grid');
        if (!grid) return;
        
        const wrapper = document.getElementById('wl-folders-wrapper');
        const activeId = window.App.getState('data.activeWlFolderId');

        if (wrapper) {
            wrapper.style.display = window.App.wishlistFolders.length > 1 ? 'block' : 'none';
        }

        if (!window.App.wishlistFolders.length) {
            grid.innerHTML = '<div class="empty" style="grid-column:1/-1">Нет папок</div>';
            return;
        }

        grid.innerHTML = window.App.wishlistFolders.map(f => `
            <div class="wl-folder-card ${f.id === activeId ? 'active' : ''}" 
                data-id="${f.id}" 
                onpointerdown="window.App.handleFolderPointerDown(${f.id})"
                onpointerup="window.App.handleFolderPointerUp()"
                onclick="if(!window.App.isFolderLongPress && !window.App.getState('flags.isReorderMode')) window.App.selectWlFolder(${f.id})">
                <div class="wl-delete-badge" onclick="event.stopPropagation(); window.App.deleteWlFolder(${f.id}, this.parentElement)">
                    ${window.App.Icons.minus}
                </div>
                <div class="wl-folder-inner">
                    <div class="wl-folder-icon" style="background: ${f.color}20; color: ${f.color};">
                        ${window.App.Icons[f.icon] || window.App.Icons.folder}
                    </div>
                    <div class="wl-folder-info">
                        <div class="wl-folder-name">${f.name}</div>
                        <div class="wl-folder-count">${f.items.length} ${window.App.plural(f.items.length, ['шоу', 'шоу', 'шоу'])}</div>
                    </div>
                </div>
            </div>
        `).join('');

        requestAnimationFrame(() => window.App.fitAll('.wl-folder-name', grid));
    },

    renderActiveWlFolder: function() {
        const content = document.getElementById('wl-active-folder-content');
        const titleEl = document.getElementById('wl-active-folder-title');
        const container = document.getElementById('wl-items-container');
        const mainHeader = document.getElementById('wl-main-header');
        // ПРИМЕЧАНИЕ: globalToggle пока оставим здесь, так как он зависит от сложной логики наличия папок,
        // но в будущем вынесем в ui.wishlistControlsVisible
        const globalToggle = document.getElementById('wl-global-view-toggle');

        const folders = window.App.wishlistFolders || [];
        const activeId = window.App.activeWlFolderId;

        // Получаем значения из StateManager
        const wlSortMode = window.App.getState('ui.sortMode') || 'default';
        const wlViewMode = window.App.getState('ui.wlViewMode') || 'grid';
        const isItemsReorderMode = window.App.getState('flags.isItemsReorderMode') || false;

        if (!activeId) {
            if (mainHeader) mainHeader.textContent = 'Избранное';
            if (content) content.style.display = 'none';
            if (globalToggle) globalToggle.style.display = 'none';
            return;
        }

        const folder = folders.find(f => f.id === activeId);
        if (!folder) return;

        if (content) content.style.display = 'block';
        if (globalToggle) globalToggle.style.display = 'flex';

        if (mainHeader) {
            if (folders.length === 1) {
                mainHeader.innerHTML = `<span style="color:${folder.color}; margin-right: 10px; display: inline-flex; vertical-align: middle;">${window.App.Icons[folder.icon] || window.App.Icons.folder}</span>${folder.name}`;
            } else {
                mainHeader.textContent = 'Мои списки';
            }
            
            mainHeader.style.fontSize = "";
            requestAnimationFrame(() => window.App.fitText(mainHeader));
        }

        if (titleEl) {
            titleEl.innerHTML = `<span style="color:${folder.color}; margin-right: 8px; display: inline-flex; vertical-align: middle;">${window.App.Icons[folder.icon] || window.App.Icons.folder}</span>${folder.name}`;
            titleEl.style.display = folders.length > 1 ? 'flex' : 'none';
        }

        requestAnimationFrame(() => {
            if (mainHeader) window.App.fitText(mainHeader);
            if (titleEl && folders.length > 1) window.App.fitText(titleEl);
        });

        document.getElementById('wl-vt-grid')?.classList.toggle('active', wlViewMode === 'grid');
        document.getElementById('wl-vt-list')?.classList.toggle('active', wlViewMode === 'list');

        const triggerBtn = document.getElementById('wl-sort-trigger');
        if (triggerBtn) {
            let triggerText = 'Сортировка';
            let triggerIcon = window.App.Icons.reorder;
            let arrowClass = '';

            if (wlSortMode.startsWith('added')) {
                triggerText = 'По дате';
                triggerIcon = window.App.Icons.sort_arrow;
                arrowClass = wlSortMode.endsWith('asc') ? 'rotate-180' : '';
            } else if (wlSortMode.startsWith('year')) {
                triggerText = 'По году';
                triggerIcon = window.App.Icons.sort_arrow;
                arrowClass = wlSortMode.endsWith('asc') ? 'rotate-180' : '';
            } else {
                triggerText = 'Порядок';
                triggerIcon = window.App.Icons.reorder;
            }

            triggerBtn.innerHTML = `
                <span class="sort-icon-main ${arrowClass}">${triggerIcon}</span>
                <span class="sort-text-label">${triggerText}</span>
                <span class="sort-chevron">${window.App.Icons.chevron_down}</span>
            `;
        }

        document.querySelectorAll('.sort-item').forEach(item => {
            const opt = item.dataset.sort;
            let isActive = false;
            if (opt === 'default' && wlSortMode === 'default') isActive = true;
            if (opt === 'added' && wlSortMode.startsWith('added')) isActive = true;
            if (opt === 'year' && wlSortMode.startsWith('year')) isActive = true;

            item.classList.toggle('active', isActive);

            const arrow = item.querySelector('.sort-arrow-icon');
            if (arrow && isActive) {
                arrow.classList.toggle('rotate-180', wlSortMode.endsWith('asc'));
            }
        });

        const reorderBtn = document.getElementById('wl-items-reorder-btn');
        if (reorderBtn) {
            reorderBtn.style.display = (folder.items.length > 1 && wlSortMode === 'default') ? 'flex' : 'none';
            if (isItemsReorderMode && (folder.items.length <= 1 || wlSortMode !== 'default')) {
                window.App.toggleItemsReorderMode();
            }
            reorderBtn.style.background = isItemsReorderMode ? 'var(--accent)' : 'var(--bg-input)';
            reorderBtn.style.color = isItemsReorderMode ? '#fff' : 'var(--text-primary)';
        }
        
        container?.classList.toggle('reorder-items-mode', isItemsReorderMode);

        if (!folder.items.length) {
            if (container) container.innerHTML = `<div class="empty"><div class="icon">${window.App.Icons.film}</div>Папка пуста</div>`;
            if (window.App.wlItemsSortable) { window.App.wlItemsSortable.destroy(); window.App.wlItemsSortable = null; }
            return;
        }

        let renderItems = [...folder.items];
        if (wlSortMode === 'added_desc') {
            renderItems.sort((a, b) => new Date(b.added_at) - new Date(a.added_at) || b.id - a.id);
        } else if (wlSortMode === 'added_asc') {
            renderItems.sort((a, b) => new Date(a.added_at) - new Date(b.added_at) || a.id - b.id);
        } else if (wlSortMode === 'year_desc') {
            renderItems.sort((a, b) => (b.year || 0) - (a.year || 0) || b.id - a.id);
        } else if (wlSortMode === 'year_asc') {
            renderItems.sort((a, b) => (a.year || 0) - (b.year || 0) || a.id - b.id);
        }

        let itemsHtml = renderItems.map((item, idx) => window.App.getWlItemHtml(item, wlViewMode, idx)).join('');

        if (container) {
            if (wlViewMode === 'list') {
                container.innerHTML = `<div class="card" style="margin:0; padding:0; overflow:hidden; border:none; background:transparent;">${itemsHtml}</div>`;
            } else {
                container.innerHTML = `<div class="hist-grid">${itemsHtml}</div>`;
            }
            
            requestAnimationFrame(() => {
                window.App.fitAll('.grid-below-title', container);
                window.App.fitAll('.grid-below-orig', container);
                window.App.fitAll('.hist-title', container);
                window.App.fitAll('.hist-orig', container);
            });
        }

        if (typeof Sortable !== 'undefined' && container) {
            if (window.App.wlItemsSortable) window.App.wlItemsSortable.destroy();
            const targetContainer = container.querySelector('.hist-grid, .card');
            if (targetContainer) {
                window.App.wlItemsSortable = new Sortable(targetContainer, {
                    group: 'wl-items',
                    animation: 350,
                    easing: "cubic-bezier(0.25, 1, 0.5, 1)",
                    disabled: !isItemsReorderMode,
                    forceFallback: true,
                    fallbackOnBody: true,
                    fallbackClass: 'sortable-fallback',
                    ghostClass: 'sortable-ghost',
                    onStart: function (evt) {
                        if (window.navigator.vibrate) window.navigator.vibrate(10);
                        document.body.classList.add('sorting-active');
                    },
                    onEnd: function (evt) {
                        document.body.classList.remove('sorting-active');
                        if (evt.to === targetContainer) {
                            const order = Array.from(targetContainer.children).map(el => parseInt(el.dataset.id));
                            const folder = window.App.wishlistFolders.find(f => f.id === activeId);
                            if (folder) {
                                const newItems = [];
                                order.forEach(id => {
                                    const it = folder.items.find(x => x.id === id);
                                    if (it) newItems.push(it);
                                });
                                folder.items = newItems;
                            }
                            window.App.sendWishlistAction('reorder_items', { folder_id: activeId, order });
                        }
                    }
                });
            }
        }
    },

    getWlItemHtml: function(item, viewModeStr, idx) {
        const sid = item.show_id;
        const addedDate = item.added_at || '';
        const delay = idx * 0.05;
        const animClass = window.App.isItemsReorderMode ? '' : 'anim-item';
        const style = window.App.isItemsReorderMode ? '' : `style="animation-delay: ${delay}s"`;

        const deleteBtn = `<div class="wl-delete-badge" onclick="event.stopPropagation(); window.App.removeWlItem(${item.id}, this.parentElement)">${window.App.Icons.minus}</div>`;

        if (viewModeStr === 'list') {
            const poster = item.poster_url ? `<img src="${item.poster_url}" class="hist-poster" loading="lazy" draggable="false">` : `<div class="hist-poster"></div>`;
            
            let ratingHtml = '';
            if (item.user_rating) {
                ratingHtml = `<span class="rating-badge">${window.App.Icons.star}${item.user_rating}</span>`;
            }

            return `
            <div class="hist-item clickable ${animClass}" ${style} data-id="${item.id}" onclick="if(!window.App.isItemsReorderMode) window.App.openShowLayer(${sid})">
                ${deleteBtn}
                ${poster}
                <div class="hist-info">
                    <div class="hist-title">${item.title}</div>
                    ${item.original_title && item.original_title !== item.title ? `<div class="hist-orig">${item.original_title}</div>` : ''}
                    <div class="hist-meta">
                        ${item.year ? `<span>${item.year}</span>` : ''}
                        ${item.type ? `<span>· ${window.App.SHOW_TYPE_RU[item.type] || item.type}</span>` : ''}
                        ${ratingHtml}
                        <span style="opacity: 0.6;">· ${addedDate}</span>
                    </div>
                </div>
            </div>`;
        } else {
            const mediumPoster = item.poster_url ? item.poster_url.replace('/small/', '/medium/') : '';
            const posterHtml = mediumPoster ? `<img src="${mediumPoster}" class="grid-poster" loading="lazy" draggable="false">` : '<div class="grid-poster"></div>';
            const yearHtml = item.year ? `<div class="grid-year">${item.year}</div>` : '';

            let badgesHtml = '';
            if (item.user_rating) {
                badgesHtml = `<span class="rating-badge" style="background:rgba(0,0,0,0.6);border:none;">${window.App.Icons.star}${item.user_rating}</span>`;
            }

            return `
            <div class="grid-item-wrap ${animClass}" ${style} data-id="${item.id}" onclick="if(!window.App.isItemsReorderMode) window.App.openShowLayer(${sid})">
                ${deleteBtn}
                <div class="grid-item">
                    ${posterHtml}
                    <div class="grid-badges">${badgesHtml}</div>
                    ${yearHtml}
                    <div class="grid-overlay">
                        <div class="grid-date" style="color: var(--text-muted);">${addedDate}</div>
                    </div>
                </div>
                <div class="grid-below-title">${item.title}</div>
                ${item.original_title && item.original_title !== item.title ? `<div class="grid-below-orig">${item.original_title}</div>` : ''}
            </div>`;
        }
    },

    loadWishlist: async function() {
        const grid = document.getElementById('wl-folders-grid');
        if (!window.App.getState('data.wishlistFolders').length) {
            grid.innerHTML = '<div class="loader-inline"><div class="spinner" style="width:32px;height:32px;border-width:3px;"></div></div>';
        }

        try {
            const data = await window.App.sendWishlistAction('get');
            const folders = data.folders || [];
            
            window.App.setState('data.wishlistFolders', folders);

            let activeId = window.App.getState('nav.query.folderId');
            const folderExists = folders.some(f => f.id === activeId);
            
            if (!folderExists && folders.length > 0) {
                activeId = folders[0].id;
                window.App.setState('nav.query.folderId', activeId);
            }
            
            window.App.setState('data.activeWlFolderId', activeId);
        } catch (e) {
            grid.innerHTML = '<div class="empty">Ошибка загрузки</div>';
        }
    },
    selectWlFolder: function(id) {
        window.App.setState('data.activeWlFolderId', id);
        window.App.setState('nav.query.folderId', id);
        // Больше никакого ручного вызова рендеринга!
        window.App.Router.updateUrl();
    },

    initWishlistReactivity: function() {
        window.App.subscribe('data.wishlistFolders', (val) => {
            window.App.wishlistFolders = val || [];
            window.App.renderWishlistFolders();
        });
        
        window.App.subscribe('data.activeWlFolderId', () => window.App.renderActiveWlFolder());
        window.App.subscribe('ui.wlViewMode', () => window.App.renderActiveWlFolder());
        window.App.subscribe('ui.sortMode', () => window.App.renderActiveWlFolder());
        window.App.subscribe('flags.isItemsReorderMode', (active) => {
            document.getElementById('wl-items-container')?.classList.toggle('reorder-items-mode', active);
            if (window.App.wlItemsSortable) window.App.wlItemsSortable.option('disabled', !active);
        });

        window.App.subscribe('ui.isSortMenuOpen', (val) => {
            const menu = document.getElementById('wl-sort-menu');
            if (menu) menu.classList.toggle('show', val);
        });
    },

    setWlViewMode: function (mode) {
        window.App.setState('ui.wlViewMode', mode);
        localStorage.setItem('kp_wl_view_mode', mode);
    },

    setWlSortMode: function (mode) {
        window.App.setState('ui.sortMode', mode);
    },

    toggleReorderMode: function () {
        const cur = window.App.getState('flags.isReorderMode');
        window.App.setState('flags.isReorderMode', !cur);
        
        if (window.App.wlFoldersSortable) {
            window.App.wlFoldersSortable.option('disabled', cur); 
        }
        window.App.renderWishlistFolders();
    },

    toggleItemsReorderMode: function() {
        const cur = window.App.getState('flags.isItemsReorderMode');
        window.App.setState('flags.isItemsReorderMode', !cur);
    },

    confirmDeleteWlItem: function (id) {
        const item = window.App.wishlistFolders.flatMap(f => f.items).find(i => i.id === id);
        if (item) {
            const textEl = document.getElementById('wl-delete-confirm-text');
            if (textEl) {
                textEl.innerHTML = `Вы уверены, что хотите удалить <b style="color:var(--text-primary)">«${item.title}»</b>?`;
            }
        }
        window.App.setState('modals.wlDelete', { isOpen: true, context: { id }});
    },
    removeWlItem: function (id, element) {
        window.App.itemToDeleteId = id;
        window.App.itemToDeleteElement = element;
        window.App.confirmDeleteWlItem(id);
    },
    removeWlStatItem: function(itemId, el) {
        const msg = "Вы уверены? Это действие безвозвратно удалит шоу из статистики избранного.";
        
        if (window.Telegram?.WebApp?.showConfirm) {
            window.Telegram.WebApp.showConfirm(msg, async function(confirmed) {
                if (confirmed) await performDelete(itemId, el);
            });
        } else {
            if (confirm(msg)) performDelete(itemId, el);
        }

        async function performDelete(id, element) {
            if (element) {
                element.style.transition = 'all 0.3s ease';
                element.style.opacity = '0';
                element.style.transform = 'scale(0.8)';
                setTimeout(() => element.remove(), 300);
            }
            try {
                await window.App.sendWishlistAction('remove_item', { 
                    item_id: id, 
                    keep_stats: false,
                    is_stat_removal: true 
                });
                
                const counterEl = document.getElementById('s-wl-watched');
                if (counterEl) {
                    let current = parseInt(counterEl.textContent) || 0;
                    if (current > 0) counterEl.textContent = current - 1;
                }
                
                if (window.App.D && window.App.D.wishlist_watched_items) {
                    window.App.D.wishlist_watched_items = window.App.D.wishlist_watched_items.filter(i => i.wl_item_id !== id);
                }
            } catch (e) {}
        }
    },
    closeItemDeleteModal: () => window.App.closeModal('wlDelete'),
    confirmItemDelete: function () {
        if (!window.App.itemToDeleteId) return;
        const keepStats = document.getElementById('wl-del-keep-stats').checked;
        const id = window.App.itemToDeleteId;
        const element = window.App.itemToDeleteElement;

        window.App.closeItemDeleteModal();

        if (element) {
            element.classList.add('anim-shrink');
            element.addEventListener('animationend', () => {
                const folder = window.App.wishlistFolders.find(f => f.id === window.App.activeWlFolderId);
                if (folder) {
                    folder.items = folder.items.filter(i => i.id !== id);
                }
                window.App.renderActiveWlFolder();
                window.App.renderWishlistFolders();
            }, { once: true });
        }

        window.App.sendWishlistAction('remove_item', { item_id: id, keep_stats: keepStats });
        window.App.showToast('Удалено');
    },
    deleteWlFolder: async function (id, element) {
        if (!confirm('Удалить папку и всё её содержимое?')) return;

        if (element) {
            element.classList.add('anim-shrink');
            element.addEventListener('animationend', async () => {
                window.App.wishlistFolders = window.App.wishlistFolders.filter(f => f.id !== id);

                if (window.App.wishlistFolders.length <= 1) {
                    const reorderBtn = document.getElementById('wl-reorder-btn');
                    if (reorderBtn) reorderBtn.style.display = 'none';
                    if (window.App.isReorderMode) window.App.toggleReorderMode();
                }

                if (window.App.wishlistFolders.length === 0) {
                    window.App.activeWlFolderId = null;
                    document.getElementById('wl-active-folder-content').style.display = 'none';
                    document.getElementById('wl-folders-grid').innerHTML = '<div class="loader-inline"><div class="spinner" style="width:32px;height:32px;border-width:3px;"></div></div>';
                    await window.App.sendWishlistAction('delete_folder', { folder_id: id });
                    await loadWishlist();
                    return;
                }

                if (window.App.activeWlFolderId === id) {
                    window.App.activeWlFolderId = window.App.wishlistFolders[0].id;
                }

                window.App.renderWishlistFolders();
                window.App.renderActiveWlFolder();
            }, { once: true });
        }

        window.App.sendWishlistAction('delete_folder', { folder_id: id });
        window.App.showToast('Папка удалена');
    },
    openFolderEditModal: function (isEdit = false, folderId = null) {
        if (!isEdit && window.App.wishlistFolders.length >= 12) {
            window.App.setState('modals.wlLimit.isOpen', true);
            if (window.navigator.vibrate) window.navigator.vibrate([40, 100, 40]);
            return;
        }

        window.App.editFolderMode = isEdit ? 'edit' : 'create';
        const folder = isEdit ? window.App.wishlistFolders.find(f => f.id === (folderId || window.App.activeWlFolderId)) : null;

        const initialData = {
            name: folder ? folder.name : '',
            color: folder ? folder.color : window.App.FOLDER_COLORS[0],
            icon: folder ? folder.icon : window.App.FOLDER_ICONS[0]
        };

        window.App.setState('forms.wlEdit', initialData);
        window.App.setState('modals.wlEdit', { 
            isOpen: true, 
            context: { isEdit, folderId }
        });

        window.App.renderColorPicker(initialData.color);
        window.App.renderIconPicker(initialData.icon);
    },
    closeFolderEditModal: () => window.App.closeModal('wlEdit'),
    closeLimitModal: () => window.App.closeModal('wlLimit'),
    selectFolderColor: function (color) {
        document.querySelectorAll('.wl-color-btn').forEach(b => b.classList.remove('active'));
        event.currentTarget.classList.add('active');
        document.getElementById('wl-color-picker').dataset.color = color;
    },
    selectFolderIcon: function (icon) {
        document.querySelectorAll('.wl-icon-btn').forEach(b => b.classList.remove('active'));
        event.currentTarget.classList.add('active');
        document.getElementById('wl-icon-picker').dataset.icon = icon;
    },
    saveFolderEdit: async function () {
        const name = document.getElementById('wl-folder-name').value.trim();
        const color = document.getElementById('wl-color-picker').dataset.color;
        const icon = document.getElementById('wl-icon-picker').dataset.icon;

        window.App.closeFolderEditModal();

        if (window.App.editFolderMode === 'create') {
            const tempId = -Date.now();
            window.App.wishlistFolders.push({ id: tempId, name: name || '', color, icon, items: [] });
            window.App.activeWlFolderId = tempId;

            window.App.renderWishlistFolders();
            window.App.renderActiveWlFolder();

            const res = await window.App.sendWishlistAction('create_folder', { name, icon, color });
            if (res.status === 'ok' && res.id) {
                window.App.activeWlFolderId = res.id;
            }
            await loadWishlist();
        } else {
            const folder = window.App.wishlistFolders.find(f => f.id === window.App.activeWlFolderId);
            if (folder) {
                folder.name = name || '';
                folder.color = color;
                folder.icon = icon;
            }
            window.App.renderWishlistFolders();
            window.App.renderActiveWlFolder();

            window.App.sendWishlistAction('edit_folder', { folder_id: window.App.activeWlFolderId, name, icon, color });
        }
    },
    editActiveFolder: function () {
        if (window.App.activeWlFolderId) window.App.openFolderEditModal(true);
    },
    deleteActiveFolder: async function () {
        if (!confirm('Удалить папку и всё её содержимое?')) return;
        window.App.closeFolderEditModal();

        const idToDelete = window.App.activeWlFolderId;
        window.App.wishlistFolders = window.App.wishlistFolders.filter(f => f.id !== idToDelete);

        if (window.App.wishlistFolders.length <= 1) {
            const reorderBtn = document.getElementById('wl-reorder-btn');
            if (reorderBtn) reorderBtn.style.display = 'none';
            if (window.App.isReorderMode) window.App.toggleReorderMode();
        }

        if (window.App.wishlistFolders.length === 0) {
            window.App.activeWlFolderId = null;
            document.getElementById('wl-active-folder-content').style.display = 'none';
            document.getElementById('wl-folders-grid').innerHTML = '<div class="loader-inline"><div class="spinner" style="width:32px;height:32px;border-width:3px;"></div></div>';
            await window.App.sendWishlistAction('delete_folder', { folder_id: idToDelete });
            await loadWishlist();
            return;
        }

        window.App.activeWlFolderId = window.App.wishlistFolders[0].id;

        window.App.renderWishlistFolders();
        window.App.renderActiveWlFolder();

        window.App.sendWishlistAction('delete_folder', { folder_id: idToDelete });
    },
    showFolderModal: async function (showId, title) {
        window.App.activeShowForWishlist = showId;

        if (window.App.wishlistFolders.length === 1) {
            try {
                await window.App.sendWishlistAction('add_item', { folder_id: window.App.wishlistFolders[0].id, show_id: showId });
                window.App.showToast('Успешно добавлено');
            } catch (e) { window.App.showToast('Ошибка при добавлении'); }
            return;
        }

        window.App.setState('modals.wlFolder', { isOpen: true, context: { showId, title } });
        
        const grid = document.getElementById('wl-modal-folders');
        if (grid) grid.innerHTML = '<div class="loader-inline"><div class="spinner"></div></div>';

        try {
            const data = await window.App.sendWishlistAction('get');
            if (data.folders) {
                window.App.wishlistFolders = data.folders;
                if (data.folders.length === 1) {
                    window.App.setState('modals.wlFolder.isOpen', false);
                    await window.App.sendWishlistAction('add_item', { folder_id: data.folders[0].id, show_id: showId });
                    window.App.showToast('Успешно добавлено');
                    return;
                }
                if (grid) {
                    grid.innerHTML = data.folders.map(f => `
                        <div class="wl-folder-card" onclick="window.App.addToFolder(${f.id})">
                            <div class="wl-folder-icon" style="color: ${f.color};">${window.App.Icons[f.icon] || window.App.Icons.folder}</div>
                            <div class="wl-folder-info">
                                <div class="wl-folder-name">${f.name}</div>
                                <div class="wl-folder-count">${f.items.length} элементов</div>
                            </div>
                        </div>
                    `).join('');
                }
            }
        } catch (e) { if (grid) grid.innerHTML = '<div class="empty">Ошибка загрузки</div>'; }
    },
    closeFolderModal: () => window.App.closeModal('wlFolder'),
    addToFolder: async function (folderId) {
        if (!window.App.activeShowForWishlist) return;
        try {
            await window.App.sendWishlistAction('add_item', { folder_id: folderId, show_id: window.App.activeShowForWishlist });
            window.App.showToast('Успешно добавлено');
            window.App.closeFolderModal();
        } catch (e) {
            window.App.showToast('Ошибка при добавлении');
        }
    },

    toggleSortDropdown: function (e) {
        if (e) e.stopPropagation();
        const current = window.App.getState('ui.isSortMenuOpen');
        window.App.setState('ui.isSortMenuOpen', !current);
    },

    setSortOption: function (type) {
        const currentSortMode = window.App.getState('ui.sortMode');
        let newMode = 'default';

        if (type === 'added') {
            newMode = (currentSortMode === 'added_desc') ? 'added_asc' : 'added_desc';
        } else if (type === 'year') {
            newMode = (currentSortMode === 'year_desc') ? 'year_asc' : 'year_desc';
        } else {
            newMode = 'default';
        }

        window.App.setWlSortMode(newMode);
        window.App.setState('ui.isSortMenuOpen', false);
    }
});