function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active-tab'));
    
    // Find the button that was clicked
    const btn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick').includes(tabId));
    if (btn) {
        btn.classList.add('active');
    }
    
    const target = document.getElementById(`${tabId}-positions`);
    if (target) {
        target.classList.add('active-tab');
    }
}

async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        
        if (data.status === 'success') {
            const pnlEl = document.getElementById('total-pnl');
            pnlEl.textContent = `$${data.pnl.toFixed(2)}`;
            pnlEl.className = 'value ' + (data.pnl >= 0 ? 'val-positive' : 'val-negative');
            
            document.getElementById('win-rate').textContent = `${data.win_rate.toFixed(1)}%`;
            document.getElementById('total-trades').textContent = data.trades;
            
            const dot = document.querySelector('.dot');
            const text = document.getElementById('market-text');
            if (data.is_open) {
                dot.className = 'dot open';
                text.textContent = 'MARKET OPEN';
                text.style.color = 'var(--color-bull)';
            } else {
                dot.className = 'dot closed';
                text.textContent = `CLOSED (Opens ${data.next_open})`;
                text.style.color = 'var(--color-bear)';
            }
        }
    } catch (e) {
        console.error("Stats error", e);
    }
}

async function fetchKosh() {
    try {
        const res = await fetch('/api/kosh');
        const data = await res.json();
        
        if (data.status === 'success') {
            document.getElementById('kosh-value').textContent = `$${data.portfolio_value.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
            document.getElementById('kosh-cash').textContent = `$${data.cash.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
            document.getElementById('kosh-bp').textContent = `$${data.buying_power.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
        }
    } catch (e) {
        console.error("Kosh error", e);
    }
}

async function fetchPositions() {
    try {
        const res = await fetch('/api/positions');
        const data = await res.json();
        
        if (data.status === 'success') {
            // Render Active
            const activeList = document.getElementById('positions-list');
            if (data.active.length === 0) {
                activeList.innerHTML = '<tr><td colspan="5" class="empty-state">No active positions.</td></tr>';
            } else {
                activeList.innerHTML = data.active.map(p => `
                    <tr class="${p.unrealized_pl >= 0 ? 'tr-profit' : 'tr-loss'}">
                        <td><span class="ticker-badge">${p.ticker}</span></td>
                        <td class="txt-right">$${p.current_price.toFixed(2)}</td>
                        <td class="txt-right">
                            <div>${p.qty.toFixed(3)} sh</div>
                            <div class="small-detail">Cost: $${p.cost_basis.toFixed(2)}</div>
                        </td>
                        <td class="txt-right ${p.unrealized_pl >= 0 ? 'val-positive' : 'val-negative'}">
                            <div>${p.unrealized_pl >= 0 ? '+' : ''}$${p.unrealized_pl.toFixed(2)}</div>
                            <div class="small-detail">${p.unrealized_plpc.toFixed(2)}%</div>
                        </td>
                        <td class="txt-right stop-col">$${p.stop_price ? p.stop_price.toFixed(2) : 'N/A'}</td>
                    </tr>
                `).join('');
            }
            
            // Render Waitlist
            const waitlistList = document.getElementById('waitlist-list');
            if (data.waitlist.length === 0) {
                waitlistList.innerHTML = '<tr><td colspan="4" class="empty-state">Waitlist is clear.</td></tr>';
            } else {
                waitlistList.innerHTML = data.waitlist.map(w => {
                    const statusText = w.is_overnight ? `Pre-Market: ${w.target_buy_time.split('T')[1].substring(0,5)}` : `3m Wait: ${w.target_buy_time.split('T')[1].substring(0,8)}`;
                    return `
                    <tr class="tr-waitlist">
                        <td><span class="ticker-badge">${w.ticker}</span></td>
                        <td class="txt-right">$${w.initial_price.toFixed(2)}</td>
                        <td class="txt-right"><span class="highlight-gold">${w.significance_score || 7}</span></td>
                        <td class="txt-right small-detail">${statusText}</td>
                    </tr>
                `}).join('');
            }
        }
    } catch (e) {
        console.error("Positions error", e);
    }
}

async function fetchNews() {
    try {
        const res = await fetch('/api/news');
        const data = await res.json();
        
        if (data.status === 'success') {
            const list = document.getElementById('news-list');
            if (data.data.length === 0) {
                list.innerHTML = '<div class="empty-state">No news processed yet.</div>';
                return;
            }
            
            list.innerHTML = data.data.map(n => {
                const timeStr = n.timestamp.includes('T') ? n.timestamp.split('T')[1].substring(0,8) : n.timestamp;
                const sentClass = n.sentiment.toLowerCase();
                return `
                    <div class="news-card">
                        <div class="news-header">
                            <span class="news-ticker">${n.ticker}</span>
                            <span class="news-sentiment ${sentClass}">${n.sentiment}</span>
                            <span class="news-time">${timeStr}</span>
                        </div>
                        <div class="news-headline">${n.headline}</div>
                        <div class="news-reasoning">${n.reasoning}</div>
                    </div>
                `
            }).join('');
        }
    } catch (e) {
        console.error("News error", e);
    }
}

// Keep track of expanded card IDs so they don't collapse on polling refresh
const expandedCards = new Set();
let allFeedback = [];
let feedbackFilter = 'all';
let feedbackSearchQuery = '';
let feedbackSort = 'recent';
let feedbackLimit = 15;

function toggleCard(id) {
    const card = document.getElementById(`learn-card-${id}`);
    if (!card) return;
    
    if (card.classList.contains('expanded')) {
        card.classList.remove('expanded');
        expandedCards.delete(id);
    } else {
        card.classList.add('expanded');
        expandedCards.add(id);
    }
}

function handleFeedbackSearch(val) {
    feedbackSearchQuery = val.trim().toLowerCase();
    renderFeedbackList();
}

function handleFeedbackSort(val) {
    feedbackSort = val;
    renderFeedbackList();
}

function handleFeedbackFilter(filter) {
    feedbackFilter = filter;
    
    // Update active class on filter pills
    document.querySelectorAll('.learning-filter-row .filter-pill').forEach(pill => {
        pill.classList.remove('active');
    });
    const activePill = document.getElementById(`pill-${filter}`);
    if (activePill) {
        activePill.classList.add('active');
    }
    
    renderFeedbackList();
}

function loadMoreFeedback() {
    feedbackLimit += 15;
    renderFeedbackList();
}

function showAllFeedback() {
    feedbackLimit = 0; // 0 will show all matching
    renderFeedbackList();
}

async function fetchFeedback() {
    try {
        // Fetch ALL trades so client-side can instantly sort/filter/search
        const res = await fetch('/api/feedback?limit=0');
        const data = await res.json();
        
        if (data.status === 'success') {
            allFeedback = data.data;
            renderFeedbackList();
        }
    } catch (e) {
        console.error("Feedback error", e);
    }
}

function renderFeedbackList() {
    const list = document.getElementById('learning-list');
    if (!list) return;
    
    if (allFeedback.length === 0) {
        list.innerHTML = '<div class="empty-state">No trade feedback loaded yet.</div>';
        return;
    }
    
    // 1. Filter by Search Query (Ticker)
    let filtered = allFeedback;
    if (feedbackSearchQuery) {
        filtered = filtered.filter(f => f.ticker.toLowerCase().includes(feedbackSearchQuery));
    }
    
    // 2. Filter by Outcome (wins / losses)
    if (feedbackFilter === 'wins') {
        filtered = filtered.filter(f => f.pnl_pct >= 0);
    } else if (feedbackFilter === 'losses') {
        filtered = filtered.filter(f => f.pnl_pct < 0);
    }
    
    // 3. Sort
    if (feedbackSort === 'recent') {
        filtered.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    } else if (feedbackSort === 'pnl-desc') {
        filtered.sort((a, b) => b.pnl_pct - a.pnl_pct);
    } else if (feedbackSort === 'pnl-asc') {
        filtered.sort((a, b) => a.pnl_pct - b.pnl_pct);
    }
    
    if (filtered.length === 0) {
        list.innerHTML = '<div class="empty-state">No matching trades found.</div>';
        return;
    }
    
    // 4. Apply pagination slice
    const totalMatching = filtered.length;
    const sliceLimit = feedbackLimit === 0 ? totalMatching : feedbackLimit;
    const sliced = filtered.slice(0, sliceLimit);
    
    let html = sliced.map((f, index) => {
        // Use ticker in ID so cards don't toggle open/closed on pagination changes
        const id = `card-${f.ticker}-${index}`;
        const pnl = f.pnl_pct;
        const pnlClass = pnl >= 0 ? 'profit' : 'loss';
        const pnlText = (pnl >= 0 ? '+' : '') + pnl.toFixed(2) + '%';
        
        const isExpanded = expandedCards.has(id);
        const expandedClass = isExpanded ? 'expanded' : '';
        
        // Takeaway styling
        let lessonText = "";
        let highlightClass = "";
        if (pnl >= 0) {
            highlightClass = "success";
            lessonText = `<strong>Takeaway:</strong> This trade succeeded because it was triggered by a high-significance fundamental catalyst combined with robust momentum confirmation. Target scale-out achieved.`;
        } else {
            highlightClass = "danger";
            lessonText = `<strong>Takeaway:</strong> Trailing stop was hit to limit portfolio drawdowns. Lesson: Check if overall market index (SPY) trend was weak, or if volatility spike triggered stop premature.`;
        }
        
        const tenaliSection = f.tenali_critique ? `
            <div class="learn-section">
                <div class="learn-section-title">🛡️ Agent Tenali Risk Audit (Consensus Score: ${f.tenali_score || 0}/10)</div>
                <div class="learn-section-content">${f.tenali_critique}</div>
            </div>
        ` : '';
        
        return `
            <div class="learn-card ${pnlClass} ${expandedClass}" id="learn-card-${id}">
                <div class="learn-header" onclick="toggleCard('${id}')">
                    <div>
                        <span class="ticker-badge" style="color: ${pnl >= 0 ? 'var(--color-bull)' : 'var(--color-bear)'};">${f.ticker}</span>
                        <span class="small-detail" style="margin-left: 10px;">${f.timestamp.split('T')[0]}</span>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <span class="pnl-badge ${pnl >= 0 ? 'val-positive' : 'val-negative'}">${pnlText}</span>
                        <svg class="chevron-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </div>
                </div>
                <div class="learn-body">
                    <div class="learn-section">
                        <div class="learn-section-title">📰 The Catalyst (Raw Headline)</div>
                        <div class="learn-section-content" style="color: var(--text-bright); font-weight: 600;">${f.headline}</div>
                    </div>
                    <div class="learn-section">
                        <div class="learn-section-title">🧠 Agent Birbal Analysis (Birbal Score: ${f.significance_score || 0}/10)</div>
                        <div class="learn-section-content">${f.reasoning}</div>
                    </div>
                    ${tenaliSection}
                    <div class="learn-section">
                        <div class="learn-section-title">⚔️ Execution Metrics</div>
                        <div class="learn-section-content">
                            Bought at: <strong>$${f.buy_price.toFixed(2)}</strong> | 
                            Sold at: <strong>$${f.sell_price.toFixed(2)}</strong> | 
                            Closed time: <strong>${f.timestamp.includes('T') ? f.timestamp.split('T')[1].substring(0,8) : f.timestamp}</strong>
                        </div>
                    </div>
                    <div class="learn-highlight-box ${highlightClass}">
                        ${lessonText}
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    // Check if there are more items to load
    if (totalMatching > sliced.length) {
        html += `
            <div class="load-more-container">
                <button class="load-more-btn" onclick="loadMoreFeedback()">
                    Load More (${sliced.length} of ${totalMatching})
                </button>
                <button class="show-all-btn" onclick="showAllFeedback()">
                    Show All
                </button>
            </div>
        `;
    } else if (feedbackLimit === 0 && totalMatching > 15) {
        html += `
            <div class="load-more-container">
                <button class="load-more-btn" onclick="feedbackLimit = 15; renderFeedbackList();">
                    Show Less
                </button>
            </div>
        `;
    }
    
    list.innerHTML = html;
}

function parseMarkdownToHTML(markdown) {
    if (!markdown) return '';
    
    const lines = markdown.split('\n');
    let html = '';
    let inList = false;
    
    for (let line of lines) {
        line = line.trim();
        if (!line) continue;
        
        // Match list bullets
        if (line.startsWith('* ') || line.startsWith('- ')) {
            if (!inList) {
                html += '<ul>';
                inList = true;
            }
            let text = line.substring(2);
            text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            html += `<li>${text}</li>`;
        } else {
            if (inList) {
                html += '</ul>';
                inList = false;
            }
            let text = line;
            text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            html += `<p>${text}</p>`;
        }
    }
    
    if (inList) {
        html += '</ul>';
    }
    
    return html;
}

async function fetchLessons() {
    try {
        const res = await fetch('/api/lessons');
        const data = await res.json();
        
        const banner = document.getElementById('lessons-banner');
        if (data.status === 'success' && data.lessons) {
            document.getElementById('lessons-date').textContent = data.date;
            document.getElementById('lessons-content').innerHTML = parseMarkdownToHTML(data.lessons);
            banner.style.display = 'block';
        } else {
            banner.style.display = 'none';
        }
    } catch (e) {
        console.error("Lessons fetch error", e);
    }
}

function updateAll() {
    fetchStats();
    fetchKosh();
    fetchPositions();
    fetchNews();
    fetchFeedback();
    fetchLessons();
}

// Initial fetch
updateAll();

// Poll every 3 seconds
setInterval(updateAll, 3000);
