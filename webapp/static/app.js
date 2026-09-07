// Deep Research Intelligence Platform - Client Application with 60/40 Workspace & Refined UI

let currentSearchResults = [];
let activeSearchAbortController = null;
let currentDownloadTaskId = null;

document.addEventListener('DOMContentLoaded', () => {
    const safeInit = (name, fn) => {
        try {
            fn();
        } catch (err) {
            console.error(`[Init Error] ${name}:`, err);
        }
    };

    safeInit('Theme', initTheme);
    safeInit('Tabs', initTabs);
    safeInit('OptionsDrawers', initOptionsDrawers);
    safeInit('EngineToggles', initEngineToggles);
    safeInit('ModeSelectors', initModeSelectors);
    safeInit('QuickSearch', initQuickSearch);
    safeInit('VisualSearch', initVisualSearch);
    safeInit('Scraper', initScraper);
    safeInit('Diagnostics', initDiagnostics);
    safeInit('Directory', initDirectory);
    safeInit('Modal', initModal);
    safeInit('CinemaPlayer', initCinemaPlayer);
    safeInit('DownloadsDrawer', initDownloadsDrawer);
    safeInit('DeepResearch', initDeepResearch);
    safeInit('DocsNav', initDocsNav);
    safeInit('OllamaModels', loadOllamaModels);
    safeInit('KnowledgeStats', loadKnowledgeStats);
    safeInit('RestoreActiveSearch', restoreActiveSearch);
    safeInit('Icons', renderIcons);
});


function renderIcons() {
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
}

// ----------------------------------------------------------------------
// Theme Switcher (Light / Dark Mode)
// ----------------------------------------------------------------------
function initTheme() {
    const toggleBtn = document.getElementById('theme-toggle');
    if (!toggleBtn) return;

    toggleBtn.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', nextTheme);
        if (nextTheme === 'dark') {
            document.documentElement.classList.add('dark');
            document.documentElement.classList.remove('light');
        } else {
            document.documentElement.classList.add('light');
            document.documentElement.classList.remove('dark');
        }
        localStorage.setItem('north_theme', nextTheme);
        renderIcons();
    });
}

// ----------------------------------------------------------------------
// Option Drawers Toggle (Direct Grid / Hidden Handler)
// ----------------------------------------------------------------------
function initOptionsDrawers() {
    function setupDrawer(toggleId, drawerId, chevronId) {
        const toggle = document.getElementById(toggleId);
        const drawer = document.getElementById(drawerId);
        const chevron = document.getElementById(chevronId);
        if (!toggle || !drawer) return;

        toggle.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            const isHidden = drawer.classList.contains('hidden') || drawer.style.display === 'none';
            if (isHidden) {
                drawer.classList.remove('hidden');
                drawer.style.display = 'grid';
                if (chevron) chevron.style.transform = 'rotate(180deg)';
            } else {
                drawer.classList.add('hidden');
                drawer.style.display = 'none';
                if (chevron) chevron.style.transform = 'rotate(0deg)';
            }
        });
    }

    setupDrawer('btn-toggle-deep-options', 'deep-options-drawer', 'deep-options-chevron');
    setupDrawer('btn-toggle-qs-options', 'qs-options-drawer', 'qs-options-chevron');
}

// ----------------------------------------------------------------------
// Search Engines Toggle Buttons & 3-Way Search Mode Selector
// ----------------------------------------------------------------------
function initEngineToggles() {
    // 1. Individual Engine Toggle Buttons
    document.addEventListener('click', (e) => {
        const toggleBtn = e.target.closest('.engine-toggle');
        if (!toggleBtn) return;

        e.preventDefault();
        e.stopPropagation();

        const isActive = toggleBtn.classList.toggle('active');
        const statusText = toggleBtn.querySelector('.engine-status-text');
        if (statusText) {
            statusText.textContent = isActive ? 'ON' : 'OFF';
        }
    });

    // 2. Batch All ON / All OFF buttons
    document.querySelectorAll('.btn-all-engines-toggle').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const target = btn.dataset.target; // 'deep' or 'qs'
            const action = btn.dataset.action; // 'all_on' or 'all_off'
            const containerId = target === 'deep' ? 'deep-providers-list' : 'qs-engines';
            const container = document.getElementById(containerId);
            if (!container) return;

            const shouldBeActive = action === 'all_on';
            container.querySelectorAll('.engine-toggle').forEach(tBtn => {
                tBtn.classList.toggle('active', shouldBeActive);
                const statusText = tBtn.querySelector('.engine-status-text');
                if (statusText) {
                    statusText.textContent = shouldBeActive ? 'ON' : 'OFF';
                }
            });
        });
    });
}

function initModeSelectors() {
    document.addEventListener('click', (e) => {
        const modeBtn = e.target.closest('.mode-selector-btn');
        if (!modeBtn) return;

        e.preventDefault();
        e.stopPropagation();

        const mode = modeBtn.dataset.mode || 'normal';
        const scope = modeBtn.dataset.scope || 'deep';
        const group = modeBtn.closest('.mode-segmented-group');
        if (group) {
            group.querySelectorAll('.mode-selector-btn').forEach(b => b.classList.remove('active'));
            modeBtn.classList.add('active');
        }

        const modeInput = document.getElementById(`${scope}-darkweb-mode-input`);
        if (modeInput) modeInput.value = mode;

        const legacyTor = document.getElementById(`${scope}-darkweb`);
        if (legacyTor) legacyTor.value = (mode === 'darknet_only' || mode === 'all') ? 'true' : 'false';
    });
}

// ----------------------------------------------------------------------
// Knowledge Base Stats
// ----------------------------------------------------------------------
async function loadKnowledgeStats() {
    const label = document.getElementById('kb-count-label');
    if (!label) return;

    try {
        const res = await fetch('/api/knowledge');
        const data = await res.json();
        if (typeof data.total_indexed === 'number') {
            label.textContent = `${data.total_indexed.toLocaleString()} persistent records`;
        }
    } catch (e) {
        label.textContent = 'Knowledge Base Online';
    }
}

// ----------------------------------------------------------------------
// Docs Navigation Highlighting
// ----------------------------------------------------------------------
function initDocsNav() {
    const navItems = document.querySelectorAll('.docs-nav-item');
    if (!navItems.length) return;

    const sections = document.querySelectorAll('.doc-section');
    window.addEventListener('scroll', debounce(() => {
        let currentSection = '';
        sections.forEach(sec => {
            const top = sec.offsetTop - 120;
            if (window.scrollY >= top) {
                currentSection = sec.getAttribute('id');
            }
        });

        if (currentSection) {
            navItems.forEach(item => {
                item.classList.toggle('active', item.getAttribute('href') === `#${currentSection}`);
            });
        }
    }, 50));
}

// ----------------------------------------------------------------------
// 1. Tab Switching & State Persistence
// ----------------------------------------------------------------------
function switchTab(target, updateHash = true) {
    if (!target) return;
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    const matchingBtn = document.querySelector(`.tab-btn[data-tab="${target}"]`);
    const activePane = document.getElementById(`pane-${target}`);

    if (!matchingBtn || !activePane) return;

    tabBtns.forEach(b => b.classList.remove('active'));
    tabPanes.forEach(p => p.style.display = 'none');

    matchingBtn.classList.add('active');
    activePane.style.display = 'block';

    localStorage.setItem('north_active_tab', target);
    if (updateHash) {
        history.replaceState(null, '', `#${target}`);
    }

    if (target === 'diagnostics') {
        runDiagnostics();
    } else if (target === 'directory') {
        loadDirectory();
    }
    renderIcons();
}

function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;
            switchTab(target, true);
        });
    });

    // Restore last active tab on page load (from URL hash or localStorage)
    const urlHashTab = window.location.hash ? window.location.hash.replace('#', '').trim() : '';
    const storedTab = localStorage.getItem('north_active_tab');
    const tabToRestore = urlHashTab || storedTab || 'deep-research';

    if (tabToRestore) {
        switchTab(tabToRestore, false);
    }

    // Handle browser back/forward navigation
    window.addEventListener('hashchange', () => {
        const hashTab = window.location.hash ? window.location.hash.replace('#', '').trim() : '';
        if (hashTab) {
            switchTab(hashTab, false);
        }
    });

    // Chip toggle helpers - robust sync with checkbox state
    document.addEventListener('change', (e) => {
        if (e.target.matches('.chip input[type="checkbox"]')) {
            const chip = e.target.closest('.chip');
            if (chip) {
                chip.classList.toggle('active', e.target.checked);
            }
            // Keep Tor switch and Dark Mode chips in sync
            if (e.target.id === 'deep-darkweb-chip') {
                const deepDarkweb = document.getElementById('deep-darkweb');
                if (deepDarkweb) deepDarkweb.checked = e.target.checked;
            } else if (e.target.id === 'deep-darkweb') {
                const deepChip = document.getElementById('deep-darkweb-chip');
                if (deepChip) {
                    deepChip.checked = e.target.checked;
                    deepChip.closest('.chip')?.classList.toggle('active', e.target.checked);
                }
            }
        }
    });

    document.addEventListener('click', (e) => {
        const chipBtn = e.target.closest('button.chip');
        if (chipBtn) {
            chipBtn.classList.toggle('active');
        }
    });

    // Initial sync of chips on DOM ready
    document.querySelectorAll('.chip input[type="checkbox"]').forEach(cb => {
        const chip = cb.closest('.chip');
        if (chip) {
            chip.classList.toggle('active', cb.checked);
        }
    });
}


// ----------------------------------------------------------------------
// Dedicated Links View Generator (with copy all, export, open all)
// ----------------------------------------------------------------------
function renderLinksTable(links, containerEl, searchTitle = 'Investigation') {
    if (!containerEl) return;
    if (!links || links.length === 0) {
        containerEl.innerHTML = `<div class="glass-card" style="text-align:center;color:var(--text-secondary);padding:30px;"><i data-lucide="link-2" class="w-6 h-6 mx-auto mb-2 opacity-40"></i>No links discovered yet. Run a search to populate links.</div>`;
        renderIcons();
        return;
    }

    const uniqueLinks = [];
    const seen = new Set();
    links.forEach(l => {
        const u = typeof l === 'string' ? l : (l.url || '');
        if (u && !seen.has(u)) {
            seen.add(u);
            uniqueLinks.push(typeof l === 'string' ? { url: u, title: u } : l);
        }
    });

    let html = `
        <div class="space-y-3">
            <!-- Action Toolbar for Links -->
            <div class="flex items-center justify-between gap-2 p-2.5 rounded-xl bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-200 dark:border-white/10 flex-wrap">
                <div class="flex items-center gap-2">
                    <span class="text-xs font-mono font-bold text-zinc-800 dark:text-zinc-200">${uniqueLinks.length} Discovered Links</span>
                </div>
                <div class="flex items-center gap-1.5 flex-wrap">
                    <button type="button" id="btn-copy-all-urls" class="px-2.5 py-1 rounded-lg bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 text-xs font-semibold hover:opacity-90 transition-all flex items-center gap-1 shadow-xs">
                        <i data-lucide="copy" class="w-3.5 h-3.5"></i>
                        <span id="copy-urls-label">Copy All Links</span>
                    </button>
                    <button type="button" id="btn-download-urls-txt" class="px-2.5 py-1 rounded-lg bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-200 border border-zinc-200 dark:border-white/10 text-xs font-medium hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-all flex items-center gap-1">
                        <i data-lucide="download" class="w-3.5 h-3.5"></i>
                        <span>Export .txt</span>
                    </button>
                    <button type="button" id="btn-open-all-urls" class="px-2.5 py-1 rounded-lg bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-200 border border-zinc-200 dark:border-white/10 text-xs font-medium hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-all flex items-center gap-1">
                        <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
                        <span>Open All</span>
                    </button>
                </div>
            </div>

            <!-- In-Page Link Search Filter -->
            <div>
                <input type="text" id="links-filter-input" class="w-full bg-white dark:bg-zinc-900/70 border border-zinc-200 dark:border-white/10 rounded-xl px-3 py-2 text-xs text-zinc-900 dark:text-white outline-none focus:border-indigo-500" placeholder="Filter links by domain or keyword...">
            </div>

            <!-- Links List -->
            <div class="space-y-1.5 max-h-[60vh] overflow-y-auto pr-1" id="links-items-list">
                ${uniqueLinks.map((item, idx) => {
                    let hostname = '';
                    try { hostname = new URL(item.url).hostname.replace(/^www\./, ''); } catch(e) { hostname = item.source_engine || 'link'; }
                    const isDark = (item.url || '').includes('.onion');
                    return `
                        <div class="link-item flex items-center justify-between gap-3 p-2.5 rounded-xl bg-white dark:bg-zinc-900/80 border border-zinc-200 dark:border-white/10 hover:border-zinc-300 dark:hover:border-white/20 transition-all shadow-subtle group">
                            <div class="flex items-center gap-2.5 min-w-0 flex-1">
                                <span class="text-[10px] font-mono font-bold text-zinc-400 shrink-0 w-5">#${idx + 1}</span>
                                <span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold shrink-0 ${isDark ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-300 dark:border-amber-800' : 'bg-zinc-100 text-zinc-700 dark:bg-white/10 dark:text-zinc-300'}">
                                    ${isDark ? '🧅 ' + hostname : hostname}
                                </span>
                                <div class="min-w-0 flex-1">
                                    <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" class="text-xs font-medium text-zinc-800 dark:text-zinc-200 hover:text-indigo-600 dark:hover:text-indigo-400 truncate block">
                                        ${escapeHtml(item.title || item.url)}
                                    </a>
                                    <span class="text-[11px] font-mono text-zinc-400 truncate block">${escapeHtml(item.url)}</span>
                                </div>
                            </div>
                            <div class="flex items-center gap-1.5 shrink-0">
                                <button type="button" class="btn-copy-single-url p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-white/10 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-all" data-url="${escapeHtml(item.url)}" title="Copy Link">
                                    <i data-lucide="copy" class="w-3.5 h-3.5"></i>
                                </button>
                                <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" class="p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-white/10 text-zinc-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-all" title="Open Link">
                                    <i data-lucide="arrow-up-right" class="w-3.5 h-3.5"></i>
                                </a>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;

    containerEl.innerHTML = html;
    renderIcons();

    const copyAllBtn = document.getElementById('btn-copy-all-urls');
    const copyLabel = document.getElementById('copy-urls-label');
    if (copyAllBtn) {
        copyAllBtn.addEventListener('click', () => {
            const allText = uniqueLinks.map(l => l.url).join('\n');
            navigator.clipboard.writeText(allText).then(() => {
                if (copyLabel) copyLabel.textContent = '✓ Copied All!';
                setTimeout(() => { if (copyLabel) copyLabel.textContent = 'Copy All Links'; }, 2000);
            });
        });
    }

    const dlTxtBtn = document.getElementById('btn-download-urls-txt');
    if (dlTxtBtn) {
        dlTxtBtn.addEventListener('click', () => {
            const allText = uniqueLinks.map(l => (l.title ? `# ${l.title}\n${l.url}` : l.url)).join('\n\n');
            const blob = new Blob([allText], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `links_${searchTitle.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 30)}.txt`;
            a.click();
            URL.revokeObjectURL(url);
        });
    }

    const openAllBtn = document.getElementById('btn-open-all-urls');
    if (openAllBtn) {
        openAllBtn.addEventListener('click', () => {
            if (uniqueLinks.length > 10) {
                if (!confirm(`Open ${uniqueLinks.length} tabs in your browser?`)) return;
            }
            uniqueLinks.forEach(l => window.open(l.url, '_blank'));
        });
    }

    containerEl.querySelectorAll('.btn-copy-single-url').forEach(btn => {
        btn.addEventListener('click', () => {
            const u = btn.dataset.url;
            if (u) {
                navigator.clipboard.writeText(u);
                btn.innerHTML = '<i data-lucide="check" class="w-3.5 h-3.5 text-emerald-500"></i>';
                renderIcons();
                setTimeout(() => {
                    btn.innerHTML = '<i data-lucide="copy" class="w-3.5 h-3.5"></i>';
                    renderIcons();
                }, 1500);
            }
        });
    });

    const filterInput = document.getElementById('links-filter-input');
    const itemsList = document.getElementById('links-items-list');
    if (filterInput && itemsList) {
        filterInput.addEventListener('input', () => {
            const q = filterInput.value.trim().toLowerCase();
            itemsList.querySelectorAll('.link-item').forEach(item => {
                const text = item.textContent.toLowerCase();
                item.style.display = (!q || text.includes(q)) ? 'flex' : 'none';
            });
        });
    }
}

// ----------------------------------------------------------------------
// History Lookup & Replay Component
// ----------------------------------------------------------------------
async function renderHistorySection(containerEl, onSelectHistoryItem) {
    if (!containerEl) return;
    containerEl.innerHTML = `<div class="glass-card" style="text-align:center;color:var(--text-secondary);padding:24px;"><i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-500"></i>Loading search history archive...</div>`;
    renderIcons();

    let localHistory = [];
    try {
        localHistory = JSON.parse(localStorage.getItem('north_search_history') || '[]');
    } catch(e) {}

    let serverJobs = [];
    try {
        const res = await fetch('/api/history');
        if (res.ok) {
            const data = await res.json();
            serverJobs = data.jobs || [];
        }
    } catch(e) {}

    const combined = [];
    const seenQueries = new Set();

    localHistory.forEach(h => {
        if (h && h.query && !seenQueries.has(h.query.toLowerCase())) {
            seenQueries.add(h.query.toLowerCase());
            combined.push(h);
        }
    });

    serverJobs.forEach(j => {
        if (j && j.query && !seenQueries.has(j.query.toLowerCase())) {
            seenQueries.add(j.query.toLowerCase());
            combined.push({
                query: j.query,
                type: 'deep',
                job_id: j.id,
                total_sources: j.total_sources || j.sources_count || 0,
                findings_count: j.findings_count || 0,
                summary: j.summary || '',
                timestamp: (j.created_at ? j.created_at * 1000 : Date.now()),
            });
        }
    });

    if (combined.length === 0) {
        containerEl.innerHTML = `
            <div class="glass-card" style="text-align:center;color:var(--text-secondary);padding:30px;">
                <i data-lucide="history" class="w-8 h-8 mx-auto mb-2 opacity-40"></i>
                <p>No past search investigations recorded yet.</p>
            </div>
        `;
        renderIcons();
        return;
    }

    let html = `
        <div class="space-y-3">
            <div class="flex items-center justify-between px-1">
                <span class="text-xs font-mono font-bold text-zinc-700 dark:text-zinc-300">${combined.length} Past Investigations</span>
                <button type="button" id="btn-clear-local-history" class="text-[11px] font-mono text-rose-500 hover:text-rose-600 transition-colors">Clear History</button>
            </div>
            <div class="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
                ${combined.map((h, i) => {
                    const isDeep = h.type === 'deep' || !!h.job_id;
                    const dateStr = h.timestamp ? new Date(h.timestamp).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
                    return `
                        <div class="p-3 rounded-xl bg-white dark:bg-zinc-900/80 border border-zinc-200 dark:border-white/10 hover:border-indigo-400 dark:hover:border-indigo-600/50 transition-all shadow-subtle flex flex-col gap-2">
                            <div class="flex items-center justify-between gap-2">
                                <span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${isDeep ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800/60' : 'bg-zinc-100 text-zinc-700 dark:bg-white/10 dark:text-zinc-300'}">
                                    ${isDeep ? '🧠 Deep Research' : '⚡ Quick Multi-Search'}
                                </span>
                                <span class="text-[10px] font-mono text-zinc-400">${dateStr}</span>
                            </div>
                            <div class="flex items-center justify-between gap-3">
                                <div class="min-w-0 flex-1">
                                    <div class="text-xs font-bold text-zinc-900 dark:text-white truncate">${escapeHtml(h.query)}</div>
                                    ${h.summary ? `<p class="text-[11px] text-zinc-500 dark:text-zinc-400 line-clamp-1 mt-0.5">${escapeHtml(h.summary)}</p>` : ''}
                                </div>
                                <button type="button" class="btn-load-history-item shrink-0 px-3 py-1.5 rounded-lg bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 text-xs font-semibold hover:opacity-90 transition-all flex items-center gap-1 shadow-xs" data-idx="${i}">
                                    <span>Replay</span>
                                    <i data-lucide="play" class="w-3 h-3 fill-current"></i>
                                </button>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;

    containerEl.innerHTML = html;
    renderIcons();

    const clearHistBtn = document.getElementById('btn-clear-local-history');
    if (clearHistBtn) {
        clearHistBtn.addEventListener('click', () => {
            if (confirm('Clear local search history?')) {
                localStorage.removeItem('north_search_history');
                renderHistorySection(containerEl, onSelectHistoryItem);
            }
        });
    }

    containerEl.querySelectorAll('.btn-load-history-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = parseInt(btn.dataset.idx, 10);
            const item = combined[idx];
            if (item && onSelectHistoryItem) {
                onSelectHistoryItem(item);
            }
        });
    });
}

// Helper to record history item
function recordSearchHistory(item) {
    try {
        let history = JSON.parse(localStorage.getItem('north_search_history') || '[]');
        history = history.filter(h => h.query.toLowerCase() !== item.query.toLowerCase());
        history.unshift(item);
        if (history.length > 50) history = history.slice(0, 50);
        localStorage.setItem('north_search_history', JSON.stringify(history));
    } catch(e) {}
}


// ----------------------------------------------------------------------
// 2. Quick Multi-Engine Search with 60/40 Split Workspace
// ----------------------------------------------------------------------
function initQuickSearch() {
    const form = document.getElementById('quick-search-form');
    const workspace = document.getElementById('quick-search-workspace');
    const resultsContainer = document.getElementById('quick-search-results');
    const statusBox = document.getElementById('quick-search-status');
    const countBadge = document.getElementById('results-count-badge');
    const linksCountBadge = document.getElementById('qs-links-count-badge');
    const liveLog = document.getElementById('live-search-log');
    const domainsList = document.getElementById('crawled-domains-list');
    const controlStatus = document.getElementById('live-control-status');
    const stopBtn = document.getElementById('btn-stop-search');
    const refineInput = document.getElementById('live-refine-input');
    const refineBtn = document.getElementById('btn-apply-refine');
    const refineStatus = document.getElementById('refine-match-status');

    // Sub-view toggle buttons
    const btnViewCards = document.getElementById('btn-qs-view-cards');
    const btnViewLinks = document.getElementById('btn-qs-view-links');
    const btnViewHistory = document.getElementById('btn-qs-view-history');
    const btnClearResults = document.getElementById('btn-clear-qs-results');

    let qsActiveView = 'cards'; // 'cards' | 'links' | 'history'

    if (!form) return;

    function logEvent(msg) {
        if (!liveLog) return;
        const ts = new Date().toLocaleTimeString();
        liveLog.textContent = `[${ts}] ${msg}\n` + liveLog.textContent.slice(0, 1000);
    }

    function setSubViewBtnState(view) {
        qsActiveView = view;
        const btns = [
            { id: btnViewCards, key: 'cards' },
            { id: btnViewLinks, key: 'links' },
            { id: btnViewHistory, key: 'history' }
        ];
        btns.forEach(b => {
            if (b.id) {
                if (b.key === view) {
                    b.id.className = 'px-2.5 py-1 rounded-lg font-semibold bg-white dark:bg-zinc-800 text-zinc-900 dark:text-white shadow-xs transition-all flex items-center gap-1.5';
                } else {
                    b.id.className = 'px-2.5 py-1 rounded-lg font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white transition-all flex items-center gap-1.5';
                }
            }
        });
    }

    function renderCardsView(results) {
        if (!results || !results.length) {
            resultsContainer.innerHTML = '<div class="glass-card" style="text-align:center;color:var(--text-secondary);padding:30px;">No matching results found for this criteria. Try refining keywords.</div>';
            return;
        }

        let html = '<div class="results-grid">';
        results.forEach(r => {
            const isDark = r.source_type === 'darkweb' || r.url.includes('.onion');
            const tagClass = isDark ? 'source-tag darkweb' : 'source-tag clearnet';
            const tagLabel = isDark ? `🧅 ${r.source_engine}` : r.source_engine;

            html += `
                <div class="result-card">
                    <div class="result-card-header">
                        <span class="${tagClass}">${tagLabel}</span>
                        <span style="font-size:11px;font-family:var(--font-mono);color:var(--text-muted);">#${r.rank || ''}</span>
                    </div>
                    <a href="${r.url}" target="_blank" rel="noopener noreferrer" class="result-title">${escapeHtml(r.title || r.url)}</a>
                    <p class="result-snippet">${escapeHtml(r.snippet || 'No preview snippet available.')}</p>
                    <div class="result-url" title="${r.url}">${escapeHtml(r.url)}</div>
                </div>
            `;
        });
        html += '</div>';
        resultsContainer.innerHTML = html;
        renderIcons();
    }

    // Wire Sub-View Switchers
    if (btnViewCards) {
        btnViewCards.addEventListener('click', () => {
            setSubViewBtnState('cards');
            renderCardsView(currentSearchResults);
        });
    }

    if (btnViewLinks) {
        btnViewLinks.addEventListener('click', () => {
            setSubViewBtnState('links');
            const q = document.getElementById('qs-query')?.value || 'QuickSearch';
            renderLinksTable(currentSearchResults, resultsContainer, q);
        });
    }

    if (btnViewHistory) {
        btnViewHistory.addEventListener('click', () => {
            setSubViewBtnState('history');
            renderHistorySection(resultsContainer, (item) => {
                if (item.type === 'deep') {
                    switchTab('deep-search');
                    const deepInput = document.getElementById('deep-query');
                    if (deepInput) deepInput.value = item.query;
                    document.getElementById('deep-research-form')?.dispatchEvent(new Event('submit'));
                } else {
                    const qsInput = document.getElementById('qs-query');
                    if (qsInput) qsInput.value = item.query;
                    form.dispatchEvent(new Event('submit'));
                }
            });
        });
    }

    if (btnClearResults) {
        btnClearResults.addEventListener('click', () => {
            currentSearchResults = [];
            if (workspace) workspace.classList.add('hidden');
            resultsContainer.innerHTML = '';
            localStorage.removeItem('north_active_quick_search');
            if (countBadge) countBadge.textContent = '0 results';
            if (linksCountBadge) linksCountBadge.textContent = '0';
        });
    }

    // Stop button handler
    if (stopBtn) {
        stopBtn.addEventListener('click', () => {
            if (activeSearchAbortController) {
                activeSearchAbortController.abort();
                activeSearchAbortController = null;
                if (controlStatus) controlStatus.textContent = 'Halted by User';
                logEvent('Investigation stopped by operator.');
            }
        });
    }

    // Live In-Page Keyword Refiner Handler
    function applyKeywordRefine() {
        const filterTerm = (refineInput?.value || '').trim().toLowerCase();
        if (!currentSearchResults || !currentSearchResults.length) return;

        let matchedCount = 0;
        const cards = resultsContainer.querySelectorAll('.result-card');
        
        cards.forEach(card => {
            const text = card.textContent.toLowerCase();
            if (!filterTerm || text.includes(filterTerm)) {
                card.style.display = 'flex';
                matchedCount++;
            } else {
                card.style.display = 'none';
            }
        });

        if (refineStatus) {
            refineStatus.textContent = filterTerm 
                ? `Showing ${matchedCount} of ${currentSearchResults.length} matching "${filterTerm}"`
                : `Matching all ${currentSearchResults.length} results`;
        }
        if (countBadge) countBadge.textContent = `${matchedCount} results`;
        logEvent(`In-page filter applied: "${filterTerm || 'ALL'}" (${matchedCount} visible)`);
    }

    if (refineInput) {
        refineInput.addEventListener('input', debounce(applyKeywordRefine, 150));
    }
    if (refineBtn) {
        refineBtn.addEventListener('click', applyKeywordRefine);
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = document.getElementById('qs-query').value.trim();
        if (!query) return;

        const engines = [];
        document.querySelectorAll('#qs-engines .engine-toggle.active').forEach(btn => {
            if (btn.dataset.engine) engines.push(btn.dataset.engine);
        });
        if (engines.length === 0) {
            engines.push('duckduckgo', 'bing', 'knowledge');
        }

        const darkwebMode = document.getElementById('qs-darkweb-mode-input')?.value || 'normal';
        const darkweb = (darkwebMode === 'darknet_only' || darkwebMode === 'all');
        const targetSite = document.getElementById('qs-target-site')?.value.trim() || '';
        const mustInclude = document.getElementById('qs-must-include')?.value.trim() || '';
        const mustExclude = document.getElementById('qs-must-exclude')?.value.trim() || '';

        // Show 60/40 Split Workspace
        if (workspace) workspace.classList.remove('hidden');
        if (controlStatus) controlStatus.textContent = `Searching ${engines.length} Providers...`;
        if (countBadge) countBadge.textContent = 'Querying...';

        logEvent(`Dispatched query: "${query}" across ${engines.length} engines.`);
        logEvent(`Mode: ${darkwebMode === 'darknet_only' ? '🧅 Only Darknet (Tor)' : (darkwebMode === 'all' ? '🌐 Hybrid All (Clearnet + Tor)' : '🛡️ Normal Clearnet')}`);
        if (targetSite) logEvent(`Domain constraint: site:${targetSite}`);
        if (mustInclude) logEvent(`Required keywords: ${mustInclude}`);

        setSubViewBtnState('cards');
        statusBox.innerHTML = `<span class="status-pill"><span class="status-dot running"></span> Active Dispatch</span>`;
        resultsContainer.innerHTML = '<div class="glass-card" style="text-align:center;color:var(--text-secondary);padding:30px;"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-500"></i>Harvesting multi-source intelligence...</div>';
        renderIcons();

        if (domainsList) {
            domainsList.innerHTML = '<div class="text-slate-400 text-[11px] animate-pulse">Resolving endpoints...</div>';
        }

        activeSearchAbortController = new AbortController();

        const fd = new FormData();
        fd.append('query', query);
        fd.append('target_site', targetSite);
        fd.append('engines', engines.join(','));
        fd.append('darkweb', darkweb);
        fd.append('darkweb_mode', darkwebMode);
        fd.append('must_include', mustInclude);
        fd.append('must_exclude', mustExclude);

        try {
            const res = await fetch('/api/quick-search', { 
                method: 'POST', 
                body: fd,
                signal: activeSearchAbortController.signal
            });
            const data = await res.json();
            activeSearchAbortController = null;

            if (data.error) {
                statusBox.innerHTML = `<span class="status-pill"><span class="status-dot error"></span> Error</span>`;
                resultsContainer.innerHTML = `<div class="glass-card" style="color:var(--danger);padding:20px;">${escapeHtml(data.error)}</div>`;
                if (controlStatus) controlStatus.textContent = 'Failed';
                return;
            }

            currentSearchResults = data.results || [];
            if (controlStatus) controlStatus.textContent = `Complete (${data.elapsed_seconds}s)`;
            statusBox.innerHTML = `<span class="status-pill"><span class="status-dot ok"></span> ${data.elapsed_seconds}s</span>`;
            if (countBadge) countBadge.textContent = `${currentSearchResults.length} results`;
            if (linksCountBadge) linksCountBadge.textContent = `${currentSearchResults.length}`;

            logEvent(`Discovered ${currentSearchResults.length} intelligence records in ${data.elapsed_seconds}s.`);

            // Save active search in localStorage for refresh persistence
            localStorage.setItem('north_active_quick_search', JSON.stringify({
                query,
                results: currentSearchResults,
                elapsed_seconds: data.elapsed_seconds,
                timestamp: Date.now()
            }));

            // Record to history archive
            recordSearchHistory({
                query,
                type: 'quick',
                results_count: currentSearchResults.length,
                timestamp: Date.now()
            });

            // Populate Discovered Domains in right panel
            const domainCounts = {};
            currentSearchResults.forEach(r => {
                try {
                    const host = new URL(r.url).hostname.replace(/^www\./, '');
                    domainCounts[host] = (domainCounts[host] || 0) + 1;
                } catch(e) {
                    domainCounts[r.source_engine] = (domainCounts[r.source_engine] || 0) + 1;
                }
            });

            if (domainsList) {
                let domHtml = '';
                Object.entries(domainCounts).forEach(([dom, cnt]) => {
                    domHtml += `
                        <div class="flex items-center justify-between p-1.5 rounded-lg bg-slate-50 dark:bg-white/[0.03] border border-slate-200/60 dark:border-white/[0.04]">
                            <span class="font-mono text-[11px] text-slate-700 dark:text-slate-300 truncate">${escapeHtml(dom)}</span>
                            <span class="text-[10px] font-mono font-bold bg-slate-200 dark:bg-white/10 px-1.5 py-0.2 rounded text-slate-600 dark:text-slate-300">${cnt}</span>
                        </div>
                    `;
                });
                domainsList.innerHTML = domHtml || '<div class="text-slate-400 text-[11px]">No external domains.</div>';
            }

            renderCardsView(currentSearchResults);
            loadKnowledgeStats();

        } catch (err) {
            if (err.name === 'AbortError') {
                resultsContainer.innerHTML = '<div class="glass-card" style="text-align:center;color:var(--text-secondary);padding:24px;">Investigation cancelled.</div>';
                return;
            }
            statusBox.innerHTML = `<span class="status-pill"><span class="status-dot error"></span> Error</span>`;
            resultsContainer.innerHTML = `<div class="glass-card" style="color:var(--danger);padding:20px;">Network Error: ${escapeHtml(err.message)}</div>`;
        }
    });
}


// ----------------------------------------------------------------------
// 3. Visual & Reverse Image Search (Local DB + Online DB)
// ----------------------------------------------------------------------
function initVisualSearch() {
    const dropzone = document.getElementById('image-dropzone');
    const fileInput = document.getElementById('image-file-input');
    const previewContainer = document.getElementById('image-preview-area');
    const localGrid = document.getElementById('local-image-matches');
    const onlineGrid = document.getElementById('online-image-matches');
    const statusEl = document.getElementById('visual-search-status');

    if (!dropzone || !fileInput) return;

    ['dragenter', 'dragover'].forEach(name => {
        dropzone.addEventListener(name, (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
    });
    ['dragleave', 'drop'].forEach(name => {
        dropzone.addEventListener(name, (e) => { e.preventDefault(); dropzone.classList.remove('dragover'); });
    });

    dropzone.addEventListener('drop', (e) => {
        if (e.dataTransfer.files.length) {
            handleImageUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            handleImageUpload(fileInput.files[0]);
        }
    });

    async function handleImageUpload(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            previewContainer.innerHTML = `
                <div class="preview-container">
                    <img src="${e.target.result}" class="preview-thumb" alt="Uploaded Image">
                    <div>
                        <strong style="color:var(--text-primary);font-weight:600;">${escapeHtml(file.name)}</strong>
                        <div style="font-size:11.5px;font-family:var(--font-mono);color:var(--text-secondary);">${(file.size / 1024).toFixed(1)} KB · Scanning DB</div>
                    </div>
                </div>
            `;
        };
        reader.readAsDataURL(file);

        statusEl.innerHTML = '<span class="status-pill"><span class="status-dot running"></span> Scanning local DB & querying online reverse search engines...</span>';
        localGrid.innerHTML = '<div style="color:var(--text-secondary);padding:20px;">Matching local embeddings & perceptual hashes...</div>';
        onlineGrid.innerHTML = '<div style="color:var(--text-secondary);padding:20px;">Querying reverse visual web engines...</div>';

        const fd = new FormData();
        fd.append('file', file);
        fd.append('top_k', 8);

        try {
            const res = await fetch('/api/reverse-image', { method: 'POST', body: fd });
            const data = await res.json();

            statusEl.innerHTML = '<span class="status-pill"><span class="status-dot ok"></span> Visual Search Completed</span>';

            // 1. Render Local Matches
            if (!data.local_matches || data.local_matches.length === 0) {
                localGrid.innerHTML = '<div style="color:var(--text-secondary);padding:20px;">No matching records found in local database.</div>';
            } else {
                let localHtml = '';
                data.local_matches.forEach(m => {
                    const imgSrc = m.photo ? `/performers/photo/${encodeURIComponent(m.photo)}` : '';
                    localHtml += `
                        <div class="visual-card" onclick="openEntityModal('${escapeHtml(m.name)}', '${imgSrc}', '${Number(m.views||0).toLocaleString()} views · ${m.videos||0} vids', '${escapeHtml(m.url||'')}')">
                            ${imgSrc ? `<img src="${imgSrc}" alt="${escapeHtml(m.name)}" loading="lazy">` : '<div style="height:160px;background:#111;display:flex;align-items:center;justify-content:center;color:var(--text-muted);">No Photo</div>'}
                            <div class="visual-card-body">
                                <div class="visual-name">${escapeHtml(m.name)}</div>
                                <div class="visual-meta">
                                    <span class="sim-badge">${m.similarity_pct}% match</span>
                                    <span>${m.videos} vids</span>
                                </div>
                            </div>
                        </div>
                    `;
                });
                localGrid.innerHTML = localHtml;
            }

            // 2. Render Online Reverse Matches
            if (!data.online_matches || data.online_matches.length === 0) {
                onlineGrid.innerHTML = '<div style="color:var(--text-secondary);padding:20px;">No online reverse results returned.</div>';
            } else {
                let onlineHtml = '';
                data.online_matches.forEach(item => {
                    onlineHtml += `
                        <div class="result-card">
                            <div class="result-card-header">
                                <span class="source-tag clearnet">${item.engine}</span>
                            </div>
                            <a href="${item.url}" target="_blank" class="result-title">${escapeHtml(item.title)}</a>
                            <p class="result-snippet">${escapeHtml(item.snippet || '')}</p>
                            <div class="result-url">${escapeHtml(item.url)}</div>
                        </div>
                    `;
                });
                onlineGrid.innerHTML = onlineHtml;
            }
            renderIcons();

        } catch (err) {
            statusEl.innerHTML = `<span class="status-pill"><span class="status-dot error"></span> Error: ${err.message}</span>`;
        }
    }
}

// ----------------------------------------------------------------------
// 4. Custom Scraper & DB Updater
// ----------------------------------------------------------------------
function initScraper() {
    const form = document.getElementById('scraper-form');
    const statusBox = document.getElementById('scraper-status-box');
    const progressFill = document.getElementById('scraper-progress-fill');
    const logEl = document.getElementById('scraper-log');

    // Quick Preset buttons
    document.querySelectorAll('.preset-target-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const url = btn.dataset.url || '';
            const inc = btn.dataset.include || '';
            const exc = btn.dataset.exclude || '';
            
            const urlInput = document.getElementById('scraper-url');
            const incInput = document.getElementById('scraper-must-include');
            const excInput = document.getElementById('scraper-must-exclude');
            
            if (urlInput) urlInput.value = url;
            if (incInput) incInput.value = inc;
            if (excInput) excInput.value = exc;
            
            // Visual feedback
            document.querySelectorAll('.preset-target-btn').forEach(b => b.classList.remove('active', 'border-indigo-500'));
            btn.classList.add('active', 'border-indigo-500');
        });
    });

    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = document.getElementById('scraper-url').value.trim();
        const mustInclude = document.getElementById('scraper-must-include').value.trim();
        const mustExclude = document.getElementById('scraper-must-exclude').value.trim();
        const maxItems = document.getElementById('scraper-max-items').value || 50;
        const downloadImages = document.getElementById('scraper-download-images').checked;

        if (!url) return;

        const fd = new FormData();
        fd.append('url', url);
        fd.append('must_include', mustInclude);
        fd.append('must_exclude', mustExclude);
        fd.append('max_items', maxItems);
        fd.append('download_images', downloadImages);

        statusBox.innerHTML = '<span class="status-pill"><span class="status-dot running"></span> Scraper active...</span>';
        logEl.textContent = `[Init] Starting scraper on: ${url}\n[Rules] Must include: "${mustInclude}" | Exclude: "${mustExclude}"\n`;

        try {
            const res = await fetch('/api/scraper/start', { method: 'POST', body: fd });
            const data = await res.json();
            if (data.error) {
                statusBox.innerHTML = `<span class="status-pill"><span class="status-dot error"></span> ${data.error}</span>`;
                return;
            }

            const interval = setInterval(async () => {
                const sRes = await fetch('/api/scraper/status');
                const sData = await sRes.json();
                const sc = sData.scraper || {};

                if (sc.message) {
                    logEl.textContent += `\n[Status] ${sc.message}`;
                    logEl.scrollTop = logEl.scrollHeight;
                }

                if (sc.total > 0) {
                    const pct = Math.min(100, Math.round((sc.collected / sc.total) * 100));
                    progressFill.style.width = `${pct}%`;
                }

                if (sc.state === 'done' || sc.state === 'idle' || sc.state === 'error') {
                    clearInterval(interval);
                    statusBox.innerHTML = `<span class="status-pill"><span class="status-dot ${sc.state === 'error' ? 'error' : 'ok'}"></span> ${sc.message || 'Completed'}</span>`;
                    loadDirectory();
                }
            }, 1200);

        } catch (err) {
            statusBox.innerHTML = `<span class="status-pill"><span class="status-dot error"></span> ${err.message}</span>`;
        }
    });
}

// ----------------------------------------------------------------------
// 5. System Diagnostics & Engine Health Check
// ----------------------------------------------------------------------
async function initDiagnostics() {
    const btn = document.getElementById('btn-run-diag');
    if (btn) {
        btn.addEventListener('click', runDiagnostics);
    }
}

async function runDiagnostics() {
    const tableBody = document.querySelector('#diag-table tbody');
    if (!tableBody) return;

    tableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-secondary);padding:24px;">Pinging search engines, Tor gateways, and Ollama server...</td></tr>';

    try {
        const res = await fetch('/api/diagnostics');
        const data = await res.json();

        let html = '';
        for (const [engine, info] of Object.entries(data)) {
            const isOk = info.status === 'ok' || info.status === 'running' || info.status === 'online';
            const statusClass = isOk ? 'ok' : 'error';
            const statusLabel = isOk ? (info.status === 'ok' ? 'ONLINE (200 OK)' : info.status.toUpperCase()) : (info.error || info.status.toUpperCase());
            const latency = info.latency_ms ? `${info.latency_ms} ms` : '—';
            const typeBadge = info.type === 'darknet' ? '🧅 Darknet' : '🌐 Clearnet';

            html += `
                <tr>
                    <td style="font-weight:600;color:var(--text-primary);">${engine.toUpperCase()}</td>
                    <td><span class="source-tag ${info.type === 'darknet' ? 'darkweb' : 'clearnet'}">${typeBadge}</span></td>
                    <td><span class="status-pill"><span class="status-dot ${statusClass}"></span> ${statusLabel}</span></td>
                    <td style="font-family:var(--font-mono);font-size:11.5px;color:var(--text-muted);">${latency}</td>
                </tr>
            `;
        }
        tableBody.innerHTML = html;
        renderIcons();
    } catch (err) {
        tableBody.innerHTML = `<tr><td colspan="4" style="color:var(--danger);">Diagnostics failed: ${err.message}</td></tr>`;
    }
}

// ----------------------------------------------------------------------
// 6. Local Directory Explorer & Creator Hub
// ----------------------------------------------------------------------
let dirOffset = 0;
const dirLimit = 32;
let dirTotal = 0;
let dirLoading = false;
let dirObserver = null;
let crawlerPollInterval = null;

function initDirectory() {
    const searchInput = document.getElementById('dir-search-input');
    const categorySelect = document.getElementById('dir-category-select');
    const countrySelect = document.getElementById('dir-country-select');
    const ageMinInput = document.getElementById('dir-age-min');
    const ageMaxInput = document.getElementById('dir-age-max');
    const sortSelect = document.getElementById('dir-sort-select');
    const hasPhotoCb = document.getElementById('dir-has-photo-cb');
    const resetBtn = document.getElementById('btn-reset-filters');

    // Pagination buttons
    const btnFirst = document.getElementById('btn-page-first');
    const btnPrev = document.getElementById('btn-page-prev');
    const btnNext = document.getElementById('btn-page-next');
    const btnPrevTop = document.getElementById('btn-page-prev-top');
    const btnNextTop = document.getElementById('btn-page-next-top');

    // Crawler buttons
    const startCrawlBtn = document.getElementById('btn-start-creator-crawl');
    const pauseCrawlBtn = document.getElementById('btn-crawler-pause');
    const stopCrawlBtn = document.getElementById('btn-crawler-stop');

    // Filter Listeners
    if (searchInput) {
        searchInput.addEventListener('input', debounce(() => { dirOffset = 0; loadDirectory(false); }, 300));
    }
    if (categorySelect) {
        categorySelect.addEventListener('change', () => { dirOffset = 0; loadDirectory(false); });
    }
    if (countrySelect) {
        countrySelect.addEventListener('change', () => { dirOffset = 0; loadDirectory(false); });
    }
    if (ageMinInput) {
        ageMinInput.addEventListener('input', debounce(() => { dirOffset = 0; loadDirectory(false); }, 400));
    }
    if (ageMaxInput) {
        ageMaxInput.addEventListener('input', debounce(() => { dirOffset = 0; loadDirectory(false); }, 400));
    }
    if (sortSelect) {
        sortSelect.addEventListener('change', () => { dirOffset = 0; loadDirectory(false); });
    }
    if (hasPhotoCb) {
        hasPhotoCb.addEventListener('change', () => { dirOffset = 0; loadDirectory(false); });
    }

    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            if (searchInput) searchInput.value = '';
            if (categorySelect) categorySelect.value = '';
            if (countrySelect) countrySelect.value = '';
            if (ageMinInput) ageMinInput.value = '';
            if (ageMaxInput) ageMaxInput.value = '';
            if (sortSelect) sortSelect.value = 'has_photo';
            if (hasPhotoCb) hasPhotoCb.checked = false;
            dirOffset = 0;
            loadDirectory(false);
        });
    }

    // Pagination Listeners
    if (btnFirst) {
        btnFirst.addEventListener('click', () => {
            if (dirOffset > 0) {
                dirOffset = 0;
                loadDirectory(false);
                scrollToDirectoryTop();
            }
        });
    }

    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            if (dirOffset >= dirLimit) {
                dirOffset -= dirLimit;
                loadDirectory(false);
                scrollToDirectoryTop();
            }
        });
    }

    if (btnPrevTop) {
        btnPrevTop.addEventListener('click', () => {
            if (dirOffset >= dirLimit) {
                dirOffset -= dirLimit;
                loadDirectory(false);
                scrollToDirectoryTop();
            }
        });
    }

    if (btnNext) {
        btnNext.addEventListener('click', () => {
            if (dirOffset + dirLimit < dirTotal) {
                dirOffset += dirLimit;
                loadDirectory(false);
                scrollToDirectoryTop();
            }
        });
    }

    if (btnNextTop) {
        btnNextTop.addEventListener('click', () => {
            if (dirOffset + dirLimit < dirTotal) {
                dirOffset += dirLimit;
                loadDirectory(false);
                scrollToDirectoryTop();
            }
        });
    }

    // Infinite Scroll IntersectionObserver
    setupInfiniteScroll();

    // Start Database Crawler / Updater
    if (startCrawlBtn) {
        startCrawlBtn.addEventListener('click', async () => {
            const cat = document.getElementById('crawl-category-select')?.value || 'OnlyFans Star';
            const count = parseInt(document.getElementById('crawl-count-input')?.value || '150', 10);
            
            showCrawlerTelemetry(true);
            updateCrawlerUI('running', `Starting database update (${count} models)...`, 0, count);

            const fd = new FormData();
            fd.append('action', 'start');
            fd.append('category', cat);
            fd.append('max_performers', count);

            try {
                const res = await fetch('/api/performers/crawler-control', { method: 'POST', body: fd });
                const data = await res.json();
                if (data.error) {
                    updateCrawlerUI('error', 'Error: ' + data.error, 0, count);
                    return;
                }
                startCrawlerPolling();
            } catch (err) {
                updateCrawlerUI('error', 'Network error: ' + err.message, 0, count);
            }
        });
    }

    // Pause / Resume Crawler
    if (pauseCrawlBtn) {
        pauseCrawlBtn.addEventListener('click', async () => {
            const isPaused = pauseCrawlBtn.dataset.state === 'paused';
            const action = isPaused ? 'resume' : 'pause';
            
            const fd = new FormData();
            fd.append('action', action);

            try {
                const res = await fetch('/api/performers/crawler-control', { method: 'POST', body: fd });
                const data = await res.json();
                if (action === 'pause') {
                    setPauseBtnState(true);
                } else {
                    setPauseBtnState(false);
                }
            } catch (e) {
                console.error("Pause/Resume error", e);
            }
        });
    }

    // Stop Crawler
    if (stopCrawlBtn) {
        stopCrawlBtn.addEventListener('click', async () => {
            const fd = new FormData();
            fd.append('action', 'stop');

            try {
                const res = await fetch('/api/performers/crawler-control', { method: 'POST', body: fd });
                const data = await res.json();
                updateCrawlerUI('stopped', data.message || 'Crawler stopped by user.', 0, 0);
                setTimeout(() => { loadDirectory(false); }, 1000);
            } catch (e) {
                console.error("Stop error", e);
            }
        });
    }

    // Check existing crawler status on load
    checkInitialCrawlerStatus();
}

function scrollToDirectoryTop() {
    const mainBox = document.querySelector('.dir-main-box');
    if (mainBox) {
        mainBox.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function setupInfiniteScroll() {
    const sentinel = document.getElementById('dir-scroll-sentinel');
    if (!sentinel) return;

    if (dirObserver) {
        dirObserver.disconnect();
    }

    dirObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !dirLoading) {
                if (dirOffset + dirLimit < dirTotal) {
                    dirOffset += dirLimit;
                    loadDirectory(true);
                }
            }
        });
    }, { rootMargin: '200px' });

    dirObserver.observe(sentinel);
}

function setPauseBtnState(paused) {
    const pauseBtn = document.getElementById('btn-crawler-pause');
    if (!pauseBtn) return;
    if (paused) {
        pauseBtn.dataset.state = 'paused';
        pauseBtn.className = 'btn-ctrl-resume flex-1 justify-center';
        pauseBtn.innerHTML = '<i data-lucide="play" class="w-3.5 h-3.5"></i><span>Resume</span>';
    } else {
        pauseBtn.dataset.state = 'running';
        pauseBtn.className = 'btn-ctrl-pause flex-1 justify-center';
        pauseBtn.innerHTML = '<i data-lucide="pause" class="w-3.5 h-3.5"></i><span>Pause</span>';
    }
    renderIcons();
}

function showCrawlerTelemetry(show) {
    const panel = document.getElementById('crawler-telemetry-panel');
    const badge = document.getElementById('crawler-state-badge');
    if (panel) panel.style.display = show ? 'flex' : 'none';
    if (badge) badge.style.display = show ? 'inline-flex' : 'none';
}

function updateCrawlerUI(state, message, collected, total) {
    const fill = document.getElementById('crawler-progress-fill');
    const counter = document.getElementById('crawler-progress-counter');
    const msgEl = document.getElementById('crawler-status-msg');
    const badge = document.getElementById('crawler-state-badge');

    const pct = total > 0 ? Math.min(100, Math.round((collected / total) * 100)) : 0;
    if (fill) fill.style.width = `${pct}%`;
    if (counter) counter.textContent = `${Number(collected).toLocaleString()} / ${Number(total).toLocaleString()} (${pct}%)`;
    if (msgEl) {
        msgEl.textContent = message || '';
        msgEl.title = message || '';
    }

    if (badge) {
        badge.textContent = state.toUpperCase();
        if (state === 'running') {
            badge.style.background = 'rgba(99, 102, 241, 0.15)';
            badge.style.color = '#818cf8';
            setPauseBtnState(false);
        } else if (state === 'paused') {
            badge.style.background = 'rgba(217, 119, 6, 0.15)';
            badge.style.color = '#fbbf24';
            setPauseBtnState(true);
        } else if (state === 'done') {
            badge.style.background = 'rgba(22, 163, 74, 0.15)';
            badge.style.color = '#4ade80';
        } else if (state === 'error' || state === 'stopped') {
            badge.style.background = 'rgba(220, 38, 38, 0.15)';
            badge.style.color = '#f87171';
        }
    }
}

async function checkInitialCrawlerStatus() {
    try {
        const res = await fetch('/api/performers/status');
        const data = await res.json();
        const sc = data.scraper || {};
        if (sc.state === 'running' || sc.state === 'paused') {
            showCrawlerTelemetry(true);
            updateCrawlerUI(sc.state, sc.message, sc.collected, sc.total);
            startCrawlerPolling();
        }
    } catch (e) {}
}

function startCrawlerPolling() {
    if (crawlerPollInterval) clearInterval(crawlerPollInterval);
    crawlerPollInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/performers/status');
            const data = await res.json();
            const sc = data.scraper || {};

            updateCrawlerUI(sc.state, sc.message, sc.collected, sc.total);

            if (sc.state === 'done' || sc.state === 'error' || sc.state === 'stopped') {
                clearInterval(crawlerPollInterval);
                crawlerPollInterval = null;
                loadDirectory(false);
            }
        } catch (e) {
            console.error("Crawler poll error", e);
        }
    }, 1200);
}

async function loadDirectory(append = false) {
    const grid = document.getElementById('directory-grid');
    const countEl = document.getElementById('dir-total-count');
    const photosEl = document.getElementById('dir-photos-count');
    const sentinelText = document.getElementById('dir-scroll-text');
    const sentinelEl = document.getElementById('dir-scroll-sentinel');
    const rangeEl = document.getElementById('dir-showing-range');
    const pageIndicator = document.getElementById('dir-page-indicator');
    const pageIndicatorTop = document.getElementById('dir-page-indicator-top');
    const btnPrev = document.getElementById('btn-page-prev');
    const btnNext = document.getElementById('btn-page-next');
    const btnPrevTop = document.getElementById('btn-page-prev-top');
    const btnNextTop = document.getElementById('btn-page-next-top');
    const btnFirst = document.getElementById('btn-page-first');

    if (!grid) return;

    dirLoading = true;

    const q = document.getElementById('dir-search-input')?.value.trim() || '';
    const category = document.getElementById('dir-category-select')?.value || '';
    const country = document.getElementById('dir-country-select')?.value || '';
    const ageMin = document.getElementById('dir-age-min')?.value || '';
    const ageMax = document.getElementById('dir-age-max')?.value || '';
    const sort = document.getElementById('dir-sort-select')?.value || 'has_photo';
    const hasPhoto = document.getElementById('dir-has-photo-cb')?.checked ? 'true' : '';

    if (!append) {
        grid.innerHTML = '<div style="color:var(--text-secondary);padding:36px;text-align:center;"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-500"></i>Loading directory records...</div>';
        renderIcons();
    }

    try {
        let url = `/api/performers/browse?q=${encodeURIComponent(q)}&sort=${sort}&limit=${dirLimit}&offset=${dirOffset}`;
        if (category) url += `&category=${encodeURIComponent(category)}`;
        if (country) url += `&country=${encodeURIComponent(country)}`;
        if (ageMin) url += `&age_min=${encodeURIComponent(ageMin)}`;
        if (ageMax) url += `&age_max=${encodeURIComponent(ageMax)}`;
        if (hasPhoto) url += `&has_photo=true`;

        const res = await fetch(url);
        const data = await res.json();

        dirTotal = data.total || 0;
        const currentBatch = data.results || [];

        if (countEl) countEl.textContent = `${dirTotal.toLocaleString()} performers indexed`;
        if (photosEl) photosEl.textContent = `${(data.photos_total || 0).toLocaleString()} with photos`;

        // Pagination calculation
        const currentPage = Math.floor(dirOffset / dirLimit) + 1;
        const totalPages = Math.max(1, Math.ceil(dirTotal / dirLimit));
        const showingStart = dirTotal > 0 ? (append ? 1 : dirOffset + 1) : 0;
        const showingEnd = Math.min(dirOffset + currentBatch.length, dirTotal);

        if (pageIndicator) pageIndicator.textContent = `Page ${currentPage} of ${totalPages}`;
        if (pageIndicatorTop) pageIndicatorTop.textContent = `Page ${currentPage} of ${totalPages}`;
        if (rangeEl) rangeEl.textContent = `Showing ${showingStart.toLocaleString()}–${showingEnd.toLocaleString()} of ${dirTotal.toLocaleString()} models`;

        // Enable/disable pagination buttons
        const isFirstPage = dirOffset === 0;
        const isLastPage = dirOffset + dirLimit >= dirTotal;

        if (btnFirst) btnFirst.disabled = isFirstPage;
        if (btnPrev) btnPrev.disabled = isFirstPage;
        if (btnPrevTop) btnPrevTop.disabled = isFirstPage;
        if (btnNext) btnNext.disabled = isLastPage;
        if (btnNextTop) btnNextTop.disabled = isLastPage;

        // Render Cards
        let html = '';
        currentBatch.forEach(r => {
            const imgSrc = r.photo ? `/performers/photo/${encodeURIComponent(r.photo)}` : '';
            const ageBadge = r.age ? `<span class="badge-tag age-tag">🎂 ${r.age} yrs</span>` : '<span class="badge-tag age-tag" style="opacity:0.65;">Age: --</span>';
            const countryBadge = r.country ? `<span class="badge-tag country-tag">📍 ${escapeHtml(r.country)}</span>` : '<span class="badge-tag country-tag" style="opacity:0.65;">📍 Global</span>';
            const catBadge = r.category ? `<span class="badge-tag category-tag">${escapeHtml(r.category)}</span>` : '';

            const pDataJson = escapeHtml(JSON.stringify(r));

            html += `
                <div class="visual-card performer-card" data-performer="${pDataJson}">
                    <div class="visual-card-thumb" onclick="openEntityModalFromCard(this)">
                        ${imgSrc ? `<img src="${imgSrc}" alt="${escapeHtml(r.name)}" loading="lazy">` : `
                            <div class="no-photo-box">
                                <i data-lucide="user" style="width:32px;height:32px;color:var(--text-dim);"></i>
                                <span style="font-size:11px;color:var(--text-muted);margin-top:4px;">No Photo</span>
                                <button class="btn-fetch-photo" onclick="event.stopPropagation(); fetchPerformerPhoto('${escapeHtml(r.name)}', this)">
                                    <i data-lucide="download-cloud" style="width:12px;height:12px;"></i> Get Photo
                                </button>
                            </div>
                        `}
                        ${r.category ? `<span class="card-cat-badge">${escapeHtml(r.category)}</span>` : ''}
                    </div>
                    <div class="visual-card-body" onclick="openEntityModalFromCard(this)">
                        <div class="visual-name" title="${escapeHtml(r.name)}">${escapeHtml(r.name)}</div>
                        <div class="performer-tags">
                            ${ageBadge}
                            ${countryBadge}
                        </div>
                        <div class="visual-meta">
                            <span>🎬 ${Number(r.videos || 0).toLocaleString()} videos produced</span>
                            ${r.gender ? `<span style="text-transform:capitalize;opacity:0.75;">${escapeHtml(r.gender)}</span>` : ''}
                        </div>
                    </div>
                </div>
            `;
        });

        if (append) {
            grid.innerHTML += html;
        } else {
            grid.innerHTML = html || '<div style="color:var(--text-secondary);padding:36px;text-align:center;">No records found matching your filters. Try adjusting search criteria.</div>';
        }

        // Sentinel display update
        if (sentinelEl) {
            if (isLastPage || currentBatch.length === 0) {
                sentinelEl.style.display = 'none';
            } else {
                sentinelEl.style.display = 'flex';
                if (sentinelText) sentinelText.innerHTML = '<i data-lucide="chevrons-down" class="w-3.5 h-3.5 animate-bounce"></i> Scroll down for more models...';
            }
        }

        renderIcons();
    } catch (err) {
        if (!append) grid.innerHTML = `<div style="color:var(--danger);padding:24px;">Failed to load directory: ${err.message}</div>`;
    } finally {
        dirLoading = false;
    }
}

async function fetchPerformerPhoto(name, btnEl) {
    if (!name || !btnEl) return;
    btnEl.innerHTML = 'Searching...';
    btnEl.disabled = true;

    try {
        const fd = new FormData();
        fd.append('name', name);
        const res = await fetch('/api/performers/fetch-photo', { method: 'POST', body: fd });
        const data = await res.json();

        if (data.photo) {
            btnEl.innerHTML = 'Saved!';
            setTimeout(() => { loadDirectory(false); }, 600);
        } else {
            btnEl.innerHTML = 'Not found';
            setTimeout(() => { btnEl.innerHTML = 'Get Photo'; btnEl.disabled = false; }, 2000);
        }
    } catch (e) {
        btnEl.innerHTML = 'Error';
    }
}

function openEntityModalFromCard(element) {
    const card = element.closest('.performer-card');
    if (!card) return;
    const rawData = card.getAttribute('data-performer');
    if (!rawData) return;
    try {
        const p = JSON.parse(rawData);
        const photoUrl = p.photo ? `/performers/photo/${encodeURIComponent(p.photo)}` : '';
        const metaInfo = `${Number(p.views || 0).toLocaleString()} views · ${p.videos || 0} videos${p.age ? ' · ' + p.age + ' yrs' : ''}${p.country ? ' · ' + p.country : ''}`;
        openEntityModal(p.name, photoUrl, metaInfo, p.url, p);
    } catch (e) {}
}

// ----------------------------------------------------------------------
// 7. Entity & Video Explorer Modal
// ----------------------------------------------------------------------
let currentPerformerName = '';
let currentAggregatorSource = 'all';

function initModal() {
    const backdrop = document.getElementById('entity-modal');
    const closeBtn = document.getElementById('btn-close-modal');
    const sourceSelect = document.getElementById('modal-aggregator-select');

    if (!backdrop || !closeBtn) return;

    closeBtn.addEventListener('click', () => {
        backdrop.style.display = 'none';
    });

    backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) {
            backdrop.style.display = 'none';
        }
    });

    // Handle Aggregator Selector change
    if (sourceSelect) {
        sourceSelect.addEventListener('change', () => {
            currentAggregatorSource = sourceSelect.value || 'all';
            if (currentPerformerName) {
                loadPerformerVideos(currentPerformerName, currentAggregatorSource);
            }
        });
    }

    // Modal tabs
    document.querySelectorAll('.modal-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.modaltab;
            document.querySelectorAll('.modal-tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('modal-tab-videos').style.display = tab === 'videos' ? 'block' : 'none';
            document.getElementById('modal-tab-details').style.display = tab === 'details' ? 'block' : 'none';
            renderIcons();
        });
    });
}

async function loadPerformerVideos(name, source = 'all') {
    const videoGrid = document.getElementById('modal-video-grid');
    const countBadge = document.getElementById('modal-video-count-badge');
    const sourceSelect = document.getElementById('modal-aggregator-select');

    if (!videoGrid || !name) return;

    const sourceLabel = source === 'all' ? 'all major networks (HDThot, Eporner, Pornhub, RedTube, YouPorn, SpankBang)' : source;
    videoGrid.innerHTML = `<div style="color:var(--text-secondary);padding:36px;text-align:center;"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2 text-emerald-500"></i>Harvesting video streams from ${escapeHtml(sourceLabel)}...</div>`;
    if (countBadge) countBadge.textContent = 'Searching...';
    renderIcons();

    try {
        const url = `/api/videos?q=${encodeURIComponent(name)}&source=${encodeURIComponent(source)}&limit=48`;
        const res = await fetch(url);
        const data = await res.json();

        currentModalVideos = data.videos || [];

        if (countBadge) {
            countBadge.textContent = `${currentModalVideos.length} videos`;
        }

        if (currentModalVideos.length === 0) {
            videoGrid.innerHTML = `
                <div style="color:var(--text-secondary);padding:40px;text-align:center;grid-column: 1 / -1;">
                    <i data-lucide="video-off" class="w-8 h-8 mx-auto mb-2 text-zinc-400 opacity-60"></i>
                    No direct video scenes found on ${escapeHtml(source === 'all' ? 'aggregated tube networks' : source)} for "${escapeHtml(name)}".
                    <div class="mt-3">
                        <button onclick="document.getElementById('modal-aggregator-select').value='all'; loadPerformerVideos('${escapeHtml(name)}', 'all');" class="btn-primary text-xs py-1 px-3">
                            Search All Aggregators
                        </button>
                    </div>
                </div>
            `;
            renderIcons();
            return;
        }

        let html = '';
        currentModalVideos.forEach((v, idx) => {
            html += `
                <div class="video-card cursor-pointer group" onclick="playModalVideoByIndex(${idx})">
                    <div class="video-thumb-wrap relative">
                        <img src="${v.thumbnail}" alt="${escapeHtml(v.title)}" loading="lazy" onerror="this.src='/static/placeholder-video.png'">
                        <div class="video-play-overlay">
                            <div class="video-play-btn">
                                <i data-lucide="play" class="w-5 h-5 fill-white text-white"></i>
                            </div>
                        </div>
                        ${v.duration ? `<span class="video-duration">${escapeHtml(v.duration)}</span>` : ''}
                        ${v.site ? `<span class="video-site-badge font-semibold">${escapeHtml(v.site)}</span>` : ''}
                    </div>
                    <div class="video-card-body">
                        <div class="video-title" title="${escapeHtml(v.title)}">${escapeHtml(v.title)}</div>
                        <div class="video-meta">
                            <span>${typeof v.views === 'number' ? Number(v.views).toLocaleString() + ' views' : v.views}</span>
                            <span class="flex items-center gap-1 text-emerald-500 font-medium">
                                <i data-lucide="play" class="w-3 h-3"></i> Ad-Free
                            </span>
                        </div>
                    </div>
                </div>
            `;
        });
        videoGrid.innerHTML = html;
        renderIcons();

    } catch (err) {
        videoGrid.innerHTML = `<div style="color:var(--danger);padding:24px;">Failed to load video streams: ${err.message}</div>`;
        if (countBadge) countBadge.textContent = 'Error';
    }
}

async function openEntityModal(name, photoUrl, metaInfo, externalUrl, fullRecord = {}) {
    const modal = document.getElementById('entity-modal');
    const titleEl = document.getElementById('modal-title');
    const subtitleEl = document.getElementById('modal-subtitle');
    const imgEl = document.getElementById('modal-performer-img');
    const profileInfo = document.getElementById('modal-profile-info');
    const sourceSelect = document.getElementById('modal-aggregator-select');

    if (!modal) return;

    currentPerformerName = name;
    if (sourceSelect) {
        sourceSelect.value = currentAggregatorSource || 'all';
    }

    titleEl.textContent = name;
    subtitleEl.textContent = metaInfo;

    if (photoUrl) {
        imgEl.src = photoUrl;
        imgEl.style.display = 'block';
    } else {
        imgEl.style.display = 'none';
    }

    const ageStr = fullRecord.age ? `${fullRecord.age} years old` : 'Unknown / Unspecified';
    const countryStr = fullRecord.country ? fullRecord.country : 'Unknown / Worldwide';
    const catStr = fullRecord.category ? fullRecord.category : 'Adult Star / Creator';
    const ofLink = fullRecord.onlyfans_url ? `<a href="${fullRecord.onlyfans_url}" target="_blank" rel="noopener noreferrer" style="color:var(--cyan);font-weight:500;">OnlyFans Profile ↗</a>` : 'Not linked';

    profileInfo.innerHTML = `
        <div style="display:flex;flex-direction:column;gap:12px;background:var(--bg-surface);padding:18px;border-radius:var(--radius-md);border:1px solid var(--border-medium);">
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:14px;">
                <div><span style="color:var(--text-muted);font-size:12px;">Performer Name</span><div style="color:var(--text-primary);font-weight:600;font-size:15px;">${escapeHtml(name)}</div></div>
                <div><span style="color:var(--text-muted);font-size:12px;">Category</span><div style="color:var(--primary);font-weight:500;">${escapeHtml(catStr)}</div></div>
                <div><span style="color:var(--text-muted);font-size:12px;">Age</span><div style="color:var(--text-primary);font-weight:600;">🎂 ${escapeHtml(ageStr)}</div></div>
                <div><span style="color:var(--text-muted);font-size:12px;">Country / Origin</span><div style="color:var(--text-primary);font-weight:600;">📍 ${escapeHtml(countryStr)}</div></div>
                <div><span style="color:var(--text-muted);font-size:12px;">Videos Produced</span><div style="color:var(--text-primary);font-family:var(--font-mono);font-weight:600;">🎬 ${fullRecord.videos || 0} videos</div></div>
                <div><span style="color:var(--text-muted);font-size:12px;">Gender</span><div style="color:var(--text-primary);text-transform:capitalize;">${escapeHtml(fullRecord.gender || 'Female')}</div></div>
            </div>
            <div style="border-top:1px solid var(--border-light);padding-top:12px;display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;">
                ${fullRecord.onlyfans_url ? `<div><strong>OnlyFans:</strong> ${ofLink}</div>` : ''}
                ${externalUrl ? `<div><strong>Source Profile:</strong> <a href="${externalUrl}" target="_blank" rel="noopener noreferrer">View Web Profile ↗</a></div>` : ''}
            </div>
        </div>
    `;

    modal.style.display = 'flex';
    renderIcons();

    // Query videos with current aggregator source
    loadPerformerVideos(name, currentAggregatorSource || 'all');
}

let currentModalVideos = [];
let currentCinemaUrl = '';
let currentCinemaInfo = null;
let downloadPollInterval = null;
let hlsInstance = null;

function playModalVideoByIndex(index) {
    const v = currentModalVideos[index];
    if (!v) return;
    openCinemaPlayer(v.url, v.title, v.site, v.thumbnail);
}

// ----------------------------------------------------------------------
// 8. Ad-Free Cinema Video Player & Direct PC Downloader
// ----------------------------------------------------------------------
function initCinemaPlayer() {
    const modal = document.getElementById('cinema-modal');
    const closeBtn = document.getElementById('btn-close-cinema');
    const video = document.getElementById('cinema-video-player');
    const qualitySelect = document.getElementById('cinema-quality-select');
    const speedSelect = document.getElementById('cinema-speed-select');
    const downloadBtn = document.getElementById('btn-cinema-download');
    const downloadQuality = document.getElementById('cinema-download-quality');
    const retryBtn = document.getElementById('btn-cinema-retry');

    if (!modal) return;

    function closeCinema() {
        modal.style.display = 'none';
        if (hlsInstance) {
            hlsInstance.destroy();
            hlsInstance = null;
        }
        if (video) {
            video.pause();
            video.removeAttribute('src');
            video.load();
        }
        const iframe = document.getElementById('cinema-iframe-player');
        if (iframe) {
            iframe.src = 'about:blank';
            iframe.style.display = 'none';
        }
        if (downloadPollInterval) {
            clearInterval(downloadPollInterval);
            downloadPollInterval = null;
        }
    }

    if (closeBtn) closeBtn.addEventListener('click', closeCinema);

    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeCinema();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.style.display !== 'none') {
            closeCinema();
        }
    });

    // Handle speed select
    if (speedSelect && video) {
        speedSelect.addEventListener('change', () => {
            const speed = parseFloat(speedSelect.value) || 1.0;
            video.playbackRate = speed;
        });
    }

    // Handle quality change during playback
    if (qualitySelect && video) {
        qualitySelect.addEventListener('change', () => {
            const selectedUrl = qualitySelect.value;
            if (!selectedUrl) return;
            const currentTime = video.currentTime;
            const wasPlaying = !video.paused;
            const currentSpeed = speedSelect ? (parseFloat(speedSelect.value) || 1.0) : 1.0;

            const isHls = selectedUrl.includes('.m3u8') || (currentCinemaInfo && currentCinemaInfo.is_hls);
            playStreamSource(selectedUrl, isHls, currentTime, wasPlaying, currentSpeed);
        });
    }

    // Handle PC Download initiation (8-part parallel downloader)
    if (downloadBtn) {
        downloadBtn.addEventListener('click', async () => {
            if (!currentCinemaUrl) return;
            const formatId = downloadQuality ? downloadQuality.value : 'best';
            const title = document.getElementById('cinema-title')?.textContent || '';

            downloadBtn.disabled = true;
            downloadBtn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Starting 8x Download...</span>';
            renderIcons();

            const panel = document.getElementById('cinema-download-panel');
            if (panel) panel.style.display = 'flex';

            const statusText = document.getElementById('cinema-dl-status-text');
            if (statusText) statusText.textContent = 'Connecting 8 parallel streams to PC Downloads folder...';

            try {
                const fd = new FormData();
                fd.append('url', currentCinemaUrl);
                fd.append('format_id', formatId);
                fd.append('title', title);

                const res = await fetch('/api/media/download', {
                    method: 'POST',
                    body: fd,
                });
                const data = await res.json();

                if (data.task_id) {
                    currentDownloadTaskId = data.task_id;
                    startDownloadPolling(data.task_id);
                    // Also trigger drawer refresh
                    pollDownloadsList();
                } else {
                    if (statusText) statusText.textContent = data.error || 'Failed to start download';
                    downloadBtn.disabled = false;
                    downloadBtn.innerHTML = '<i data-lucide="download" class="w-4 h-4"></i><span>Download to PC</span>';
                    renderIcons();
                }
            } catch (err) {
                if (statusText) statusText.textContent = `Download error: ${err.message}`;
                downloadBtn.disabled = false;
                downloadBtn.innerHTML = '<i data-lucide="download" class="w-4 h-4"></i><span>Download to PC</span>';
                renderIcons();
            }
        });
    }

    if (retryBtn) {
        retryBtn.addEventListener('click', () => {
            if (currentCinemaUrl) {
                const title = document.getElementById('cinema-title')?.textContent || 'Video';
                const site = document.getElementById('cinema-site-badge')?.textContent || 'Stream';
                openCinemaPlayer(currentCinemaUrl, title, site);
            }
        });
    }
}

function playStreamSource(streamUrl, isHls, startTime = 0, shouldPlay = true, speed = 1.0) {
    const video = document.getElementById('cinema-video-player');
    if (!video || !streamUrl) return;

    if (hlsInstance) {
        hlsInstance.destroy();
        hlsInstance = null;
    }

    if (isHls && window.Hls && Hls.isSupported()) {
        hlsInstance = new Hls({
            enableWorker: true,
            lowLatencyMode: false,          // Disable low-latency mode — causes re-fetching on VOD
            maxBufferLength: 60,             // Buffer 60 seconds ahead
            maxMaxBufferLength: 120,         // Allow up to 120 seconds of max buffer
            maxBufferSize: 60 * 1000 * 1000, // 60 MB buffer cap
            maxBufferHole: 0.25,             // Tolerate larger discontinuities
            startLevel: -1,                  // Auto start level (ABR)
            abrEwmaDefaultEstimate: 10000000, // Assume 10 Mbps by default (avoids starting at 360p)
            nudgeMaxRetry: 10,
            maxFragLookUpTolerance: 0.5,
        });
        hlsInstance.loadSource(streamUrl);
        hlsInstance.attachMedia(video);
        hlsInstance.on(Hls.Events.MANIFEST_PARSED, () => {
            if (startTime > 0) video.currentTime = startTime;
            video.playbackRate = speed;
            if (shouldPlay) video.play().catch(() => {});
        });
        hlsInstance.on(Hls.Events.ERROR, (event, data) => {
            if (data.fatal) {
                console.warn('HLS fatal error, attempting recovery:', data);
                switch (data.type) {
                    case Hls.ErrorTypes.NETWORK_ERROR:
                        hlsInstance.startLoad();
                        break;
                    case Hls.ErrorTypes.MEDIA_ERROR:
                        hlsInstance.recoverMediaError();
                        break;
                    default:
                        hlsInstance.destroy();
                        hlsInstance = null;
                        video.src = streamUrl;
                        if (shouldPlay) video.play().catch(() => {});
                        break;
                }
            }
        });
    } else {
        video.src = streamUrl;
        if (startTime > 0) video.currentTime = startTime;
        video.playbackRate = speed;
        if (shouldPlay) video.play().catch(() => {});
    }
}

function startDownloadPolling(taskId) {
    currentDownloadTaskId = taskId;
    if (downloadPollInterval) clearInterval(downloadPollInterval);

    const filenameEl = document.getElementById('cinema-dl-filename');
    const speedEl = document.getElementById('cinema-dl-speed');
    const etaEl = document.getElementById('cinema-dl-eta');
    const percentEl = document.getElementById('cinema-dl-percent');
    const barFill = document.getElementById('cinema-dl-bar-fill');
    const statusText = document.getElementById('cinema-dl-status-text');
    const downloadBtn = document.getElementById('btn-cinema-download');

    downloadPollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/media/download-status?task_id=${encodeURIComponent(taskId)}`);
            if (!res.ok) return;
            const data = await res.json();

            if (filenameEl && data.filename) filenameEl.textContent = data.filename;
            if (speedEl) speedEl.textContent = data.speed_str || '0 MB/s';
            if (etaEl) etaEl.textContent = data.eta_str ? `ETA: ${data.eta_str}` : 'ETA: --';
            if (percentEl) percentEl.textContent = `${data.percent || 0}%`;
            if (barFill) barFill.style.width = `${data.percent || 0}%`;

            if (data.state === 'finished' || data.state === 'completed') {
                clearInterval(downloadPollInterval);
                downloadPollInterval = null;
                if (statusText) statusText.innerHTML = '🎉 <strong class="text-emerald-500 font-semibold">Saved to PC Downloads folder!</strong>';
                if (downloadBtn) {
                    downloadBtn.disabled = false;
                    downloadBtn.innerHTML = '<i data-lucide="check-circle" class="w-4 h-4 text-emerald-300"></i><span>Downloaded</span>';
                    renderIcons();
                }
                pollDownloadsList();
            } else if (data.state === 'error') {
                clearInterval(downloadPollInterval);
                downloadPollInterval = null;
                if (statusText) statusText.textContent = `Error: ${data.error || 'Download failed'}`;
                if (downloadBtn) {
                    downloadBtn.disabled = false;
                    downloadBtn.innerHTML = '<i data-lucide="alert-circle" class="w-4 h-4"></i><span>Retry Download</span>';
                    renderIcons();
                }
                pollDownloadsList();
            } else {
                if (statusText) statusText.textContent = `8-part downloading (${data.downloaded_bytes ? (data.downloaded_bytes / (1024*1024)).toFixed(1) + ' MB' : ''})...`;
                // Show pause button while downloading
                const pauseBtn = document.getElementById('btn-cinema-dl-pause');
                const resumeBtn = document.getElementById('btn-cinema-dl-resume');
                if (data.state === 'paused') {
                    if (pauseBtn) pauseBtn.classList.add('hidden');
                    if (resumeBtn) resumeBtn.classList.remove('hidden');
                    if (statusText) statusText.textContent = `⏸ Paused at ${data.percent || 0}%`;
                } else if (data.state === 'downloading') {
                    if (pauseBtn) pauseBtn.classList.remove('hidden');
                    if (resumeBtn) resumeBtn.classList.add('hidden');
                }
            }
        } catch (e) {
            console.error('Download poll error', e);
        }
    }, 800);
}

async function cinemaDlPause() {
    if (!currentDownloadTaskId) return;
    const fd = new FormData();
    fd.append('task_id', currentDownloadTaskId);
    try {
        await fetch('/api/media/pause-download', { method: 'POST', body: fd });
    } catch (e) { console.error('Pause failed', e); }
}

async function cinemaDlResume() {
    if (!currentDownloadTaskId) return;
    const fd = new FormData();
    fd.append('task_id', currentDownloadTaskId);
    try {
        await fetch('/api/media/resume-download', { method: 'POST', body: fd });
        const pauseBtn = document.getElementById('btn-cinema-dl-pause');
        const resumeBtn = document.getElementById('btn-cinema-dl-resume');
        if (pauseBtn) pauseBtn.classList.remove('hidden');
        if (resumeBtn) resumeBtn.classList.add('hidden');
    } catch (e) { console.error('Resume failed', e); }
}

async function openCinemaPlayer(url, title, site, thumbnail = '') {
    currentCinemaUrl = url;
    const modal = document.getElementById('cinema-modal');
    const titleEl = document.getElementById('cinema-title');
    const siteBadge = document.getElementById('cinema-site-badge');
    const durationBadge = document.getElementById('cinema-duration-badge');
    const video = document.getElementById('cinema-video-player');
    const iframe = document.getElementById('cinema-iframe-player');
    const loadingOverlay = document.getElementById('cinema-loading-overlay');
    const errorOverlay = document.getElementById('cinema-error-overlay');
    const errorMsg = document.getElementById('cinema-error-msg');
    const fallbackLink = document.getElementById('cinema-error-fallback-link');
    const externalLink = document.getElementById('cinema-external-link');
    const qualitySelect = document.getElementById('cinema-quality-select');
    const speedSelect = document.getElementById('cinema-speed-select');
    const downloadQuality = document.getElementById('cinema-download-quality');
    const downloadPanel = document.getElementById('cinema-download-panel');
    const downloadBtn = document.getElementById('btn-cinema-download');

    if (!modal) return;

    modal.style.display = 'flex';
    if (titleEl) titleEl.textContent = title || 'Video Stream';
    if (siteBadge) siteBadge.textContent = site || 'Tube Network';
    if (durationBadge) durationBadge.style.display = 'none';
    if (externalLink) externalLink.href = url;
    if (fallbackLink) fallbackLink.href = url;
    if (downloadPanel) downloadPanel.style.display = 'none';
    if (speedSelect) speedSelect.value = '1.0';
    if (downloadBtn) {
        downloadBtn.disabled = false;
        downloadBtn.innerHTML = '<i data-lucide="download" class="w-4 h-4"></i><span>Download to PC</span>';
    }

    if (loadingOverlay) loadingOverlay.style.display = 'flex';
    if (errorOverlay) errorOverlay.style.display = 'none';

    if (iframe) {
        iframe.src = 'about:blank';
        iframe.style.display = 'none';
    }
    if (video) {
        video.style.display = 'block';
        video.pause();
        video.removeAttribute('src');
        if (thumbnail) video.poster = thumbnail;
    }

    renderIcons();

    try {
        const fd = new FormData();
        fd.append('url', url);

        const res = await fetch('/api/media/info', {
            method: 'POST',
            body: fd,
        });
        const data = await res.json();
        currentCinemaInfo = data;

        if (!data.success) {
            throw new Error(data.error || 'Direct video stream URL could not be resolved.');
        }

        if (titleEl && data.title && data.title !== 'Ad-Free Cinema Player') titleEl.textContent = data.title;
        if (siteBadge && data.site) siteBadge.textContent = data.site;
        if (durationBadge && data.duration_formatted) {
            durationBadge.textContent = `⏱ ${data.duration_formatted}`;
            durationBadge.style.display = 'inline-flex';
        }

        const hasDirectStream = data.stream_url || (data.qualities && data.qualities.length > 0);

        if (hasDirectStream) {
            if (iframe) iframe.style.display = 'none';
            if (video) video.style.display = 'block';

            // Populate Playback Qualities dropdown
            if (qualitySelect) {
                qualitySelect.innerHTML = '';
                if (data.qualities && data.qualities.length > 0) {
                    data.qualities.forEach((q, idx) => {
                        const opt = document.createElement('option');
                        opt.value = q.url;
                        opt.textContent = `${q.label}${q.filesize_mb ? ` (~${q.filesize_mb} MB)` : ''}`;
                        if (idx === 0) opt.selected = true;
                        qualitySelect.appendChild(opt);
                    });
                } else if (data.stream_url) {
                    const opt = document.createElement('option');
                    opt.value = data.stream_url;
                    opt.textContent = 'Auto / Direct Stream';
                    opt.selected = true;
                    qualitySelect.appendChild(opt);
                }
            }

            // Play stream via direct MP4 or HLS
            const initialStream = (data.qualities && data.qualities.length > 0) ? data.qualities[0].url : data.stream_url;
            const isHls = Boolean(data.is_hls || (initialStream && initialStream.includes('.m3u8')));
            playStreamSource(initialStream, isHls, 0, true, 1.0);

        } else if (data.embed_url) {
            if (video) {
                video.style.display = 'none';
                video.pause();
                video.removeAttribute('src');
            }
            if (iframe) {
                iframe.src = data.embed_url;
                iframe.style.display = 'block';
            }
            if (qualitySelect) {
                qualitySelect.innerHTML = '<option value="">High Definition Auto</option>';
            }
        }

        // Populate Download Qualities dropdown
        if (downloadQuality) {
            downloadQuality.innerHTML = '';
            if (data.qualities && data.qualities.length > 0) {
                data.qualities.forEach((q, idx) => {
                    const opt = document.createElement('option');
                    opt.value = q.format_id || 'best';
                    opt.textContent = `${q.label}${q.filesize_mb ? ` (${q.filesize_mb} MB)` : ''}`;
                    if (idx === 0) opt.selected = true;
                    downloadQuality.appendChild(opt);
                });
            }
            const bestOpt = document.createElement('option');
            bestOpt.value = 'best';
            bestOpt.textContent = 'Best Available Resolution (1080p/720p 8x)';
            downloadQuality.appendChild(bestOpt);
        }

        if (loadingOverlay) loadingOverlay.style.display = 'none';

    } catch (err) {
        if (loadingOverlay) loadingOverlay.style.display = 'none';
        if (errorOverlay) {
            errorOverlay.style.display = 'flex';
            if (errorMsg) errorMsg.textContent = err.message || 'Stream extraction failed.';
        }
    } finally {
        renderIcons();
    }
}

// // ----------------------------------------------------------------------
// 9. Global Downloads Manager Drawer & 8-Part Parallel Telemetry
// ----------------------------------------------------------------------
let drawerPollInterval = null;
let _dlActiveTab = 'active'; // 'active' | 'done'

function switchDlTab(tab) {
    _dlActiveTab = tab;
    const activeBtn = document.getElementById('dl-tab-active');
    const doneBtn = document.getElementById('dl-tab-done');
    const activeCls = 'border-b-2 border-emerald-500 text-emerald-600 dark:text-emerald-400 font-semibold';
    const inactiveCls = 'border-b-2 border-transparent text-zinc-500 dark:text-zinc-400 font-medium';
    if (activeBtn) activeBtn.className = `flex-1 py-2.5 text-xs text-center transition-all ${tab === 'active' ? activeCls : inactiveCls}`;
    if (doneBtn) doneBtn.className = `flex-1 py-2.5 text-xs text-center transition-all ${tab === 'done' ? activeCls : inactiveCls}`;
    pollDownloadsList();
}

function initDownloadsDrawer() {
    const triggerBtn = document.getElementById('btn-open-downloads');
    const drawer = document.getElementById('downloads-drawer');
    const backdrop = document.getElementById('downloads-drawer-backdrop');
    const closeBtn = document.getElementById('btn-close-downloads-drawer');
    const openFolderBtn = document.getElementById('btn-open-downloads-folder');
    const clearBtn = document.getElementById('btn-clear-downloads-history');

    if (!drawer) return;

    function openDrawer() {
        drawer.style.display = 'flex';
        if (backdrop) backdrop.style.display = 'block';
        loadDrawerFolderPath();
        pollDownloadsList();
        if (!drawerPollInterval) {
            drawerPollInterval = setInterval(pollDownloadsList, 1500);
        }
    }

    function closeDrawer() {
        drawer.style.display = 'none';
        if (backdrop) backdrop.style.display = 'none';
        if (drawerPollInterval) {
            clearInterval(drawerPollInterval);
            drawerPollInterval = null;
        }
    }

    if (triggerBtn) triggerBtn.addEventListener('click', openDrawer);
    if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
    if (backdrop) backdrop.addEventListener('click', closeDrawer);

    if (openFolderBtn) {
        openFolderBtn.addEventListener('click', async () => {
            try {
                await fetch('/api/media/open-folder', { method: 'POST' });
            } catch (e) {
                console.error('Failed to open downloads folder', e);
            }
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', async () => {
            try {
                await fetch('/api/media/clear-completed', { method: 'POST' });
                pollDownloadsList();
            } catch (e) {
                console.error('Failed to clear completed downloads', e);
            }
        });
    }

    // Start passive badge polling every 4 seconds
    pollDownloadsList();
    setInterval(pollDownloadsList, 4000);
}

// ----------------------------------------------------------------------
// Deep Research Live Process Monitor & In-Page Result Streamer
// ----------------------------------------------------------------------
function initDeepResearch() {
    const form = document.getElementById('deep-research-form');
    const workspace = document.getElementById('deep-research-workspace');
    const processLog = document.getElementById('deep-process-log');
    const processStatus = document.getElementById('deep-process-status');
    const processPulse = document.getElementById('deep-process-pulse');
    const resultsContainer = document.getElementById('deep-response');
    const resultsCount = document.getElementById('deep-results-count');

    if (!form) return;

    let activeEventSource = null;
    let discoveredUrls = [];
    let extractedFindings = [];
    let discoveredImages = [];

    function addProcessLog(msg, type = 'info') {
        if (!processLog) return;
        const colors = {
            'info':    'text-zinc-600 dark:text-zinc-300',
            'step':    'text-indigo-600 dark:text-indigo-400 font-semibold',
            'found':   'text-emerald-600 dark:text-emerald-400',
            'warn':    'text-amber-600 dark:text-amber-400',
            'done':    'text-emerald-500 dark:text-emerald-400 font-bold',
            'error':   'text-rose-600 dark:text-rose-400',
        };
        const cls = colors[type] || colors.info;
        const ts = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const line = document.createElement('div');
        line.className = `flex gap-2 text-[11px] font-mono py-0.5 border-b border-zinc-100 dark:border-white/[0.04]`;
        line.innerHTML = `<span class="text-zinc-400 shrink-0">${ts}</span><span class="${cls}">${escapeHtml(msg)}</span>`;
        processLog.insertBefore(line, processLog.firstChild);
        while (processLog.children.length > 100) {
            processLog.removeChild(processLog.lastChild);
        }
    }

    function renderFindingsFeed() {
        if (!resultsContainer) return;
        let html = '';

        // 1. Images Gallery if any
        if (discoveredImages.length > 0) {
            html += `
                <div class="mb-4">
                    <div class="text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">Discovered Visual Intelligence (${discoveredImages.length})</div>
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        ${discoveredImages.slice(0, 8).map(img => `
                            <div class="rounded-xl overflow-hidden border border-zinc-200 dark:border-white/10 bg-black/40 aspect-video relative group">
                                <img src="${escapeHtml(img.url || img.thumb || '')}" alt="${escapeHtml(img.title || '')}" class="w-full h-full object-cover" onerror="this.src='/static/placeholder-video.png'">
                                <div class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity p-2 flex flex-col justify-end text-[10px] text-white">
                                    <span class="truncate font-semibold">${escapeHtml(img.title || 'Image')}</span>
                                    <span class="text-zinc-300 font-mono">${escapeHtml(img.source_engine || '')}</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        // 2. Key Findings Cards
        if (extractedFindings.length > 0) {
            html += `
                <div class="mb-4">
                    <div class="text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">Key Extracted Findings (${extractedFindings.length})</div>
                    <div class="space-y-2.5">
                        ${extractedFindings.map(f => {
                            const conf = f.confidence ? Math.round(f.confidence * 100) : 85;
                            return `
                                <div class="p-3.5 rounded-xl bg-white dark:bg-zinc-900/80 border border-zinc-200 dark:border-white/10 shadow-xs">
                                    <div class="flex items-center justify-between gap-2 mb-1.5">
                                        <span class="text-xs font-bold text-indigo-600 dark:text-indigo-400">${escapeHtml(f.topic || 'Analysis')}</span>
                                        <span class="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full ${conf >= 80 ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800' : 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-400'}">${conf}% Confidence</span>
                                    </div>
                                    <p class="text-xs text-zinc-700 dark:text-zinc-300 leading-relaxed">${escapeHtml(f.content || '')}</p>
                                    ${f.source_url ? `
                                        <div class="mt-2 pt-2 border-t border-zinc-100 dark:border-white/[0.04] flex items-center justify-between">
                                            <a href="${escapeHtml(f.source_url)}" target="_blank" rel="noopener noreferrer" class="text-[11px] font-mono text-zinc-500 hover:text-indigo-500 dark:hover:text-indigo-400 truncate max-w-[85%]">
                                                ↗ ${escapeHtml(f.source_title || f.source_url)}
                                            </a>
                                            <span class="text-[10px] font-mono bg-zinc-100 dark:bg-white/[0.06] text-zinc-600 dark:text-zinc-400 px-1.5 py-0.2 rounded">${escapeHtml(f.source_type || 'web')}</span>
                                        </div>
                                    ` : ''}
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }

        // 3. Discovered URLs / Sources
        if (discoveredUrls.length > 0) {
            html += `
                <div class="mb-4">
                    <div class="text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">Crawled & Discovered Sources (${discoveredUrls.length})</div>
                    <div class="results-grid">
                        ${discoveredUrls.map(u => {
                            const isDark = (u.url || '').includes('.onion');
                            const tagClass = isDark ? 'source-tag darkweb' : 'source-tag clearnet';
                            const tagLabel = isDark ? '🧅 Onion / Darknet' : (u.source_engine || 'Web');
                            return `
                                <div class="result-card">
                                    <div class="result-card-header">
                                        <span class="${tagClass}">${tagLabel}</span>
                                    </div>
                                    <a href="${escapeHtml(u.url)}" target="_blank" rel="noopener noreferrer" class="result-title">${escapeHtml(u.title || u.url)}</a>
                                    ${u.snippet || u.text ? `<p class="result-snippet">${escapeHtml((u.snippet || u.text).slice(0, 200))}</p>` : ''}
                                    <div class="result-url" title="${escapeHtml(u.url)}">${escapeHtml(u.url)}</div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }

        if (discoveredUrls.length === 0 && extractedFindings.length === 0 && discoveredImages.length === 0) {
            html = `<div class="glass-card" style="text-align:center;color:var(--text-secondary);padding:30px;"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-500"></i>Initializing search agents and dispatching multi-engine crawl...</div>`;
        }

        resultsContainer.innerHTML = html;
        if (resultsCount) {
            const total = extractedFindings.length + discoveredUrls.length;
            resultsCount.textContent = `${total} findings`;
        }
        renderIcons();
    }

    // Sub-view toggle buttons
    const btnViewFeed = document.getElementById('btn-deep-view-feed');
    const btnViewLinks = document.getElementById('btn-deep-view-links');
    const btnViewHistory = document.getElementById('btn-deep-view-history');
    const btnClearResults = document.getElementById('btn-clear-deep-results');
    const deepLinksCountBadge = document.getElementById('deep-links-count-badge');

    let deepActiveView = 'feed'; // 'feed' | 'links' | 'history'

    function setDeepSubViewBtnState(view) {
        deepActiveView = view;
        const btns = [
            { id: btnViewFeed, key: 'feed' },
            { id: btnViewLinks, key: 'links' },
            { id: btnViewHistory, key: 'history' }
        ];
        btns.forEach(b => {
            if (b.id) {
                if (b.key === view) {
                    b.id.className = 'px-2.5 py-1 rounded-lg font-semibold bg-white dark:bg-zinc-800 text-zinc-900 dark:text-white shadow-xs transition-all flex items-center gap-1.5';
                } else {
                    b.id.className = 'px-2.5 py-1 rounded-lg font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white transition-all flex items-center gap-1.5';
                }
            }
        });
    }

    if (btnViewFeed) {
        btnViewFeed.addEventListener('click', () => {
            setDeepSubViewBtnState('feed');
            renderFindingsFeed();
        });
    }

    if (btnViewLinks) {
        btnViewLinks.addEventListener('click', () => {
            setDeepSubViewBtnState('links');
            const q = document.getElementById('deep-query')?.value || 'DeepResearch';
            renderLinksTable(discoveredUrls, resultsContainer, q);
        });
    }

    if (btnViewHistory) {
        btnViewHistory.addEventListener('click', () => {
            setDeepSubViewBtnState('history');
            renderHistorySection(resultsContainer, (item) => {
                const deepInput = document.getElementById('deep-query');
                if (deepInput) deepInput.value = item.query;
                form.dispatchEvent(new Event('submit'));
            });
        });
    }

    if (btnClearResults) {
        btnClearResults.addEventListener('click', () => {
            discoveredUrls = [];
            extractedFindings = [];
            discoveredImages = [];
            if (workspace) workspace.classList.add('hidden');
            resultsContainer.innerHTML = '';
            localStorage.removeItem('north_active_deep_search');
            if (resultsCount) resultsCount.textContent = '0 findings';
            if (deepLinksCountBadge) deepLinksCountBadge.textContent = '0';
        });
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = (document.getElementById('deep-query')?.value || '').trim();
        if (!query) return;

        if (activeEventSource) {
            activeEventSource.close();
            activeEventSource = null;
        }

        discoveredUrls = [];
        extractedFindings = [];
        discoveredImages = [];

        setDeepSubViewBtnState('feed');

        // Collect selected engines
        const engines = [];
        document.querySelectorAll('#deep-providers-list .engine-toggle.active').forEach(btn => {
            if (btn.dataset.engine) engines.push(btn.dataset.engine);
        });
        if (engines.length === 0) {
            engines.push('duckduckgo', 'bing', 'knowledge');
        }

        const darkwebMode = document.getElementById('deep-darkweb-mode-input')?.value || 'normal';
        const darkweb = (darkwebMode === 'darknet_only' || darkwebMode === 'all');
        const targetSite = document.getElementById('deep-target-site')?.value.trim() || '';
        const mustInclude = document.getElementById('deep-must-include')?.value.trim() || '';
        const mustExclude = document.getElementById('deep-must-exclude')?.value.trim() || '';

        const maxSources = parseInt(document.getElementById('input-max-sources')?.value || '10', 10);
        const maxSubQueries = parseInt(document.getElementById('input-sub-queries')?.value || '3', 10);
        const model = document.getElementById('ai-model')?.value || 'dolphin3:8b';

        // Reveal workspace
        if (workspace) workspace.classList.remove('hidden');
        if (processLog) processLog.innerHTML = '';
        if (processStatus) {
            processStatus.textContent = 'Active Dispatch...';
            processStatus.className = 'text-[10px] font-mono bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 px-2 py-0.5 rounded-full border border-indigo-200 dark:border-indigo-800/60';
        }
        if (processPulse) processPulse.classList.add('animate-ping');

        const modeStr = darkwebMode === 'darknet_only' ? '🧅 Only Darknet (Tor)' : (darkwebMode === 'all' ? '🌐 Hybrid (Clearnet + Tor)' : '🛡️ Normal Web');
        addProcessLog(`Initiating deep intelligence synthesis: "${query}"`, 'step');
        addProcessLog(`Mode: ${modeStr} | Engines: ${engines.join(', ')} | Model: ${model}`, 'info');

        renderFindingsFeed();

        const fd = new FormData();
        fd.append('query', query);
        fd.append('engines', engines.join(','));
        fd.append('darkweb', darkweb);
        fd.append('darkweb_mode', darkwebMode);
        fd.append('target_site', targetSite);
        fd.append('must_include', mustInclude);
        fd.append('must_exclude', mustExclude);
        fd.append('max_sources', maxSources);
        fd.append('max_sub_queries', maxSubQueries);
        fd.append('model', model);
        fd.append('mode', 'research');

        try {
            const res = await fetch('/api/research', { method: 'POST', body: fd });
            const data = await res.json();

            if (data.error) {
                if (processStatus) processStatus.textContent = 'Error';
                addProcessLog(`Dispatch error: ${data.error}`, 'error');
                resultsContainer.innerHTML = `<div class="glass-card" style="color:var(--danger);padding:20px;">${escapeHtml(data.error)}</div>`;
                return;
            }

            const jobId = data.job_id;
            addProcessLog(`Job spawned [${jobId}]. Subscribing to live SSE telemetry...`, 'info');

            activeEventSource = new EventSource(`/api/jobs/${jobId}/stream`);

            activeEventSource.onmessage = (event) => {
                try {
                    const evt = JSON.parse(event.data);
                    const type = evt.type || 'status';

                    if (type === 'sub_queries') {
                        const qList = evt.queries || [];
                        addProcessLog(`Generated ${qList.length} sub-queries: ${qList.join(' · ')}`, 'step');
                    } else if (type === 'search_results' || type === 'url') {
                        const urls = evt.urls || (evt.url ? [evt] : []);
                        urls.forEach(u => {
                            const uObj = typeof u === 'string' ? { url: u, title: u } : u;
                            if (!discoveredUrls.some(x => x.url === uObj.url)) {
                                discoveredUrls.push(uObj);
                                addProcessLog(`Discovered target: ${uObj.title || uObj.url}`, 'found');
                            }
                        });
                        if (deepLinksCountBadge) deepLinksCountBadge.textContent = `${discoveredUrls.length}`;
                        if (deepActiveView === 'feed') renderFindingsFeed();
                        else if (deepActiveView === 'links') renderLinksTable(discoveredUrls, resultsContainer, query);
                    } else if (type === 'scrape') {
                        addProcessLog(`Crawling content: ${evt.title || evt.url}`, 'info');
                    } else if (type === 'finding') {
                        extractedFindings.unshift(evt);
                        addProcessLog(`Extracted finding: [${evt.topic || 'Intel'}] ${(evt.content||'').slice(0, 60)}...`, 'found');
                        if (deepActiveView === 'feed') renderFindingsFeed();
                    } else if (type === 'image') {
                        discoveredImages.push(evt);
                        if (deepActiveView === 'feed') renderFindingsFeed();
                    } else if (type === 'log') {
                        addProcessLog(evt.message || JSON.stringify(evt), 'info');
                    } else if (type === 'done') {
                        activeEventSource.close();
                        activeEventSource = null;
                        if (processStatus) {
                            processStatus.textContent = 'Complete';
                            processStatus.className = 'text-[10px] font-mono bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-800/60';
                        }
                        if (processPulse) processPulse.classList.remove('animate-ping');
                        addProcessLog('Synthesis complete. Compiling executive report...', 'done');

                        // Fetch final synthesized result
                        fetch(`/api/jobs/${jobId}/result`)
                            .then(r => r.json())
                            .then(jobData => {
                                if (jobData.result) {
                                    const r = jobData.result;
                                    let summaryHtml = `
                                        <div class="mb-5 p-4 sm:p-5 rounded-2xl bg-indigo-50/70 dark:bg-indigo-950/30 border border-indigo-200/80 dark:border-indigo-800/40">
                                            <div class="flex items-center justify-between gap-2 mb-3">
                                                <div class="flex items-center gap-2">
                                                    <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                                                    <span class="text-xs font-bold uppercase tracking-wider text-indigo-900 dark:text-indigo-300">Synthesized Executive Intelligence</span>
                                                </div>
                                                <div class="flex items-center gap-2">
                                                    <a href="/api/export/${jobId}?fmt=md" download="research-${jobId}.md" class="px-2.5 py-1 rounded-lg bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-white/10 text-[11px] font-semibold hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-all flex items-center gap-1">
                                                        📥 Export MD
                                                    </a>
                                                    <a href="/results/${jobId}" target="_blank" class="px-2.5 py-1 rounded-lg bg-indigo-600 text-white text-[11px] font-semibold hover:bg-indigo-700 transition-all flex items-center gap-1">
                                                        📄 Full Report →
                                                    </a>
                                                </div>
                                            </div>
                                            <p class="text-sm text-zinc-800 dark:text-zinc-200 leading-relaxed font-serif whitespace-pre-wrap">${escapeHtml(r.summary || 'Summary compiled.')}</p>
                                        </div>
                                    `;

                                    if (r.findings && r.findings.length > 0) {
                                        extractedFindings = r.findings;
                                    }
                                    if (r.sources && r.sources.length > 0) {
                                        discoveredUrls = r.sources;
                                    }
                                    if (deepLinksCountBadge) deepLinksCountBadge.textContent = `${discoveredUrls.length}`;

                                    // Save state in localStorage for refresh persistence
                                    localStorage.setItem('north_active_deep_search', JSON.stringify({
                                        query,
                                        jobId,
                                        summary: r.summary || '',
                                        findings: extractedFindings,
                                        sources: discoveredUrls,
                                        images: discoveredImages,
                                        timestamp: Date.now()
                                    }));

                                    // Record in history archive
                                    recordSearchHistory({
                                        query,
                                        type: 'deep',
                                        job_id: jobId,
                                        summary: r.summary || '',
                                        total_sources: discoveredUrls.length,
                                        findings_count: extractedFindings.length,
                                        timestamp: Date.now()
                                    });

                                    renderFindingsFeed();
                                    resultsContainer.innerHTML = summaryHtml + resultsContainer.innerHTML;
                                    renderIcons();
                                }
                            })
                            .catch(err => {
                                console.error('Failed to load final result', err);
                            });
                    } else if (type === 'error') {
                        activeEventSource.close();
                        activeEventSource = null;
                        if (processStatus) processStatus.textContent = 'Failed';
                        if (processPulse) processPulse.classList.remove('animate-ping');
                        addProcessLog(`Pipeline Error: ${evt.error || 'Unknown error'}`, 'error');
                    }
                } catch(e) {
                    console.error('SSE JSON error', e);
                }
            };

            activeEventSource.onerror = (err) => {
                console.warn('SSE stream closed or completed', err);
                if (activeEventSource) {
                    activeEventSource.close();
                    activeEventSource = null;
                }
                if (processPulse) processPulse.classList.remove('animate-ping');
            };

        } catch (err) {
            if (processStatus) processStatus.textContent = 'Network Error';
            if (processPulse) processPulse.classList.remove('animate-ping');
            addProcessLog(`Request failed: ${err.message}`, 'error');
            resultsContainer.innerHTML = `<div class="glass-card" style="color:var(--danger);padding:20px;">Network Error: ${escapeHtml(err.message)}</div>`;
        }
    });
}

// ----------------------------------------------------------------------
// Global Search Persistence Across Browser Refreshes (F5)
// ----------------------------------------------------------------------
function restoreActiveSearch() {
    try {
        // 1. Restore Quick Search if present
        const savedQs = localStorage.getItem('north_active_quick_search');
        if (savedQs) {
            const data = JSON.parse(savedQs);
            if (data && data.query && data.results && data.results.length > 0) {
                const qsInput = document.getElementById('qs-query');
                const workspace = document.getElementById('quick-search-workspace');
                const resultsContainer = document.getElementById('quick-search-results');
                const countBadge = document.getElementById('results-count-badge');
                const linksCountBadge = document.getElementById('qs-links-count-badge');
                const statusBox = document.getElementById('quick-search-status');

                if (qsInput) qsInput.value = data.query;
                currentSearchResults = data.results;

                if (workspace) workspace.classList.remove('hidden');
                if (countBadge) countBadge.textContent = `${data.results.length} results`;
                if (linksCountBadge) linksCountBadge.textContent = `${data.results.length}`;
                if (statusBox) statusBox.innerHTML = `<span class="status-pill"><span class="status-dot ok"></span> Restored</span>`;

                if (resultsContainer) {
                    let html = '<div class="results-grid">';
                    data.results.forEach(r => {
                        const isDark = r.source_type === 'darkweb' || r.url.includes('.onion');
                        const tagClass = isDark ? 'source-tag darkweb' : 'source-tag clearnet';
                        const tagLabel = isDark ? `🧅 ${r.source_engine}` : r.source_engine;

                        html += `
                            <div class="result-card">
                                <div class="result-card-header">
                                    <span class="${tagClass}">${tagLabel}</span>
                                    <span style="font-size:11px;font-family:var(--font-mono);color:var(--text-muted);">#${r.rank || ''}</span>
                                </div>
                                <a href="${r.url}" target="_blank" rel="noopener noreferrer" class="result-title">${escapeHtml(r.title || r.url)}</a>
                                <p class="result-snippet">${escapeHtml(r.snippet || 'No preview snippet available.')}</p>
                                <div class="result-url" title="${r.url}">${escapeHtml(r.url)}</div>
                            </div>
                        `;
                    });
                    html += '</div>';
                    resultsContainer.innerHTML = html;
                }
            }
        }

        // 2. Restore Deep Research if present
        const savedDeep = localStorage.getItem('north_active_deep_search');
        if (savedDeep) {
            const data = JSON.parse(savedDeep);
            if (data && data.query) {
                const deepInput = document.getElementById('deep-query');
                const workspace = document.getElementById('deep-research-workspace');
                const resultsContainer = document.getElementById('deep-response');
                const resultsCount = document.getElementById('deep-results-count');
                const linksCountBadge = document.getElementById('deep-links-count-badge');
                const processStatus = document.getElementById('deep-process-status');

                if (deepInput) deepInput.value = data.query;
                if (workspace) workspace.classList.remove('hidden');
                if (processStatus) {
                    processStatus.textContent = 'Restored';
                    processStatus.className = 'text-[10px] font-mono bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-800/60';
                }

                const sources = data.sources || [];
                const findings = data.findings || [];
                const images = data.images || [];

                if (resultsCount) resultsCount.textContent = `${findings.length + sources.length} findings`;
                if (linksCountBadge) linksCountBadge.textContent = `${sources.length}`;

                if (resultsContainer) {
                    let html = '';
                    if (data.summary) {
                        html += `
                            <div class="mb-5 p-4 sm:p-5 rounded-2xl bg-indigo-50/70 dark:bg-indigo-950/30 border border-indigo-200/80 dark:border-indigo-800/40">
                                <div class="flex items-center justify-between gap-2 mb-3">
                                    <div class="flex items-center gap-2">
                                        <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                                        <span class="text-xs font-bold uppercase tracking-wider text-indigo-900 dark:text-indigo-300">Synthesized Executive Intelligence</span>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        ${data.jobId ? `
                                            <a href="/api/export/${data.jobId}?fmt=md" download="research-${data.jobId}.md" class="px-2.5 py-1 rounded-lg bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-white/10 text-[11px] font-semibold hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-all flex items-center gap-1">
                                                📥 Export MD
                                            </a>
                                            <a href="/results/${data.jobId}" target="_blank" class="px-2.5 py-1 rounded-lg bg-indigo-600 text-white text-[11px] font-semibold hover:bg-indigo-700 transition-all flex items-center gap-1">
                                                📄 Full Report →
                                            </a>
                                        ` : ''}
                                    </div>
                                </div>
                                <p class="text-sm text-zinc-800 dark:text-zinc-200 leading-relaxed font-serif whitespace-pre-wrap">${escapeHtml(data.summary)}</p>
                            </div>
                        `;
                    }

                    if (findings.length > 0) {
                        html += `
                            <div class="mb-4">
                                <div class="text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">Key Extracted Findings (${findings.length})</div>
                                <div class="space-y-2.5">
                                    ${findings.map(f => {
                                        const conf = f.confidence ? Math.round(f.confidence * 100) : 85;
                                        return `
                                            <div class="p-3.5 rounded-xl bg-white dark:bg-zinc-900/80 border border-zinc-200 dark:border-white/10 shadow-xs">
                                                <div class="flex items-center justify-between gap-2 mb-1.5">
                                                    <span class="text-xs font-bold text-indigo-600 dark:text-indigo-400">${escapeHtml(f.topic || 'Analysis')}</span>
                                                    <span class="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full ${conf >= 80 ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800' : 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-400'}">${conf}% Confidence</span>
                                                </div>
                                                <p class="text-xs text-zinc-700 dark:text-zinc-300 leading-relaxed">${escapeHtml(f.content || '')}</p>
                                                ${f.source_url ? `
                                                    <div class="mt-2 pt-2 border-t border-zinc-100 dark:border-white/[0.04] flex items-center justify-between">
                                                        <a href="${escapeHtml(f.source_url)}" target="_blank" rel="noopener noreferrer" class="text-[11px] font-mono text-zinc-500 hover:text-indigo-500 dark:hover:text-indigo-400 truncate max-w-[85%]">
                                                            ↗ ${escapeHtml(f.source_title || f.source_url)}
                                                        </a>
                                                        <span class="text-[10px] font-mono bg-zinc-100 dark:bg-white/[0.06] text-zinc-600 dark:text-zinc-400 px-1.5 py-0.2 rounded">${escapeHtml(f.source_type || 'web')}</span>
                                                    </div>
                                                ` : ''}
                                            </div>
                                        `;
                                    }).join('')}
                                </div>
                            </div>
                        `;
                    }

                    if (sources.length > 0) {
                        html += `
                            <div class="mb-4">
                                <div class="text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">Crawled & Discovered Sources (${sources.length})</div>
                                <div class="results-grid">
                                    ${sources.map(u => {
                                        const isDark = (u.url || '').includes('.onion');
                                        const tagClass = isDark ? 'source-tag darkweb' : 'source-tag clearnet';
                                        const tagLabel = isDark ? '🧅 Onion / Darknet' : (u.source_engine || 'Web');
                                        return `
                                            <div class="result-card">
                                                <div class="result-card-header">
                                                    <span class="${tagClass}">${tagLabel}</span>
                                                </div>
                                                <a href="${escapeHtml(u.url)}" target="_blank" rel="noopener noreferrer" class="result-title">${escapeHtml(u.title || u.url)}</a>
                                                ${u.snippet || u.text ? `<p class="result-snippet">${escapeHtml((u.snippet || u.text).slice(0, 200))}</p>` : ''}
                                                <div class="result-url" title="${escapeHtml(u.url)}">${escapeHtml(u.url)}</div>
                                            </div>
                                        `;
                                    }).join('')}
                                </div>
                            </div>
                        `;
                    }

                    resultsContainer.innerHTML = html;
                }
            }
        }
    } catch(e) {
        console.warn('Failed to restore previous search state', e);
    }
}



async function loadDrawerFolderPath() {
    try {
        const res = await fetch('/api/settings');
        const data = await res.json();
        const dirEl = document.getElementById('drawer-downloads-dir');
        if (dirEl && data.downloads_dir) {
            // Show just the last folder name for brevity
            const parts = data.downloads_dir.replace(/\\/g, '/').split('/');
            dirEl.textContent = parts[parts.length - 1] || data.downloads_dir;
            dirEl.title = data.downloads_dir;
        }
    } catch (e) { /* ignore */ }
}

async function pollDownloadsList() {
    const listEl = document.getElementById('downloads-drawer-list');
    const badgeEl = document.getElementById('header-downloads-badge');

    try {
        const res = await fetch('/api/media/downloads');
        if (!res.ok) return;
        const data = await res.json();
        const tasks = data.tasks || [];
        const activeCount = tasks.filter(t => t.state === 'downloading' || t.state === 'paused').length;

        // Update header badge
        if (badgeEl) {
            if (activeCount > 0) {
                badgeEl.textContent = activeCount;
                badgeEl.classList.remove('hidden');
            } else {
                badgeEl.classList.add('hidden');
            }
        }

        // Only update drawer list if drawer is open
        const drawer = document.getElementById('downloads-drawer');
        if (!drawer || drawer.style.display === 'none' || !listEl) return;

        // Filter by active tab
        const activeTasks = tasks.filter(t => t.state === 'downloading' || t.state === 'paused');
        const doneTasks = tasks.filter(t => t.state === 'finished' || t.state === 'completed');
        const showTasks = _dlActiveTab === 'done' ? doneTasks : activeTasks;

        if (showTasks.length === 0) {
            listEl.innerHTML = `
                <div class="p-8 text-center text-xs text-zinc-500 dark:text-zinc-400">
                    <i data-lucide="${_dlActiveTab === 'done' ? 'folder-check' : 'download-cloud'}" class="w-8 h-8 mx-auto mb-2 text-zinc-400 opacity-60"></i>
                    ${_dlActiveTab === 'done' ? 'No downloaded files yet. Finished downloads appear here.' : 'No downloads in progress. Parallel 8-part downloads will appear here.'}
                </div>
            `;
            renderIcons();
            return;
        }

        let html = '';
        showTasks.forEach(t => {
            const isDownloading = t.state === 'downloading';
            const isPaused = t.state === 'paused';
            const isCompleted = t.state === 'finished' || t.state === 'completed';
            const isFailed = t.state === 'error' || t.state === 'failed';

            let statusBadge = '';
            if (isPaused) {
                statusBadge = `<span class="dl-status-badge" style="background:rgba(251,191,36,0.12);color:#d97706;border-color:rgba(251,191,36,0.3);"><i data-lucide="pause-circle" class="w-3 h-3"></i> Paused (${t.percent || 0}%)</span>`;
            } else if (isDownloading) {
                statusBadge = `<span class="dl-status-badge dl-status-downloading"><i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i> 8x Parallel (${t.percent || 0}%)</span>`;
            } else if (isCompleted) {
                statusBadge = `<span class="dl-status-badge dl-status-completed"><i data-lucide="check" class="w-3 h-3"></i> Saved to PC</span>`;
            } else {
                statusBadge = `<span class="dl-status-badge dl-status-failed"><i data-lucide="alert-circle" class="w-3 h-3"></i> ${escapeHtml(t.error || 'Failed')}</span>`;
            }

            const qualityBadge = t.quality_label ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 border border-zinc-200 dark:border-white/10">${escapeHtml(t.quality_label)}</span>` : '';

            html += `
                <div class="dl-card ${(isDownloading || isPaused) ? 'dl-card-active' : ''}">
                    <div class="dl-card-title">${escapeHtml(t.title || t.filename || 'Video Download')} ${qualityBadge}</div>
                    
                    <div class="dl-card-bar-track">
                        <div class="dl-card-bar-fill" style="width: ${t.percent || 0}%; ${isPaused ? 'background: #f59e0b;' : ''}"></div>
                    </div>

                    <div class="dl-card-meta">
                        <span>${isPaused ? '⏸ Paused' : (t.speed_str || (isCompleted ? 'Finished' : '0 MB/s'))}</span>
                        <span>${t.eta_str && !isCompleted ? 'ETA: ' + t.eta_str : (t.downloaded_bytes ? (t.downloaded_bytes / (1024*1024)).toFixed(1) + ' MB' : '')}</span>
                    </div>

                    <div class="dl-card-actions">
                        ${statusBadge}
                        <div class="flex items-center gap-1">
                            ${isDownloading ? `
                                <button onclick="pauseDownloadTask('${escapeHtml(t.task_id)}')" title="Pause" class="px-2 py-0.5 rounded text-[10px] font-medium bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-800/60 hover:bg-amber-100 transition-all">
                                    ⏸ Pause
                                </button>
                            ` : ''}
                            ${isPaused ? `
                                <button onclick="resumeDownloadTask('${escapeHtml(t.task_id)}')" title="Resume" class="px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/60 hover:bg-emerald-100 transition-all">
                                    ▶ Resume
                                </button>
                            ` : ''}
                            ${(isDownloading || isPaused) ? `
                                <button onclick="cancelDownloadTask('${escapeHtml(t.task_id)}')" class="px-2 py-0.5 rounded text-[10px] font-medium bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-800/60 hover:bg-rose-100 transition-all">
                                    ✕ Cancel
                                </button>
                            ` : ''}
                            ${isCompleted && t.filepath ? `
                                <button onclick="openLocalFile('${escapeHtml(t.filepath)}')" class="px-2 py-0.5 rounded text-[10px] font-medium bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800/60 hover:bg-blue-100 transition-all">
                                    📂 Open
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        });

        listEl.innerHTML = html;
        renderIcons();

    } catch (e) {
        console.error('Error polling downloads:', e);
    }
}

async function pauseDownloadTask(taskId) {
    if (!taskId) return;
    try {
        const fd = new FormData();
        fd.append('task_id', taskId);
        await fetch('/api/media/pause-download', { method: 'POST', body: fd });
        pollDownloadsList();
    } catch (e) {
        console.error('Failed to pause download', e);
    }
}

async function resumeDownloadTask(taskId) {
    if (!taskId) return;
    try {
        const fd = new FormData();
        fd.append('task_id', taskId);
        await fetch('/api/media/resume-download', { method: 'POST', body: fd });
        pollDownloadsList();
    } catch (e) {
        console.error('Failed to resume download', e);
    }
}

async function cancelDownloadTask(taskId) {
    if (!taskId) return;
    try {
        const fd = new FormData();
        fd.append('task_id', taskId);
        await fetch('/api/media/cancel-download', { method: 'POST', body: fd });
        pollDownloadsList();
    } catch (e) {
        console.error('Failed to cancel download', e);
    }
}

async function openLocalFile(filepath) {
    // Ask server to reveal in Explorer / file manager
    try {
        const fd = new FormData();
        fd.append('filepath', filepath);
        await fetch('/api/media/open-file', { method: 'POST', body: fd });
    } catch (e) {
        console.error('Failed to open file', e);
    }
}


// ----------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------
function loadOllamaModels() {
    const sel = document.getElementById('ai-model');
    if (!sel) return;
    fetch('/api/models').then(r => r.json()).then(data => {
        if (data.models && data.models.length) {
            sel.innerHTML = '';
            data.models.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = m;
                if (m === data.current) opt.selected = true;
                sel.appendChild(opt);
            });
        }
    }).catch(() => {});
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function debounce(fn, ms) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), ms);
    };
}
