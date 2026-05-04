window.App = window.App || {};
let folderLongPressTimer;
let isFolderLongPress = false;
let itemLongPressTimer;
let isItemLongPress = false;
let isItemsReorderMode = false;
let isReorderMode = false;

let activeWlFolderId = null;
let wlViewMode = localStorage.getItem('wl_view_mode') || 'grid';
let wlSortMode = localStorage.getItem('wl_sort_mode') || 'default';
let wlFoldersSortable = null;
let wlItemsSortable = null;
let wishlistFolders = [];
let itemToDeleteId = null;
let itemToDeleteElement = null;

const FOLDER_COLORS = ['#388bfd', '#2ecc71', '#e74c3c', '#f1c40f', '#9b59b6', '#e67e22', '#1abc9c', '#95a5a6', '#fd79a8'];
const FOLDER_ICONS = [
    'folder', 'bookmark', 'star', 'heart',
    'film', 'tv', 'video', 'ticket',
    'award', 'zap', 'rocket',
    'ghost',
    'coffee', 'list'
];

let editFolderMode = 'create';
let activeShowForWishlist = null;

function handleFolderPointerDown(id) {
    if (isReorderMode) return;
    isFolderLongPress = false;
    folderLongPressTimer = setTimeout(() => {
        isFolderLongPress = true;
        window.App.openFolderEditModal(true, id);
        if (window.navigator.vibrate) window.navigator.vibrate(50);
    }, 600);
}

function handleFolderPointerUp() {
    clearTimeout(folderLongPressTimer);
}

function handleItemPointerDown(id) {
    if (isItemsReorderMode) return;
    isItemLongPress = false;
    itemLongPressTimer = setTimeout(() => {
        isItemLongPress = true;
        window.App.confirmDeleteWlItem(id);
        if (window.navigator.vibrate) window.navigator.vibrate(50);
    }, 600);
}

function handleItemPointerUp() {
    clearTimeout(itemLongPressTimer);
}

async function sendWishlistAction(action, payload = {}) {
    const r = await fetch('/api/webapp/wishlist/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, ...payload, init_data: tg?.initData || '' })
    });
    if (!r.ok) throw new Error('Network response error');
    return r.json();
}

async function loadWishlist() {
    const grid = document.getElementById('wl-folders-grid');
    const reorderBtn = document.getElementById('wl-reorder-btn');
    if (!wishlistFolders.length) grid.innerHTML = '<div class="loader-inline"><div class="spinner" style="width:32px;height:32px;border-width:3px;"></div></div>';

    try {
        const data = await sendWishlistAction('get');
        wishlistFolders = data.folders || [];

        if (reorderBtn) {
            reorderBtn.style.display = wishlistFolders.length > 1 ? 'flex' : 'none';
            if (isReorderMode && wishlistFolders.length <= 1) {
                window.App.toggleReorderMode();
            }
        }

        const folderExists = wishlistFolders.some(f => f.id === activeWlFolderId);
        if (!folderExists) {
            activeWlFolderId = null;
        }

        if (wishlistFolders.length > 0 && !activeWlFolderId) {
            activeWlFolderId = wishlistFolders[0].id;
        }

        renderWishlistFolders();
        renderActiveWlFolder();
    } catch (e) {
        grid.innerHTML = '<div class="empty">Ошибка загрузки</div>';
    }
}

function renderWishlistFolders() {
    const grid = document.getElementById('wl-folders-grid');
    const wrapper = document.getElementById('wl-folders-wrapper');

    if (wrapper) {
        wrapper.style.display = wishlistFolders.length > 1 ? 'block' : 'none';
    }

    if (!wishlistFolders.length) {
        grid.innerHTML = '<div class="empty" style="grid-column:1/-1">Нет папок</div>';
        if (wlFoldersSortable) { wlFoldersSortable.destroy(); wlFoldersSortable = null; }
        return;
    }

    grid.innerHTML = wishlistFolders.map(f => `
        <div class="wl-folder-card ${f.id === activeWlFolderId && !isReorderMode ? 'active' : ''}" 
             data-id="${f.id}" 
             onpointerdown="handleFolderPointerDown(${f.id})"
             onpointerup="handleFolderPointerUp()"
             onpointerleave="handleFolderPointerUp()"
             onclick="if(!isFolderLongPress && !isReorderMode) window.App.selectWlFolder(${f.id})">
            <div class="wl-delete-badge" onclick="event.stopPropagation(); window.App.deleteWlFolder(${f.id}, this.parentElement)">
                ${Icons.minus}
            </div>
            <div class="wl-folder-inner ${isReorderMode ? 'wiggle' : ''}">
                <div class="wl-folder-icon" style="background: ${f.color}20; color: ${f.color};">
                    ${Icons[f.icon] || Icons.folder}
                </div>
                <div class="wl-folder-info">
                    <div class="wl-folder-name">${f.name}</div>
                    <div class="wl-folder-count">${f.items.length} ${plural(f.items.length, ['шоу', 'шоу', 'шоу'])}</div>
                </div>
            </div>
        </div>
    `).join('');

    if (typeof Sortable !== 'undefined' && !wlFoldersSortable) {
        wlFoldersSortable = new Sortable(grid, {
            animation: 350,
            easing: "cubic-bezier(0.25, 1, 0.5, 1)",
            disabled: true,
            forceFallback: true,
            fallbackOnBody: true,
            fallbackClass: 'sortable-fallback',
            ghostClass: 'sortable-ghost',
            onStart: function (evt) {
                document.body.classList.add('sorting-active');
                if (window.navigator.vibrate) window.navigator.vibrate(10);

                requestAnimationFrame(() => {
                    const fallback = document.querySelector('.sortable-fallback');
                    if (fallback) {
                        fallback.style.width = evt.item.offsetWidth + 'px';
                        fallback.style.height = evt.item.offsetHeight + 'px';
                        const animatedChildren = fallback.querySelectorAll('.wiggle, .wl-folder-inner');
                        animatedChildren.forEach(el => { el.style.animation = 'none'; });
                        const badge = fallback.querySelector('.wl-delete-badge');
                        if (badge) badge.style.display = 'none';
                    }
                });
            },
            onEnd: function (evt) {
                document.body.classList.remove('sorting-active');
                const order = Array.from(grid.children).map(el => parseInt(el.dataset.id));
                sendWishlistAction('reorder_folders', { order });
            }
        });
    }
}

function renderActiveWlFolder() {
    const content = document.getElementById('wl-active-folder-content');
    const titleEl = document.getElementById('wl-active-folder-title');
    const container = document.getElementById('wl-items-container');
    const mainHeader = document.getElementById('wl-main-header');

    if (!activeWlFolderId) {
        if (mainHeader) mainHeader.textContent = 'Избранное';
        if (content) content.style.display = 'none';
        return;
    }

    if (content) content.style.display = 'block';
    const folder = wishlistFolders.find(f => f.id === activeWlFolderId);

    if (mainHeader) {
        if (wishlistFolders.length === 1) {
            mainHeader.innerHTML = `<span style="color:${folder.color}; margin-right: 10px; display: inline-flex; vertical-align: middle;">${Icons[folder.icon] || Icons.folder}</span>${folder.name}`;
        } else {
            mainHeader.textContent = 'Мои списки';
        }
    }

    titleEl.innerHTML = `<span style="color:${folder.color}">${Icons[folder.icon] || Icons.folder}</span> ${folder.name}`;
    titleEl.style.display = wishlistFolders.length > 1 ? 'flex' : 'none';

    document.getElementById('wl-vt-grid').classList.toggle('active', wlViewMode === 'grid');
    document.getElementById('wl-vt-list').classList.toggle('active', wlViewMode === 'list');

    const triggerBtn = document.getElementById('wl-sort-trigger');
    let triggerText = 'Сортировка';
    let triggerIcon = Icons.reorder;
    let arrowClass = '';

    if (wlSortMode.startsWith('added')) {
        triggerText = 'По дате';
        triggerIcon = Icons.sort_arrow;
        arrowClass = wlSortMode.endsWith('asc') ? 'rotate-180' : '';
    } else if (wlSortMode.startsWith('year')) {
        triggerText = 'По году';
        triggerIcon = Icons.sort_arrow;
        arrowClass = wlSortMode.endsWith('asc') ? 'rotate-180' : '';
    } else {
        triggerText = 'Порядок';
        triggerIcon = Icons.reorder;
    }

    triggerBtn.innerHTML = `
        <span class="sort-icon-main ${arrowClass}">${triggerIcon}</span>
        <span class="sort-text-label">${triggerText}</span>
        <span class="sort-chevron">${Icons.chevron_down}</span>
    `;

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
    reorderBtn.style.display = (folder.items.length > 1 && wlSortMode === 'default') ? 'flex' : 'none';
    if (isItemsReorderMode && (folder.items.length <= 1 || wlSortMode !== 'default')) {
        window.App.toggleItemsReorderMode();
    }

    reorderBtn.style.background = isItemsReorderMode ? 'var(--accent)' : 'var(--bg-input)';
    reorderBtn.style.color = isItemsReorderMode ? '#fff' : 'var(--text-primary)';
    container.classList.toggle('reorder-items-mode', isItemsReorderMode);

    if (!folder.items.length) {
        container.innerHTML = `<div class="empty"><div class="icon">${Icons.film}</div>Папка пуста</div>`;
        if (wlItemsSortable) { wlItemsSortable.destroy(); wlItemsSortable = null; }
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

    let itemsHtml = renderItems.map((item, idx) => getWlItemHtml(item, wlViewMode, idx)).join('');

    if (wlViewMode === 'list') {
        container.innerHTML = `<div class="card" style="margin:0; padding:0; overflow:hidden; border:none; background:transparent;">${itemsHtml}</div>`;
    } else {
        container.innerHTML = `<div class="hist-grid">${itemsHtml}</div>`;
    }

    if (typeof Sortable !== 'undefined') {
        if (wlItemsSortable) wlItemsSortable.destroy();
        const targetContainer = container.firstChild;
        wlItemsSortable = new Sortable(targetContainer, {
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
                    sendWishlistAction('reorder_items', { folder_id: activeWlFolderId, order });
                }
            }
        });
    }
}

function getWlItemHtml(item, viewModeStr, idx) {
    const sid = item.show_id;
    const addedDate = item.added_at || '';
    const delay = idx * 0.05;
    const animClass = isItemsReorderMode ? '' : 'anim-item';
    const style = isItemsReorderMode ? '' : `style="animation-delay: ${delay}s"`;

    const deleteBtn = `<div class="wl-delete-badge" onclick="event.stopPropagation(); window.App.removeWlItem(${item.id}, this.parentElement)">${Icons.minus}</div>`;

    if (viewModeStr === 'list') {
        const poster = item.poster_url ? `<img src="${item.poster_url}" class="hist-poster" loading="lazy" draggable="false">` : `<div class="hist-poster"></div>`;
        return `
        <div class="hist-item clickable ${animClass}" ${style} data-id="${item.id}" onclick="if(!isItemsReorderMode) window.App.openShowLayer(${sid})">
            ${deleteBtn}
            ${poster}
            <div class="hist-info">
                <div class="hist-title">${item.title}</div>
                ${item.original_title && item.original_title !== item.title ? `<div class="hist-orig">${item.original_title}</div>` : ''}
                <div class="hist-meta">
                    ${item.year ? `<span>${item.year}</span>` : ''}
                    ${item.type ? `<span>· ${item.type}</span>` : ''}
                    <span style="opacity: 0.6;">· ${addedDate}</span>
                </div>
            </div>
        </div>`;
    } else {
        const mediumPoster = item.poster_url ? item.poster_url.replace('/small/', '/medium/') : '';
        const posterHtml = mediumPoster ? `<img src="${mediumPoster}" class="grid-poster" loading="lazy" draggable="false">` : '<div class="grid-poster"></div>';
        const yearHtml = item.year ? `<div class="grid-year">${item.year}</div>` : '';

        return `
        <div class="grid-item-wrap ${animClass}" ${style} data-id="${item.id}" onclick="if(!isItemsReorderMode) window.App.openShowLayer(${sid})">
            ${deleteBtn}
            <div class="grid-item">
                ${posterHtml}
                ${yearHtml}
                <div class="grid-overlay">
                    <div class="grid-date" style="color: var(--text-muted);">${addedDate}</div>
                </div>
            </div>
            <div class="grid-below-title">${item.title}</div>
            ${item.original_title && item.original_title !== item.title ? `<div class="grid-below-orig">${item.original_title}</div>` : ''}
        </div>`;
    }
}

function renderColorPicker(activeColor) {
    const cont = document.getElementById('wl-color-picker');
    cont.innerHTML = FOLDER_COLORS.map(c => `
        <div class="wl-color-btn ${c === activeColor ? 'active' : ''}" style="background-color: ${c}" onclick="window.App.selectFolderColor('${c}')"></div>
    `).join('');
}

function renderIconPicker(activeIcon) {
    const cont = document.getElementById('wl-icon-picker');
    cont.innerHTML = FOLDER_ICONS.map(i => `
        <div class="wl-icon-btn ${i === activeIcon ? 'active' : ''}" onclick="window.App.selectFolderIcon('${i}')">${Icons[i]}</div>
    `).join('');
}

window.App = {
    ...window.App,
    loadWishlist: loadWishlist,
    selectWlFolder: function (id) {
        if (activeWlFolderId === id) return;
        activeWlFolderId = id;
        renderWishlistFolders();
        renderActiveWlFolder();
    },
    setWlViewMode: function (mode) {
        wlViewMode = mode;
        localStorage.setItem('wl_view_mode', mode);
        renderActiveWlFolder();
    },
    setWlSortMode: function (mode) {
        wlSortMode = mode;
        localStorage.setItem('wl_sort_mode', mode);
        renderActiveWlFolder();
    },
    toggleReorderMode: function () {
        isReorderMode = !isReorderMode;
        const btn = document.getElementById('wl-reorder-btn');
        const viewWrap = document.getElementById('view-wishlist');

        btn.innerHTML = isReorderMode ? Icons.reorder : Icons.reorder;
        btn.style.background = isReorderMode ? 'var(--accent)' : 'var(--bg-input)';
        btn.style.color = isReorderMode ? '#fff' : 'var(--text-primary)';

        viewWrap.classList.toggle('reorder-active-state', isReorderMode);
        document.getElementById('wl-folders-grid').classList.toggle('reorder-mode', isReorderMode);

        if (wlFoldersSortable) {
            wlFoldersSortable.option('disabled', !isReorderMode);
        }

        renderWishlistFolders();
    },
    toggleItemsReorderMode: function () {
        isItemsReorderMode = !isItemsReorderMode;
        const btn = document.getElementById('wl-items-reorder-btn');
        const container = document.getElementById('wl-items-container');

        btn.style.background = isItemsReorderMode ? 'var(--accent)' : 'var(--bg-input)';
        btn.style.color = isItemsReorderMode ? '#fff' : 'var(--text-primary)';

        container.classList.toggle('reorder-items-mode', isItemsReorderMode);

        if (wlItemsSortable) {
            wlItemsSortable.option('disabled', !isItemsReorderMode);
        }
    },
    confirmDeleteWlItem: function (id) {
        const el = document.querySelector(`.hist-item[data-id="${id}"], .grid-item-wrap[data-id="${id}"]`);
        itemToDeleteId = id;
        itemToDeleteElement = el;

        const item = wishlistFolders.flatMap(f => f.items).find(i => i.id === id);
        if (item) {
            const typeMap = {
                'Series': 'сериал',
                'Movie': 'фильм',
                'Concert': 'концерт',
                'Documentary Movie': 'док. фильм',
                'Documentary Series': 'док. сериал',
                'TV Show': 'ТВ-шоу',
                '3D Movie': '3D фильм'
            };
            const ruType = typeMap[item.type] || 'шоу';
            const textEl = document.getElementById('wl-delete-confirm-text');
            if (textEl) {
                textEl.innerHTML = `Вы уверены, что хотите удалить ${ruType} <b style="color:var(--text-primary)">«${item.title}»</b> из списка?`;
            }
        }

        document.getElementById('wl-del-keep-stats').checked = true;
        document.getElementById('wl-item-delete-modal').classList.add('show');
    },
    removeWlItem: function (id, element) {
        itemToDeleteId = id;
        itemToDeleteElement = element;
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
                await sendWishlistAction('remove_item', { item_id: id, keep_stats: false });
                
                const counterEl = document.getElementById('s-wl-watched');
                if (counterEl) {
                    let current = parseInt(counterEl.textContent) || 0;
                    if (current > 0) counterEl.textContent = current - 1;
                }
                
                if (D && D.wishlist_watched_items) {
                    D.wishlist_watched_items = D.wishlist_watched_items.filter(i => i.wl_item_id !== id);
                }
            } catch (e) {}
        }
    },
    closeItemDeleteModal: function () {
        document.getElementById('wl-item-delete-modal').classList.remove('show');
        itemToDeleteId = null;
        itemToDeleteElement = null;
    },
    confirmItemDelete: function () {
        if (!itemToDeleteId) return;
        const keepStats = document.getElementById('wl-del-keep-stats').checked;
        const id = itemToDeleteId;
        const element = itemToDeleteElement;

        window.App.closeItemDeleteModal();

        if (element) {
            element.classList.add('anim-shrink');
            element.addEventListener('animationend', () => {
                const folder = wishlistFolders.find(f => f.id === activeWlFolderId);
                if (folder) {
                    folder.items = folder.items.filter(i => i.id !== id);
                }
                renderActiveWlFolder();
                renderWishlistFolders();
            }, { once: true });
        }

        sendWishlistAction('remove_item', { item_id: id, keep_stats: keepStats });
        showToast('Удалено');
    },
    deleteWlFolder: async function (id, element) {
        if (!confirm('Удалить папку и всё её содержимое?')) return;

        if (element) {
            element.classList.add('anim-shrink');
            element.addEventListener('animationend', async () => {
                wishlistFolders = wishlistFolders.filter(f => f.id !== id);

                if (wishlistFolders.length <= 1) {
                    const reorderBtn = document.getElementById('wl-reorder-btn');
                    if (reorderBtn) reorderBtn.style.display = 'none';
                    if (isReorderMode) window.App.toggleReorderMode();
                }

                if (wishlistFolders.length === 0) {
                    activeWlFolderId = null;
                    document.getElementById('wl-active-folder-content').style.display = 'none';
                    document.getElementById('wl-folders-grid').innerHTML = '<div class="loader-inline"><div class="spinner" style="width:32px;height:32px;border-width:3px;"></div></div>';
                    await sendWishlistAction('delete_folder', { folder_id: id });
                    await loadWishlist();
                    return;
                }

                if (activeWlFolderId === id) {
                    activeWlFolderId = wishlistFolders[0].id;
                }

                renderWishlistFolders();
                renderActiveWlFolder();
            }, { once: true });
        }

        sendWishlistAction('delete_folder', { folder_id: id });
        showToast('Папка удалена');
    },
    openFolderEditModal: function (isEdit = false, folderId = null) {
        if (!isEdit && wishlistFolders.length >= 12) {
            document.getElementById('wl-limit-modal').classList.add('show');
            if (window.navigator.vibrate) window.navigator.vibrate([40, 100, 40]);
            return;
        }

        editFolderMode = isEdit ? 'edit' : 'create';
        const titleEl = document.getElementById('wl-edit-title');
        const nameInp = document.getElementById('wl-folder-name');
        const delBtn = document.getElementById('wl-delete-folder-btn');

        let curName = '', curColor = FOLDER_COLORS[0], curIcon = FOLDER_ICONS[0];

        if (isEdit) {
            if (folderId) activeWlFolderId = folderId;
            const folder = wishlistFolders.find(f => f.id === activeWlFolderId);
            if (!folder) return;

            curName = folder.name;
            curColor = folder.color;
            curIcon = folder.icon;
            titleEl.textContent = 'Настройки папки';
            delBtn.style.display = 'block';
        } else {
            titleEl.textContent = 'Новая папка';
            delBtn.style.display = 'none';
            nameInp.value = '';
        }

        nameInp.value = curName;
        document.getElementById('wl-color-picker').dataset.color = curColor;
        document.getElementById('wl-icon-picker').dataset.icon = curIcon;

        renderColorPicker(curColor);
        renderIconPicker(curIcon);

        document.getElementById('wl-edit-modal').classList.add('show');
    },
    closeFolderEditModal: function () {
        document.getElementById('wl-edit-modal').classList.remove('show');
    },
    closeLimitModal: function () {
        document.getElementById('wl-limit-modal').classList.remove('show');
    },
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

        if (editFolderMode === 'create') {
            const tempId = -Date.now();
            wishlistFolders.push({ id: tempId, name: name || '', color, icon, items: [] });
            activeWlFolderId = tempId;

            renderWishlistFolders();
            renderActiveWlFolder();

            const res = await sendWishlistAction('create_folder', { name, icon, color });
            if (res.status === 'ok' && res.id) {
                activeWlFolderId = res.id;
            }
            await loadWishlist();
        } else {
            const folder = wishlistFolders.find(f => f.id === activeWlFolderId);
            if (folder) {
                folder.name = name || '';
                folder.color = color;
                folder.icon = icon;
            }
            renderWishlistFolders();
            renderActiveWlFolder();

            sendWishlistAction('edit_folder', { folder_id: activeWlFolderId, name, icon, color });
        }
    },
    editActiveFolder: function () {
        if (activeWlFolderId) window.App.openFolderEditModal(true);
    },
    deleteActiveFolder: async function () {
        if (!confirm('Удалить папку и всё её содержимое?')) return;
        window.App.closeFolderEditModal();

        const idToDelete = activeWlFolderId;
        wishlistFolders = wishlistFolders.filter(f => f.id !== idToDelete);

        if (wishlistFolders.length <= 1) {
            const reorderBtn = document.getElementById('wl-reorder-btn');
            if (reorderBtn) reorderBtn.style.display = 'none';
            if (isReorderMode) window.App.toggleReorderMode();
        }

        if (wishlistFolders.length === 0) {
            activeWlFolderId = null;
            document.getElementById('wl-active-folder-content').style.display = 'none';
            document.getElementById('wl-folders-grid').innerHTML = '<div class="loader-inline"><div class="spinner" style="width:32px;height:32px;border-width:3px;"></div></div>';
            await sendWishlistAction('delete_folder', { folder_id: idToDelete });
            await loadWishlist();
            return;
        }

        activeWlFolderId = wishlistFolders[0].id;

        renderWishlistFolders();
        renderActiveWlFolder();

        sendWishlistAction('delete_folder', { folder_id: idToDelete });
    },
    showFolderModal: async function (showId, title) {
        activeShowForWishlist = showId;

        if (wishlistFolders.length === 1) {
            try {
                await sendWishlistAction('add_item', { folder_id: wishlistFolders[0].id, show_id: showId });
                showToast('Успешно добавлено');
            } catch (e) {
                showToast('Ошибка при добавлении');
            }
            return;
        }

        document.getElementById('wl-modal-title').textContent = title;
        const grid = document.getElementById('wl-modal-folders');
        grid.innerHTML = '<div class="spinner" style="margin: 20px auto;"></div>';
        document.getElementById('wl-modal').classList.add('show');

        try {
            const data = await sendWishlistAction('get');
            if (data.folders) {
                wishlistFolders = data.folders;

                if (wishlistFolders.length === 1) {
                    window.App.closeFolderModal();
                    await sendWishlistAction('add_item', { folder_id: wishlistFolders[0].id, show_id: showId });
                    showToast('Успешно добавлено');
                    return;
                }

                grid.innerHTML = data.folders.map(f => `
                    <div class="wl-folder-card" style="margin-bottom:8px;" onclick="window.App.addToFolder(${f.id})">
                        <div class="wl-folder-icon" style="background: ${f.color}20; color: ${f.color};">
                            ${Icons[f.icon] || Icons.folder}
                        </div>
                        <div class="wl-folder-info">
                            <div class="wl-folder-name">${f.name}</div>
                            <div class="wl-folder-count">${f.items.length} элементов</div>
                        </div>
                    </div>
                `).join('');
                if (!data.folders.length) grid.innerHTML = '<div class="empty">Нет папок. Создайте их в Избранном.</div>';
            }
        } catch (e) {
            grid.innerHTML = '<div class="empty">Ошибка</div>';
        }
    },
    closeFolderModal: function () {
        const modal = document.getElementById('wl-modal');
        if (modal) modal.classList.remove('show');
    },
    addToFolder: async function (folderId) {
        if (!activeShowForWishlist) return;
        try {
            await sendWishlistAction('add_item', { folder_id: folderId, show_id: activeShowForWishlist });
            showToast('Успешно добавлено');
            window.App.closeFolderModal();
        } catch (e) {
            showToast('Ошибка при добавлении');
        }
    },
    toggleSortDropdown: function (e) {
        if (e) e.stopPropagation();
        const menu = document.getElementById('wl-sort-menu');
        const isVisible = menu.classList.contains('show');

        document.querySelectorAll('.sort-dropdown-menu').forEach(m => m.classList.remove('show'));

        if (!isVisible) {
            document.getElementById('si-reorder').innerHTML = Icons.reorder;
            document.getElementById('si-added').innerHTML = Icons.sort_arrow;
            document.getElementById('si-year').innerHTML = Icons.sort_arrow;

            menu.classList.add('show');
            const closeHandler = () => {
                menu.classList.remove('show');
                document.removeEventListener('click', closeHandler);
            };
            setTimeout(() => document.addEventListener('click', closeHandler), 10);
        }
    },
    setSortOption: function (type) {
        let newMode = 'default';

        if (type === 'added') {
            newMode = (wlSortMode === 'added_desc') ? 'added_asc' : 'added_desc';
        } else if (type === 'year') {
            newMode = (wlSortMode === 'year_desc') ? 'year_asc' : 'year_desc';
        } else {
            newMode = 'default';
        }

        window.App.setWlSortMode(newMode);
    }
};