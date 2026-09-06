// Shared helpers
function esc(s) {
    if (s == null) return '';
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
}

function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
}

// ── Live research progress page ──────────────────────────────
function initLivePage() {
    const logEl = document.getElementById('live-log');
    const stageBanner = document.getElementById('stage-banner');
    const planList = document.getElementById('plan-list');
    const urlList = document.getElementById('url-list');
    const urlCount = document.getElementById('url-count');
    const sourceList = document.getElementById('source-list');
    const sourceCount = document.getElementById('source-count');
    const findingList = document.getElementById('finding-list');
    const findingCount = document.getElementById('finding-count');
    const statusPill = document.getElementById('status-pill');
    const viewResults = document.getElementById('view-results');
    const gallery = document.getElementById('image-gallery');
    const galleryHint = document.getElementById('image-mode-hint');
    const imageCount = document.getElementById('image-count');

    // In image mode we hide the text widgets (no report to show)
    const isImageMode = (typeof JOB_MODE !== 'undefined' && JOB_MODE === 'images');
    if (isImageMode && gallery) {
        gallery.classList.remove('hidden');
        galleryHint.classList.remove('hidden');
        // Hide text columns that don't apply to image mode
        document.querySelectorAll('.progress-columns, .log-wrap').forEach(el => el.style.display = 'none');
    }

    // If this is a finished image job, pre-load its images
    if (isImageMode) {
        fetch('/api/jobs/' + JOB_ID + '/images').then(r => r.json()).then(d => {
            if (d.images && d.images.length) {
                d.images.forEach(img => {
                    const data = {
                        page_url: img.page_url,
                        image_url: img.image_url,
                        thumbnail_url: img.thumbnail_url,
                        title: img.title
                    };
                    if (gallery) addImageElement(gallery, data);
                });
                if (imageCount) {
                    imageCount.textContent = d.images.length + ' images found';
                    imageCount.classList.remove('hidden');
                }
                if (galleryHint) galleryHint.classList.add('hidden');
            }
        }).catch(() => {});
    }

    const urlSet = new Set();
    const refs = { log: logEl, findings: findingList };
    let imgCount = 0;

    function appendLog(msg) {
        const line = '[' + new Date().toLocaleTimeString() + '] ' + msg;
        logEl.textContent += line + '\n';
        logEl.scrollTop = logEl.scrollHeight;
    }

    function addImageElement(container, data) {
        const cell = el('a', 'image-cell');
        cell.href = data.page_url || data.image_url;
        cell.target = '_blank';
        const img = document.createElement('img');
        img.src = data.thumbnail_url || data.image_url;
        img.alt = data.title || '';
        img.loading = 'lazy';
        cell.appendChild(img);
        if (data.title) {
            const cap = el('div', 'image-cap', data.title);
            cell.appendChild(cap);
        }
        container.appendChild(cell);
    }

    function addImage(data) {
        if (gallery) addImageElement(gallery, data);
    }

    function handle(evtName, data) {
        switch (evtName) {
            case 'stage':
                stageBanner.textContent = data.title + (data.detail ? ' — ' + data.detail : '');
                appendLog('▸ ' + data.title);
                break;

            case 'status':
                appendLog(data.message || 'status');
                break;

            case 'plan':
                if (data.sub_queries && data.sub_queries.length) {
                    planList.innerHTML = '';
                    data.sub_queries.forEach(sq => {
                        const li = el('li', '', sq.aspect + ' → ' + sq.query);
                        planList.appendChild(li);
                    });
                }
                break;

            case 'image':
                if (gallery) {
                    addImage(data);
                }
                break;

            case 'images_done':
                imgCount = data.count || 0;
                if (imageCount) {
                    imageCount.textContent = imgCount + ' images found';
                    imageCount.classList.remove('hidden');
                }
                if (galleryHint) galleryHint.classList.add('hidden');
                appendLog('Image search complete: ' + imgCount + ' images');
                break;

            case 'found_urls':
                urlCount.textContent = data.count || (data.urls ? data.urls.length : 0);
                if (data.urls) {
                    urlList.innerHTML = '';
                    data.urls.forEach((u, i) => {
                        if (urlSet.has(u.url)) return;
                        urlSet.add(u.url);
                        const item = el('div', 'url-item');
                        item.appendChild(el('span', 'idx', String(i + 1)));
                        const a = el('a', '', u.title || u.url);
                        a.href = u.url; a.target = '_blank';
                        item.appendChild(a);
                        const badge = el('span', 'tag-badge ' + u.source_type, u.source_type === 'darkweb' ? 'onion' : u.source_type);
                        item.appendChild(badge);
                        urlList.appendChild(item);
                    });
                }
                appendLog('Found ' + urlCount.textContent + ' URLs');
                break;

            case 'source':
                if (data.error) {
                    appendLog('⚠ Failed: ' + data.url + ' (' + data.error + ')');
                    break;
                }
                sourceCount.textContent = parseInt(sourceCount.textContent || '0') + 1;
                const si = el('div', 'source-item');
                const sta = el('a', '', data.title || data.url);
                sta.href = data.url; sta.target = '_blank';
                si.appendChild(sta);
                si.appendChild(el('div', 'muted', data.word_count + ' words · ' + data.url));
                sourceList.appendChild(si);
                appendLog('Extracted: ' + (data.title || data.url));
                break;

            case 'finding':
                findingCount.textContent = parseInt(findingCount.textContent || '0') + 1;
                const fi = el('div', 'finding-item');
                const topic = el('span', 'topic', data.topic + ' ');
                const conf = el('span', 'conf', '[' + data.confidence + ']');
                fi.appendChild(topic); fi.appendChild(conf);
                fi.appendChild(el('div', '', data.content));
                findingList.appendChild(fi);
                break;

            case 'report':
                appendLog('Report generated: ' + data.summary);
                break;

            case 'error':
                statusPill.textContent = 'Error';
                statusPill.className = 'status-pill error';
                appendLog('✖ ERROR: ' + (data.error || 'unknown'));
                break;

            case 'done':
                statusPill.textContent = 'Done';
                statusPill.className = 'status-pill done';
                appendLog('✔ Research complete.');
                if (viewResults) viewResults.classList.remove('hidden');
                break;

            default:
                appendLog(evtName + ': ' + JSON.stringify(data));
        }
    }

    const es = new EventSource('/api/jobs/' + JOB_ID + '/stream');
    es.onmessage = function (e) { };
    es.addEventListener('stage', ev => handle('stage', JSON.parse(ev.data)));
    es.addEventListener('status', ev => handle('status', JSON.parse(ev.data)));
    es.addEventListener('plan', ev => handle('plan', JSON.parse(ev.data)));
    es.addEventListener('found_urls', ev => handle('found_urls', JSON.parse(ev.data)));
    es.addEventListener('source', ev => handle('source', JSON.parse(ev.data)));
    es.addEventListener('finding', ev => handle('finding', JSON.parse(ev.data)));
    es.addEventListener('report', ev => handle('report', JSON.parse(ev.data)));
    es.addEventListener('image', ev => handle('image', JSON.parse(ev.data)));
    es.addEventListener('images_done', ev => handle('images_done', JSON.parse(ev.data)));
    es.addEventListener('error', ev => handle('error', JSON.parse(ev.data)));
    es.addEventListener('done', ev => handle('done', JSON.parse(ev.data)));

    es.onerror = function () {
        // Reconnect handled automatically by EventSource
        appendLog('…connection lost, reconnecting');
    };
}

// ── Results page with filtering ──────────────────────────────
function initResultsPage() {
    const scriptEl = document.getElementById('result-data');
    if (!scriptEl) return;
    let data;
    try { data = JSON.parse(scriptEl.textContent); } catch (e) { return; }

    const urlsContent = document.getElementById('urls-content');
    const sourcesContent = document.getElementById('sources-content');
    const findingsContent = document.getElementById('findings-content');

    // Load found links from the saved file? We have the data from pipeline.
    // Render sources + findings; URLs come from the fused list embedded in data.
    // We'll render sources which contain URLs, plus a links table from sources.

    function activeFilters() {
        const kw = document.getElementById('filter-keyword').value.trim().toLowerCase();
        const type = document.getElementById('filter-type').value;
        const conf = parseFloat(document.getElementById('filter-confidence').value || '0');
        return { kw, type, conf };
    }

    function matchesType(st) {
        const f = activeFilters();
        return f.type === 'all' || st === f.type;
    }

    function matchesKw(...texts) {
        const f = activeFilters();
        if (!f.kw) return true;
        return texts.some(t => t && String(t).toLowerCase().includes(f.kw));
    }

    function renderSources() {
        sourcesContent.innerHTML = '';
        const f = activeFilters();
        const list = (data.sources || []).filter(s => matchesType(s.source_type) && matchesKw(s.title, s.url));
        if (!list.length) { sourcesContent.innerHTML = '<p class="muted">No sources match.</p>'; return; }
        list.forEach(s => {
            const box = el('div', 'report-section');
            const h = el('h3', '');
            const a = el('a', '', s.title || s.url);
            a.href = s.url; a.target = '_blank';
            h.appendChild(a);
            box.appendChild(h);
            box.appendChild(el('div', 'muted', s.url + ' · type: ' + s.source_type + ' · quality: ' + (s.quality_score).toFixed(2)));
            const body = el('div', 'report-content');
            body.textContent = s.text || '(no content)';
            box.appendChild(body);
            sourcesContent.appendChild(box);
        });
    }

    function renderFindings() {
        findingsContent.innerHTML = '';
        const f = activeFilters();
        const list = ((data.findings || [])).filter(fi =>
            parseFloat(fi.confidence) >= f.conf &&
            matchesType(fi.source_type) &&
            matchesKw(fi.content, fi.topic, fi.source_title)
        );
        if (!list.length) { findingsContent.innerHTML = '<p class="muted">No findings match.</p>'; return; }
        list.sort((a, b) => b.confidence - a.confidence);
        list.forEach(fi => {
            const item = el('div', 'finding-item');
            const topic = el('span', 'topic', fi.topic || '');
            const conf = el('span', 'conf', ' [' + fi.confidence + ']');
            item.appendChild(topic); item.appendChild(conf);
            item.appendChild(el('div', '', fi.content));
            const src = el('div', 'muted', '— ' + fi.source_title + ' · ' + fi.source_url);
            item.appendChild(src);
            if (fi.contradictions && fi.contradictions.length) {
                item.appendChild(el('div', 'contradiction', '⚠ ' + fi.contradictions.join('; ')));
            }
            findingsContent.appendChild(item);
        });
    }

    function renderUrls() {
        // Build a links table from sources + findings source URLs
        urlsContent.innerHTML = '';
        const f = activeFilters();
        const seen = new Set();
        const rows = [];
        (data.sources || []).forEach(s => {
            if (seen.has(s.url)) return;
            seen.add(s.url);
            if (matchesType(s.source_type) && matchesKw(s.title, s.url)) {
                rows.push({ url: s.url, title: s.title, type: s.source_type });
            }
        });
        if (!rows.length) { urlsContent.innerHTML = '<p class="muted">No URLs match.</p>'; return; }
        const table = document.createElement('table');
        table.className = 'history-table';
        table.innerHTML = '<thead><tr><th>#</th><th>Title</th><th>URL</th><th>Type</th></tr></thead>';
        const tbody = document.createElement('tbody');
        rows.forEach((r, i) => {
            const tr = document.createElement('tr');
            tr.appendChild(el('td', '', String(i + 1)));
            const tdT = document.createElement('td'); tdT.textContent = r.title || ''; tr.appendChild(tdT);
            const tdU = document.createElement('td');
            const a = el('a', '', r.url); a.href = r.url; a.target = '_blank';
            tdU.appendChild(a); tr.appendChild(tdU);
            const tdTy = document.createElement('td'); tdTy.textContent = r.type; tr.appendChild(tdTy);
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        urlsContent.appendChild(table);
    }

    function refresh() {
        renderSources();
        renderFindings();
        renderUrls();
    }

    // Tabs
    document.querySelectorAll('.tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            document.getElementById('pane-' + btn.dataset.tab).classList.add('active');
        });
    });

    // Filters (debounced)
    let timer;
    ['filter-keyword', 'filter-type', 'filter-confidence'].forEach(id => {
        const inp = document.getElementById(id);
        if (inp) inp.addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(refresh, 150);
        });
    });

    refresh();
}

document.addEventListener('DOMContentLoaded', function () {
    if (typeof JOB_ID !== 'undefined') initLivePage();
    else if (document.getElementById('result-data')) initResultsPage();
});
