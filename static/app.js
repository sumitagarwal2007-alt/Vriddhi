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

async function fetchFeedback() {
    try {
        const res = await fetch('/api/feedback');
        const data = await res.json();
        
        if (data.status === 'success') {
            const list = document.getElementById('learning-list');
            if (data.data.length === 0) {
                list.innerHTML = '<tr><td colspan="4" class="empty-state">No trade feedback loaded yet.</td></tr>';
                return;
            }
            
            list.innerHTML = data.data.map(f => {
                const pnl = f.pnl_pct;
                const pnlClass = pnl >= 0 ? 'tr-profit' : 'tr-loss';
                const pnlText = (pnl >= 0 ? '+' : '') + pnl.toFixed(2) + '%';
                
                return `
                    <tr class="${pnlClass}">
                        <td>
                            <span class="ticker-badge">${f.ticker}</span>
                            <div class="small-detail" style="max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${f.headline}">${f.headline}</div>
                        </td>
                        <td class="txt-right">
                            <div>$${f.sell_price.toFixed(2)}</div>
                            <div class="small-detail">In: $${f.buy_price.toFixed(2)}</div>
                        </td>
                        <td class="txt-right ${pnl >= 0 ? 'val-positive' : 'val-negative'}" style="font-weight: bold;">
                            ${pnlText}
                        </td>
                        <td style="font-size: 11px; max-width: 200px; line-height: 1.3;">
                            <div style="font-style: italic; color: #aaa;" title="${f.reasoning}">${f.reasoning.length > 80 ? f.reasoning.substring(0, 80) + '...' : f.reasoning}</div>
                        </td>
                    </tr>
                `;
            }).join('');
        }
    } catch (e) {
        console.error("Feedback error", e);
    }
}

function updateAll() {
    fetchStats();
    fetchKosh();
    fetchPositions();
    fetchNews();
    fetchFeedback();
}

// Initial fetch
updateAll();

// Poll every 3 seconds
setInterval(updateAll, 3000);
