window.App = window.App || {};

Object.assign(window.App, {
    searchTimer: null,

    doSearch: async function(q) {
        clearTimeout(window.App.searchTimer);
        const resEl = document.getElementById('search-results');
        if (!resEl) return;
        
        if (q.length < 2) {
            window.App.setState('data.search.results', null);
            resEl.innerHTML = `
                <div class="empty">
                    <div class="icon" style="font-size: 48px; opacity: 0.3; margin-bottom: 16px;">
                        ${window.App.Icons.search}
                    </div>
                    Введите название для поиска
                </div>`;
            return;
        }

        window.App.searchTimer = setTimeout(async () => {
            // Показываем лоадер только если запрос всё еще актуален
            resEl.innerHTML = '<div class="loader-inline"><div class="spinner" style="width:32px;height:32px;border-width:3px;"></div></div>';
            
            try {
                const r = await fetch('/api/webapp/search/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: q, init_data: window.Telegram?.WebApp?.initData || '' })
                });
                const data = await r.json();
                
                // Проверяем, не изменился ли запрос пока мы ждали ответа
                const currentQ = window.App.getState('forms.search.query');
                if (currentQ === q) {
                    window.App.setState('data.search.results', data);
                }
            } catch (e) {
                if (window.App.getState('forms.search.query') === q) {
                    resEl.innerHTML = '<div class="empty">Ошибка при поиске</div>';
                }
            }
        }, 400);
    },

    renderSearchResults: function(data) {
        const resEl = document.getElementById('search-results');
        if (!resEl) return;

        if (!data || (!data.shows?.length && !data.persons?.length)) {
            resEl.innerHTML = `<div class="empty"><div class="icon">${window.App.Icons.dash}</div>Ничего не найдено</div>`;
            return;
        }

        let html = '';
        if (data.persons?.length) {
            html += `<div class="label"><div class="icon" style="color:#d29922">${window.App.Icons.users}</div>Люди</div>`;
            html += '<div class="h-scroll-container" style="padding-bottom:16px;">';
            data.persons.forEach(p => {
                const fb = p.fallback_photo_url ? `'${p.fallback_photo_url}'` : 'null';
                const safeName = p.name.replace(/'/g, "\\'");
                const img = p.photo_url 
                    ? `<img src="${p.photo_url}" class="person-avatar" style="object-fit:cover;" 
                        onerror="window.App.handleImgErr(this, ${fb}, '${safeName}')" 
                        onload="window.App.handleKpPlaceholder(this, '${safeName}')">` 
                    : `<div class="person-avatar">${window.App.Icons.person_placeholder}</div>`;
                html += `
                    <div class="person-pill" onclick="window.App.openCollectionLayer('person', ${p.id}, '${safeName}')">
                        ${img}
                        <div class="person-name">${p.name}</div>
                    </div>`;
            });
            html += '</div>';
        }

        if (data.shows?.length) {
            html += `<div class="label"><div class="icon" style="color:var(--info)">${window.App.Icons.film}</div>Контент</div>`;
            html += '<div class="hist-grid" style="padding:0 16px;">';
            data.shows.forEach(s => {
                const poster = s.poster_url ? `<img src="${s.poster_url}" class="grid-poster" loading="lazy">` : '<div class="grid-poster"></div>';
                const safeTitle = s.title.replace(/'/g, "\\'");
                let badgesHtml = s.user_rating ? `<span class="rating-badge" style="background:rgba(0,0,0,0.6);border:none;">${window.App.Icons.star}${s.user_rating}</span>` : '';

                html += `
                    <div class="grid-item-wrap anim-item" onclick="window.App.openShowLayer(${s.id})">
                        <div class="grid-item">
                            ${poster}<div class="grid-badges">${badgesHtml}</div>
                            ${s.year ? `<div class="grid-year">${s.year}</div>` : ''}
                            <button class="wishlist-add-btn" onclick="event.stopPropagation(); window.App.showFolderModal(${s.id}, '${safeTitle}')">${window.App.Icons.bookmark_plus}</button>
                        </div>
                        <div class="grid-below-title">${s.title}</div>
                    </div>`;
            });
            html += '</div>';
        }

        resEl.innerHTML = html;
        requestAnimationFrame(() => window.App.fitAll('.grid-below-title', resEl));
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

    handleKpPlaceholder: function(img, name) {
        if (img.naturalWidth === 208 && img.naturalHeight === 304) {
            this.handleImgErr(img, null, name);
        }
    }
});