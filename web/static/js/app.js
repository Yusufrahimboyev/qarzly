/**
 * QARZ DAFTAR — TELEGRAM MINI APP JAVASCRIPT
 */

// Initialize Telegram WebApp
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
    try {
        tg.enableClosingConfirmation();
    } catch (e) {}
}

function hapticSuccess() {
    try {
        tg?.HapticFeedback?.notificationOccurred('success');
    } catch (e) {}
}

function hapticError() {
    try {
        tg?.HapticFeedback?.notificationOccurred('error');
    } catch (e) {}
}

function hapticImpact() {
    try {
        tg?.HapticFeedback?.impactOccurred('light');
    } catch (e) {}
}

// Global App State
const state = {
    summaries: [],
    filter: 'all',
    searchQuery: '',
    selectedClientReport: null,
};

// Utilities
function formatMoney(amount) {
    const num = Math.round(Number(amount) || 0);
    return num.toLocaleString('ru-RU').replace(/,/g, ' ') + " so'm";
}

function getTodayFormatted() {
    const now = new Date();
    const d = String(now.getDate()).padStart(2, '0');
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const y = now.getFullYear();
    return `${d}.${m}.${y}`;
}

function showToast(message) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

// ==========================================
// API REQUESTS
// ==========================================

async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        if (!res.ok) return;
        const data = await res.json();
        document.getElementById('stat-total-debt').textContent = formatMoney(data.total_debt);
        document.getElementById('stat-debtors-count').textContent = `${data.debtors_count} ta`;
        document.getElementById('stat-clients-count').textContent = `${data.clients_count} ta`;
    } catch (err) {
        console.error('Error fetching stats:', err);
    }
}

async function fetchSummaries() {
    try {
        const res = await fetch('/api/summaries');
        if (!res.ok) return;
        state.summaries = await res.json();
        renderClientsList();
        populatePaymentClients();
    } catch (err) {
        console.error('Error fetching summaries:', err);
        document.getElementById('clients-list').innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <p>Ma'lumotlarni yuklab bo'lmadi</p>
            </div>
        `;
    }
}

async function fetchClientReport(clientId) {
    try {
        const res = await fetch(`/api/clients/${clientId}/report`);
        if (!res.ok) throw new Error('Hisobot topilmadi');
        return await res.json();
    } catch (err) {
        console.error('Error fetching client report:', err);
        return null;
    }
}

// ==========================================
// TAB 1: RENDER CLIENTS LIST & SEARCH/FILTER
// ==========================================

function renderClientsList() {
    const container = document.getElementById('clients-list');
    if (!container) return;

    let list = [...state.summaries];

    // Apply Filter Chips
    if (state.filter === 'debtors') {
        list = list.filter(item => item.has_debt);
    } else if (state.filter === 'paid') {
        list = list.filter(item => !item.has_debt);
    }

    // Apply Search Query
    if (state.searchQuery.trim()) {
        const q = state.searchQuery.toLowerCase().trim();
        list = list.filter(item => 
            item.full_name.toLowerCase().includes(q) ||
            item.phone.toLowerCase().includes(q)
        );
    }

    if (list.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📂</div>
                <p>Hech qanday mijoz topilmadi</p>
            </div>
        `;
        return;
    }

    container.innerHTML = list.map(item => `
        <div class="client-item-card" data-client-id="${item.id}">
            <div class="client-item-info">
                <div class="client-item-name">${escapeHtml(item.full_name)}</div>
                <div class="client-item-phone">${escapeHtml(item.phone)}</div>
            </div>
            <div class="client-item-meta">
                <div class="client-item-debt ${item.has_debt ? 'has-debt' : 'no-debt'}">
                    ${item.has_debt ? formatMoney(item.total_remaining_debt) : "0 so'm"}
                </div>
                <span class="badge ${item.has_debt ? 'badge-danger' : 'badge-success'}">
                    ${item.has_debt ? '🔴 Qarzdor' : '🟢 Yopilgan'}
                </span>
            </div>
        </div>
    `).join('');

    // Attach click handlers to open modal
    container.querySelectorAll('.client-item-card').forEach(card => {
        card.addEventListener('click', () => {
            const clientId = card.getAttribute('data-client-id');
            openClientReportModal(clientId);
        });
    });
}

function escapeHtml(str) {
    return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ==========================================
// CLIENT REPORT MODAL
// ==========================================

async function openClientReportModal(clientId) {
    hapticImpact();
    const modal = document.getElementById('report-modal');
    const data = await fetchClientReport(clientId);
    if (!data || !modal) {
        showToast('Mijoz ma\'lumotlarini yuklab bo\'lmadi');
        return;
    }

    state.selectedClientReport = data;

    document.getElementById('modal-client-name').textContent = data.client.full_name;
    document.getElementById('modal-client-phone').textContent = data.client.phone;
    document.getElementById('modal-total-products').textContent = formatMoney(data.total_product_price);
    document.getElementById('modal-total-paid').textContent = formatMoney(data.total_paid_after + data.total_given_money);
    document.getElementById('modal-total-remaining').textContent = formatMoney(data.total_remaining_debt);

    // Render Debts History
    const debtsList = document.getElementById('modal-debts-list');
    if (data.debts.length === 0) {
        debtsList.innerHTML = '<p class="text-muted" style="font-size:13px;">Qarzlar mavjud emas</p>';
    } else {
        debtsList.innerHTML = data.debts.map(d => `
            <div class="history-card">
                <div class="history-card-header">
                    <span>${escapeHtml(d.product_name)}</span>
                    <span class="${d.status === 'active' ? 'text-danger' : 'text-success'}">
                        ${d.status === 'active' ? formatMoney(d.remaining_debt) : '🟢 Yopilgan'}
                    </span>
                </div>
                <div class="history-card-detail">
                    <span>📅 ${d.debt_date}</span>
                    <span>Narxi: ${formatMoney(d.product_price)}</span>
                </div>
                ${d.exchange_exists ? `
                <div class="history-card-detail" style="color:var(--accent-yellow); margin-top:2px;">
                    <span>🔄 Exchange: ${escapeHtml(d.exchange_product_name || 'Tovar')}</span>
                    <span>-${formatMoney(d.exchange_product_price)}</span>
                </div>` : ''}
                ${d.given_money > 0 ? `
                <div class="history-card-detail" style="color:var(--accent-green); margin-top:2px;">
                    <span>💵 Berilgan pul:</span>
                    <span>-${formatMoney(d.given_money)}</span>
                </div>` : ''}
            </div>
        `).join('');
    }

    // Render Payments History
    const paymentsList = document.getElementById('modal-payments-list');
    const actualPayments = data.payments.filter(p => p.payment_type !== 'initial');
    if (actualPayments.length === 0) {
        paymentsList.innerHTML = '<p class="text-muted" style="font-size:13px;">To\'lovlar mavjud emas</p>';
    } else {
        paymentsList.innerHTML = actualPayments.map(p => `
            <div class="history-card">
                <div class="history-card-header">
                    <span class="text-success">+${formatMoney(p.amount)}</span>
                    <span style="font-size:11px; text-transform:uppercase;">
                        ${p.payment_type === 'full' ? 'To\'liq' : 'Qisman'}
                    </span>
                </div>
                <div class="history-card-detail">
                    <span>📅 ${p.payment_date}</span>
                </div>
            </div>
        `).join('');
    }

    const payBtn = document.getElementById('modal-pay-now-btn');
    if (data.total_remaining_debt <= 0) {
        payBtn.style.display = 'none';
    } else {
        payBtn.style.display = 'block';
    }

    modal.style.display = 'flex';
}

function closeClientReportModal() {
    const modal = document.getElementById('report-modal');
    if (modal) modal.style.display = 'none';
    state.selectedClientReport = null;
}

// ==========================================
// TAB 2: CREATE DEBT FORM & LIVE CALC
// ==========================================

function setupCreateForm() {
    const dateInput = document.getElementById('create-date');
    const btnToday = document.getElementById('btn-set-today');
    const productPriceInput = document.getElementById('create-product-price');
    const exchangeToggle = document.getElementById('create-exchange-toggle');
    const exchangeFields = document.getElementById('exchange-fields');
    const exchangePriceInput = document.getElementById('create-exchange-price');
    const givenToggle = document.getElementById('create-given-toggle');
    const givenFields = document.getElementById('given-money-fields');
    const givenAmountInput = document.getElementById('create-given-amount');
    const submitBtn = document.getElementById('btn-submit-debt');

    // Default Date to Today
    if (dateInput) dateInput.value = getTodayFormatted();
    if (btnToday) {
        btnToday.addEventListener('click', () => {
            if (dateInput) dateInput.value = getTodayFormatted();
            hapticImpact();
        });
    }

    // Toggle Exchange
    if (exchangeToggle) {
        exchangeToggle.addEventListener('change', () => {
            exchangeFields.style.display = exchangeToggle.checked ? 'block' : 'none';
            if (!exchangeToggle.checked && exchangePriceInput) exchangePriceInput.value = '';
            updateCreateCalculation();
            hapticImpact();
        });
    }

    // Toggle Given Money
    if (givenToggle) {
        givenToggle.addEventListener('change', () => {
            givenFields.style.display = givenToggle.checked ? 'block' : 'none';
            if (!givenToggle.checked && givenAmountInput) givenAmountInput.value = '';
            updateCreateCalculation();
            hapticImpact();
        });
    }

    // Input changes for live calculation
    [productPriceInput, exchangePriceInput, givenAmountInput].forEach(el => {
        if (el) el.addEventListener('input', updateCreateCalculation);
    });

    function updateCreateCalculation() {
        const productPrice = Number(productPriceInput?.value) || 0;
        const hasExchange = exchangeToggle?.checked;
        const exchangePrice = hasExchange ? (Number(exchangePriceInput?.value) || 0) : 0;
        const hasGiven = givenToggle?.checked;
        const givenAmount = hasGiven ? (Number(givenAmountInput?.value) || 0) : 0;

        document.getElementById('calc-product-price').textContent = formatMoney(productPrice);

        const exRow = document.getElementById('calc-exchange-row');
        if (exRow) {
            exRow.style.display = hasExchange ? 'flex' : 'none';
            document.getElementById('calc-exchange-price').textContent = `-${formatMoney(exchangePrice)}`;
        }

        const givenRow = document.getElementById('calc-given-row');
        if (givenRow) {
            givenRow.style.display = hasGiven ? 'flex' : 'none';
            document.getElementById('calc-given-price').textContent = `-${formatMoney(givenAmount)}`;
        }

        const totalDebt = Math.max(0, productPrice - exchangePrice - givenAmount);
        document.getElementById('calc-total-debt').textContent = formatMoney(totalDebt);
    }

    // Submit New Debt
    if (submitBtn) {
        submitBtn.addEventListener('click', async () => {
            const clientName = document.getElementById('create-client-name')?.value.trim();
            const clientPhone = document.getElementById('create-client-phone')?.value.trim();
            const debtDate = dateInput?.value.trim() || getTodayFormatted();
            const productName = document.getElementById('create-product-name')?.value.trim();
            const productPrice = Number(productPriceInput?.value) || 0;

            const hasExchange = exchangeToggle?.checked || false;
            const exchangeName = document.getElementById('create-exchange-name')?.value.trim() || null;
            const exchangePrice = hasExchange ? (Number(exchangePriceInput?.value) || 0) : 0;

            const hasGiven = givenToggle?.checked || false;
            const givenMoney = hasGiven ? (Number(givenAmountInput?.value) || 0) : 0;

            if (!clientName) {
                showToast('Mijoz ismini kiriting');
                return;
            }
            if (!clientPhone) {
                showToast('Telefon raqamini kiriting');
                return;
            }
            if (!productName) {
                showToast('Tovar nomini kiriting');
                return;
            }
            if (productPrice <= 0) {
                showToast('Tovar narxini kiriting');
                return;
            }
            if (exchangePrice + givenMoney > productPrice) {
                showToast('Exchange va berilgan pul tovar narxidan oshmasligi kerak');
                return;
            }

            submitBtn.disabled = true;
            submitBtn.textContent = 'Saqlanmoqda...';

            try {
                const res = await fetch('/api/debts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        client_name: clientName,
                        client_phone: clientPhone,
                        debt_date: debtDate,
                        product_name: productName,
                        product_price: productPrice,
                        exchange_exists: hasExchange,
                        exchange_product_name: exchangeName,
                        exchange_product_price: exchangePrice,
                        given_money: givenMoney,
                    })
                });

                const json = await res.json();
                if (!res.ok || json.error) {
                    throw new Error(json.error || 'Qarzni saqlashda xatolik');
                }

                hapticSuccess();
                showToast('✅ Qarz muvaffaqiyatli saqlandi!');

                // Reset form
                document.getElementById('create-debt-form').reset();
                if (exchangeFields) exchangeFields.style.display = 'none';
                if (givenFields) givenFields.style.display = 'none';
                if (dateInput) dateInput.value = getTodayFormatted();
                updateCreateCalculation();

                // Refresh data and switch to tab 1
                await fetchStats();
                await fetchSummaries();
                switchTab('tab-table');
            } catch (err) {
                hapticError();
                showToast(`❌ ${err.message}`);
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = '✅ Qarzni Saqlash';
            }
        });
    }
}

// ==========================================
// TAB 3: PAYMENT FORM
// ==========================================

function populatePaymentClients() {
    const select = document.getElementById('pay-client-select');
    if (!select) return;

    const debtors = state.summaries.filter(s => s.has_debt);
    select.innerHTML = '<option value="">-- Mijozni tanlang --</option>' +
        debtors.map(d => `
            <option value="${d.id}" data-phone="${escapeHtml(d.phone)}" data-debt="${d.total_remaining_debt}">
                ${escapeHtml(d.full_name)} (${formatMoney(d.total_remaining_debt)})
            </option>
        `).join('');
}

function setupPaymentForm() {
    const select = document.getElementById('pay-client-select');
    const infoCard = document.getElementById('pay-client-info-card');
    const optionsWrapper = document.getElementById('pay-options-wrapper');
    const radioModes = document.querySelectorAll('input[name="payment_mode"]');
    const partialGroup = document.getElementById('partial-amount-group');
    const partialInput = document.getElementById('pay-partial-amount');
    const previewAmount = document.getElementById('pay-preview-amount');
    const previewRemaining = document.getElementById('pay-preview-remaining');
    const submitBtn = document.getElementById('btn-submit-payment');

    if (select) {
        select.addEventListener('change', () => {
            const opt = select.selectedOptions[0];
            if (!opt || !opt.value) {
                if (infoCard) infoCard.style.display = 'none';
                if (optionsWrapper) optionsWrapper.style.display = 'none';
                return;
            }

            const name = opt.text.split('(')[0].trim();
            const phone = opt.getAttribute('data-phone');
            const debt = Number(opt.getAttribute('data-debt')) || 0;

            document.getElementById('pay-selected-client-name').textContent = name;
            document.getElementById('pay-selected-client-phone').textContent = phone;
            document.getElementById('pay-selected-client-debt').textContent = formatMoney(debt);

            infoCard.style.display = 'block';
            optionsWrapper.style.display = 'block';
            updatePaymentCalculation();
            hapticImpact();
        });
    }

    radioModes.forEach(radio => {
        radio.addEventListener('change', () => {
            const isPartial = radio.value === 'partial';
            if (partialGroup) partialGroup.style.display = isPartial ? 'block' : 'none';
            updatePaymentCalculation();
            hapticImpact();
        });
    });

    if (partialInput) {
        partialInput.addEventListener('input', updatePaymentCalculation);
    }

    // Quick chip buttons
    document.querySelectorAll('.btn-chip').forEach(btn => {
        btn.addEventListener('click', () => {
            const opt = select?.selectedOptions[0];
            const totalDebt = Number(opt?.getAttribute('data-debt')) || 0;
            const quick = btn.getAttribute('data-quick');

            if (quick === 'half') {
                if (partialInput) partialInput.value = Math.floor(totalDebt / 2);
            } else {
                if (partialInput) partialInput.value = Number(quick) || 0;
            }
            updatePaymentCalculation();
            hapticImpact();
        });
    });

    function updatePaymentCalculation() {
        const opt = select?.selectedOptions[0];
        const totalDebt = Number(opt?.getAttribute('data-debt')) || 0;
        const mode = document.querySelector('input[name="payment_mode"]:checked')?.value || 'full';

        let payAmount = totalDebt;
        if (mode === 'partial') {
            payAmount = Number(partialInput?.value) || 0;
        }

        const remaining = Math.max(0, totalDebt - payAmount);
        if (previewAmount) previewAmount.textContent = formatMoney(payAmount);
        if (previewRemaining) {
            previewRemaining.textContent = formatMoney(remaining);
            previewRemaining.className = remaining === 0 ? 'text-success' : 'text-danger';
        }
    }

    if (submitBtn) {
        submitBtn.addEventListener('click', async () => {
            const clientId = Number(select?.value) || 0;
            const mode = document.querySelector('input[name="payment_mode"]:checked')?.value || 'full';
            const opt = select?.selectedOptions[0];
            const totalDebt = Number(opt?.getAttribute('data-debt')) || 0;

            if (!clientId) {
                showToast('Qarzdor mijozni tanlang');
                return;
            }

            let amount = totalDebt;
            if (mode === 'partial') {
                amount = Number(partialInput?.value) || 0;
                if (amount <= 0) {
                    showToast('To\'lov summasini kiriting');
                    return;
                }
                if (amount > totalDebt) {
                    showToast('To\'lov summasi qarzdan oshmasligi kerak');
                    return;
                }
            }

            submitBtn.disabled = true;
            submitBtn.textContent = 'Qabul qilinmoqda...';

            try {
                const res = await fetch('/api/payments', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        client_id: clientId,
                        payment_type: mode,
                        amount: amount,
                        payment_date: getTodayFormatted(),
                    })
                });

                const json = await res.json();
                if (!res.ok || json.error) {
                    throw new Error(json.error || 'To\'lovni qabul qilishda xatolik');
                }

                hapticSuccess();
                showToast('✅ To\'lov muvaffaqiyatli qabul qilindi!');

                // Reset payment form
                document.getElementById('payment-form').reset();
                if (infoCard) infoCard.style.display = 'none';
                if (optionsWrapper) optionsWrapper.style.display = 'none';
                if (partialGroup) partialGroup.style.display = 'none';

                // Refresh data and switch to tab 1
                await fetchStats();
                await fetchSummaries();
                switchTab('tab-table');
            } catch (err) {
                hapticError();
                showToast(`❌ ${err.message}`);
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = '✅ To\'lovni Qabul Qilish';
            }
        });
    }
}

// ==========================================
// TABS & NAVIGATION
// ==========================================

function switchTab(tabId) {
    document.querySelectorAll('.tab-pane').forEach(tab => {
        tab.classList.toggle('active', tab.id === tabId);
    });
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ==========================================
// EVENT LISTENERS INITIALIZATION
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    // Bottom Nav Tabs
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.getAttribute('data-tab');
            switchTab(tabId);
            hapticImpact();
        });
    });

    // Refresh Button
    const refreshBtn = document.getElementById('btn-refresh');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            refreshBtn.classList.add('rotating');
            hapticImpact();
            await Promise.all([fetchStats(), fetchSummaries()]);
            setTimeout(() => refreshBtn.classList.remove('rotating'), 600);
            showToast('Yangilandi');
        });
    }

    // Search Input
    const searchInput = document.getElementById('table-search-input');
    const clearSearchBtn = document.getElementById('clear-search-btn');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            state.searchQuery = e.target.value;
            if (clearSearchBtn) clearSearchBtn.style.display = state.searchQuery ? 'block' : 'none';
            renderClientsList();
        });
    }
    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            if (searchInput) searchInput.value = '';
            state.searchQuery = '';
            clearSearchBtn.style.display = 'none';
            renderClientsList();
            hapticImpact();
        });
    }

    // Filter Chips
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            state.filter = chip.getAttribute('data-filter') || 'all';
            renderClientsList();
            hapticImpact();
        });
    });

    // Modal Close
    const modalCloseBtn = document.getElementById('modal-close-btn');
    if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeClientReportModal);

    const modalOverlay = document.getElementById('report-modal');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) closeClientReportModal();
        });
    }

    // Modal "Pay Now" Quick Action
    const modalPayBtn = document.getElementById('modal-pay-now-btn');
    if (modalPayBtn) {
        modalPayBtn.addEventListener('click', () => {
            if (!state.selectedClientReport) return;
            const clientId = state.selectedClientReport.client.id;
            closeClientReportModal();
            switchTab('tab-payment');

            // Select this client in dropdown
            const select = document.getElementById('pay-client-select');
            if (select) {
                select.value = String(clientId);
                select.dispatchEvent(new Event('change'));
            }
        });
    }

    // Setup forms
    setupCreateForm();
    setupPaymentForm();

    // Initial Fetch
    fetchStats();
    fetchSummaries();
});
