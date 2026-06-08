function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active-tab'));
    
    event.target.classList.add('active');
    document.getElementById(`${tabId}-positions`).classList.add('active-tab');
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
                activeList.innerHTML = '<div class="empty-state">No active positions.</div>';
            } else {
                activeList.innerHTML = data.active.map(p => `
                    <div class="pos-card ${p.unrealized_pl >= 0 ? 'profit' : 'loss'}">
                        <div class="pos-left">
                            <div class="ticker">${p.ticker} <span style="font-size: 0.7em; color: rgba(255,255,255,0.5); font-weight: normal;">($${p.current_price.toFixed(2)})</span></div>
                            <div class="details">${p.qty.toFixed(4)} sh | Cost: $${p.cost_basis.toFixed(2)}</div>
                        </div>
                        <div class="pos-right">
                            <div class="pl ${p.unrealized_pl >= 0 ? 'val-positive' : 'val-negative'}">
                                ${p.unrealized_pl >= 0 ? '+' : ''}$${p.unrealized_pl.toFixed(2)} (${p.unrealized_plpc.toFixed(2)}%)
                            </div>
                            <div class="stop">Stop: $${p.stop_price ? p.stop_price.toFixed(2) : 'N/A'}</div>
                        </div>
                    </div>
                `).join('');
            }
            
            // Render Waitlist
            const waitlistList = document.getElementById('waitlist-list');
            if (data.waitlist.length === 0) {
                waitlistList.innerHTML = '<div class="empty-state">Waitlist is clear.</div>';
            } else {
                waitlistList.innerHTML = data.waitlist.map(w => {
                    const statusText = w.is_overnight ? `Pre-Market: ${w.target_buy_time.split('T')[1].substring(0,5)}` : `Waiting 3m: ${w.target_buy_time.split('T')[1].substring(0,8)}`;
                    return `
                    <div class="pos-card waitlist">
                        <div class="pos-left">
                            <div class="ticker">${w.ticker}</div>
                            <div class="details">Trigger: $${w.initial_price.toFixed(2)}</div>
                        </div>
                        <div class="pos-right">
                            <div class="stop">${statusText}</div>
                        </div>
                    </div>
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

function updateAll() {
    fetchStats();
    fetchKosh();
    fetchPositions();
    fetchNews();
}

// Initial fetch
updateAll();

// Poll every 3 seconds
setInterval(updateAll, 3000);
