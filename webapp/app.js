(() => {
  'use strict';

  const tg = window.Telegram?.WebApp;
  const state = {
    data: null,
    txType: 'expense',
    quickCategoryId: null,
    activeDebtId: null,
    activeGoalId: null,
    activePlanItemId: null,
    charts: {},
    busy: new Set(),
  };

  const $ = (id) => document.getElementById(id);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const fmt = (n) => Number(n || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 });
  const val = (id) => ($(id)?.value || '').trim();
  const walletById = (walletId) => (state.data?.wallets || []).find((w) => String(w.id) === String(walletId));
  const hasPerm = (permission) => (state.data?.permissions || []).includes(permission);
  const walletCurrency = (walletId, fallback = 'UZS') => walletById(walletId)?.currency || fallback;
  const setText = (id, text) => { const el = $(id); if (el) el.textContent = text ?? ''; };
  const clear = (el) => { if (el) el.innerHTML = ''; };
  const initData = () => tg?.initData || new URLSearchParams(location.search).get('tg') || '';
  const authHeaders = () => ({ 'X-Telegram-Init-Data': initData() });
  const idem = () => `${Date.now()}-${Math.random().toString(16).slice(2)}-${crypto?.randomUUID?.() || ''}`;

  function syncCurrencyWithWallet() {
    const walletId = val('wallet') || state.data?.wallets?.[0]?.id;
    const cur = walletCurrency(walletId, val('currency') || 'UZS');
    const curEl = $('currency');
    if (curEl && cur) curEl.value = cur;
  }

  function toast(message, type = 'ok') {
    const root = $('toastRoot');
    if (!root) return alert(message);
    const item = document.createElement('div');
    item.className = `toast ${type}`;
    item.textContent = message;
    root.appendChild(item);
    setTimeout(() => item.remove(), 3500);
  }
  const err = (m) => toast(m || 'Ошибка', 'error');

  function textEl(tag, text, cls = '') {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    el.textContent = text ?? '';
    return el;
  }

  async function request(path, { method = 'GET', body = null, idempotent = false } = {}) {
    const headers = authHeaders();
    if (body !== null) headers['Content-Type'] = 'application/json';
    if (idempotent) headers['X-Idempotency-Key'] = idem();
    try {
      const response = await fetch(path, { method, headers, body: body === null ? undefined : JSON.stringify(body) });
      const type = response.headers.get('content-type') || '';
      const payload = type.includes('application/json') ? await response.json() : await response.text();
      if (!response.ok || payload?.ok === false) throw new Error(payload?.error || payload || `HTTP ${response.status}`);
      return payload;
    } catch (e) {
      if (window.FFOffline?.isQueueable?.(method, path) && (!navigator.onLine || String(e.message || '').includes('Failed to fetch'))) {
        const queued = await window.FFOffline.enqueue({ path, method, body });
        toast('Нет интернета. Операция сохранена в offline-очередь и синхронизируется позже.', 'ok');
        renderOfflineQueue();
        return { ok: true, offline_queued: true, queue_id: queued.id };
      }
      throw e;
    }
  }

  async function withBusy(buttonId, fn) {
    const btn = $(buttonId);
    if (state.busy.has(buttonId)) return;
    state.busy.add(buttonId);
    if (btn) btn.disabled = true;
    try { await fn(); }
    finally { state.busy.delete(buttonId); if (btn) btn.disabled = false; }
  }

  function currentMonth() { return new Date().toISOString().slice(0, 7); }


  async function downloadFile(path, filename) {
    const response = await fetch(path, { headers: authHeaders() });
    if (!response.ok) throw new Error(await response.text());
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function loadData() {
    try {
      state.data = await request('/api/init');
      await window.FFOffline?.saveInit?.(state.data);
    } catch (e) {
      const cached = await window.FFOffline?.getInit?.();
      if (!cached) throw e;
      state.data = cached;
      toast('Нет связи. Показаны последние сохраненные данные.', 'ok');
    }
    renderAll();
  }

  async function finishMutation(result, successMessage, { reload = true, onOnline = null } = {}) {
    if (result?.offline_queued) {
      if (typeof onOnline === 'function') onOnline();
      toast(`${successMessage}. Сохранено в offline-очередь. Данные обновятся после синхронизации.`, 'ok');
      await renderOfflineQueue();
      return;
    }
    toast(successMessage, 'success');
    if (reload) await loadData();
  }

  function renderAll() {
    const d = state.data || {};
    renderSummary(d.summary || {});
    renderSelects(d);
    renderWallets(d.wallets || []);
    renderRecent(d.recent || []);
    renderReports(d);
    renderDebts(d.debts || []);
    renderGoals(d.goals || []);
    renderSettings(d);
    renderWalletManagement(d.wallets || []);
    renderCategoryManagement([...(d.income_categories || []), ...(d.expense_categories || [])]);
    renderSchedules(d.scheduled_payments || []);
    renderFinancialPlan(d.financial_plan || []);
    renderQuickExpense(d.expense_categories || []);
    renderDashboard(d);
    renderOfflineQueue();
    renderCalendar(d.financial_calendar || {});
    renderAiAnalysis(d.ai_analysis || null);
    renderAiRules(d.ai_rules || []);
    renderMandatoryPayments(d.mandatory_payments || {});
    renderScheduledIssues(d.scheduled_payment_issues || []);
    renderMonthEndMoney(d.month_end_money || {});
    renderBudgetWizard(d.budget_wizard || {});
    applyPermissions();
  }

  function setVisible(selector, visible) {
    $$(selector).forEach((el) => el.classList.toggle('hidden', !visible));
  }

  function applyPermissions() {
    const rules = [
      ['manage_wallets', '#walletManageBox, #createWalletBtn'],
      ['manage_categories', '#categoryManageBox, #createCategoryBtn'],
      ['manage_rates', '#ratesBox, #saveRateBtn'],
      ['manage_schedules', '#scheduleBox, #saveScheduleBtn'],
      ['manage_financial_plan', '#savePlanBtn, #financialPlanList .row-actions'],
      ['manage_debt', '#saveDebtBtn'],
      ['manage_goals', '#saveGoalBtn'],
      ['manage_budget', '#budgetBox, #saveBudgetBtn'],
      ['add_transaction', '#saveTransactionBtn, #saveQuickExpenseBtn, #fabExpense, #openQuickExpenseBtn'],
      ['transfer', '#saveTransferBtn'],
      ['export', '#downloadPdfBtn, #exportExcelBtn'],
      ['view_ai_analysis', '[data-page="ai"], #pageAi'],
      ['manage_ai_rules', '#saveAiRuleBtn, #aiRulesList .row-actions'],
    ];
    rules.forEach(([perm, selector]) => setVisible(selector, hasPerm(perm)));
    if (!hasPerm('view_ai_analysis') && !document.querySelector('[data-page="home"]')?.classList.contains('active')) {
      showPage('home');
    }
  }

  function renderSummary(s) {
    setText('balance', `${fmt(s.balance)} ${s.base_currency || ''}`);
    setText('income', fmt(s.income));
    setText('expense', fmt(s.expense));
    setText('debtLeft', fmt(s.debt_left));
    setText('dashBalance', fmt(s.balance));
    const burn = Number(s.income || 0) ? Math.round(Number(s.expense || 0) / Number(s.income || 1) * 100) : 0;
    setText('dashBurnRate', `${burn}%`);
  }

  function option(label, value, selected = false) {
    const o = document.createElement('option');
    o.textContent = label; o.value = value; o.selected = selected;
    return o;
  }

  function fillSelect(id, rows, labelFn, valueFn, first = null) {
    const el = $(id); if (!el) return;
    clear(el);
    if (first) el.appendChild(option(first.label, first.value));
    rows.forEach((r) => el.appendChild(option(labelFn(r), valueFn(r))));
  }

  function renderSelects(d) {
    const wallets = d.wallets || [];
    const cats = state.txType === 'income' ? (d.income_categories || []) : (d.expense_categories || []);
    ['wallet', 'transferFrom', 'transferTo', 'quickExpenseWallet', 'debtPayWallet', 'goalAddWallet'].forEach((id) => fillSelect(id, wallets, (w) => `${w.name} — ${fmt(w.balance)} ${w.currency}`, (w) => w.id));
    fillSelect('category', cats, (c) => c.display_name || c.name, (c) => c.id);
    fillSelect('opWallet', wallets, (w) => w.name, (w) => w.id, { label: 'Все кошельки', value: '' });
    fillSelect('opCategory', [...(d.income_categories || []), ...(d.expense_categories || [])], (c) => `${c.name} (${c.type})`, (c) => c.id, { label: 'Все категории', value: '' });
    fillSelect('budgetCategory', d.expense_categories || [], (c) => c.display_name || c.name, (c) => c.id);
    fillSelect('newCategoryParent', [...(d.income_categories || []), ...(d.expense_categories || [])].filter((c) => !c.parent_id), (c) => `${c.name} (${c.type})`, (c) => c.id, { label: 'Основная категория', value: '' });
    fillSelect('scheduleWallet', wallets, (w) => `${w.name} — ${fmt(w.balance)} ${w.currency}`, (w) => w.id, { label: 'Кошелек для автосписания', value: '' });
    fillSelect('scheduleCategory', d.expense_categories || [], (c) => c.display_name || c.name, (c) => c.id, { label: 'Категория расхода', value: '' });
    fillSelect('aiRuleCategory', d.expense_categories || [], (c) => c.display_name || c.name, (c) => c.id, { label: 'Категория (для правила)', value: '' });
    syncCurrencyWithWallet();
  }

  function renderWallets(wallets) {
    const box = $('walletBalances'); clear(box);
    wallets.forEach((w) => {
      const row = document.createElement('div'); row.className = 'mini-row';
      row.append(textEl('b', w.name), textEl('span', `${fmt(w.balance)} ${w.currency}`));
      box?.appendChild(row);
    });
  }

  function txLabel(t) {
    const sign = ['income', 'transfer_in'].includes(t.type) ? '+' : '-';
    return `${sign} ${fmt(t.amount)} ${t.currency} — ${t.category_name || t.type} / ${t.wallet_name || ''}`;
  }

  function txRow(t) {
    const row = document.createElement('div'); row.className = 'tx-row';
    row.append(textEl('b', txLabel(t)), textEl('small', `${t.created_at || ''} ${t.comment ? ' · ' + t.comment : ''}`));
    const actions = document.createElement('div'); actions.className = 'row-actions';
    const hist = textEl('button', 'История', 'tiny'); hist.addEventListener('click', () => showOperationHistory(t.id)); actions.appendChild(hist);
    if (['income', 'expense'].includes(t.type)) {
      const del = textEl('button', 'Удалить', 'tiny danger'); del.addEventListener('click', () => deleteTransaction(t.id)); actions.appendChild(del);
    }
    row.appendChild(actions);
    return row;
  }

  function renderRecent(rows) {
    const box = $('recent'); clear(box);
    if (!rows.length) return box?.appendChild(textEl('p', 'Операций пока нет', 'empty'));
    rows.forEach((t) => box?.appendChild(txRow(t)));
  }

  function renderSimple(id, rows, fn) {
    const box = $(id); clear(box);
    if (!rows?.length) return box?.appendChild(textEl('p', 'Нет данных', 'empty'));
    rows.forEach((x) => box?.appendChild(textEl('div', fn(x), 'mini-row')));
  }

  function renderReports(d) {
    const month = d.month_summary || {};
    setText('monthIncome', fmt(month.income)); setText('monthExpense', fmt(month.expense)); setText('monthBalance', fmt(month.balance));
    renderSimple('walletReport', d.wallet_report || [], (x) => `${x.name}: ${fmt(x.balance)} ${x.currency} ≈ ${fmt(x.balance_base)} ${d.summary?.base_currency || ''}`);
    renderSimple('memberReport', d.member_report || [], (x) => `${x.full_name} (${x.role}): доход ${fmt(x.income)}, расход ${fmt(x.expense)}, операций ${x.count}`);
    renderSimple('currencyReport', d.currency_report || [], (x) => `${x.currency}: доход ${fmt(x.income)}, расход ${fmt(x.expense)}, остаток ${fmt(x.wallet_balance)}`);
    renderSimple('categoryReport', d.category_report || [], (x) => `${x.category_name}: ${fmt(x.amount)} (${x.percent}%)`);
    renderBudgets(d.budgets || []);
    renderCharts(d);
    renderForecast(d.forecast || {});
  }

  function chartOptions() {
    return { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } }, scales: { y: { beginAtZero: true } } };
  }
  function destroyChart(name) { if (state.charts[name]) state.charts[name].destroy(); }
  function chart(name, id, config) { const canvas = $(id); if (!canvas || !window.Chart) return; destroyChart(name); state.charts[name] = new Chart(canvas, config); }

  function renderCharts(d) {
    const pack = d.chart_pack || {};
    const daily = pack.daily || d.daily_chart || {};
    const cats = d.category_report || [];
    chart('daily', 'dailyChart', { type: 'line', data: { labels: daily.labels || [], datasets: [{ label: 'Доход', data: daily.income || [] }, { label: 'Расход', data: daily.expense || [] }] }, options: chartOptions() });
    chart('homeDaily', 'homeDailyChart', { type: 'line', data: { labels: daily.labels || [], datasets: [{ label: 'Доход', data: daily.income || [] }, { label: 'Расход', data: daily.expense || [] }] }, options: chartOptions() });
    chart('category', 'categoryChart', { type: 'doughnut', data: { labels: cats.map((x) => x.category_name), datasets: [{ data: cats.map((x) => x.amount) }] }, options: { responsive: true, maintainAspectRatio: false } });
    chart('homeCategory', 'homeCategoryChart', { type: 'doughnut', data: { labels: cats.map((x) => x.category_name), datasets: [{ data: cats.map((x) => x.amount) }] }, options: { responsive: true, maintainAspectRatio: false } });
    const trend = pack.monthly_trend || {};
    chart('trend', 'monthlyTrendChart', { type: 'bar', data: { labels: trend.labels || [], datasets: [{ label: 'Доход', data: trend.income || [] }, { label: 'Расход', data: trend.expense || [] }, { label: 'Остаток', data: trend.balance || [], type: 'line' }] }, options: chartOptions() });
    const b = pack.budget_usage || {};
    chart('budgetUsage', 'budgetUsageChart', { type: 'bar', data: { labels: b.labels || [], datasets: [{ label: 'Лимит', data: b.limit || [] }, { label: 'Факт', data: b.spent || [] }] }, options: { ...chartOptions(), indexAxis: 'y' } });
  }

  function renderForecast(fc) {
    const box = $('forecastBox'); clear(box);
    if (!fc || !Object.keys(fc).length) return box?.appendChild(textEl('p', 'Нет данных для прогноза', 'empty'));
    [['Потрачено сейчас', fc.spent_so_far], ['Средний расход / день', fc.daily_avg], ['Прогноз до конца месяца', fc.projected_expense], ['Осталось дней', fc.remaining_days]].forEach(([k, v]) => box?.appendChild(textEl('div', `${k}: ${fmt(v)}`, 'mini-row')));
    setText('dashForecast', fmt(fc.projected_expense));
    chart('forecast', 'forecastChart', { type: 'bar', data: { labels: (fc.categories || []).slice(0, 8).map((x) => x.category_name), datasets: [{ label: 'Сейчас', data: (fc.categories || []).slice(0, 8).map((x) => x.spent) }, { label: 'Прогноз', data: (fc.categories || []).slice(0, 8).map((x) => x.projected) }] }, options: chartOptions() });
  }

  function renderBudgets(rows) {
    const box = $('budgetList'); clear(box);
    if (!rows.length) return box?.appendChild(textEl('p', 'Лимиты пока не заданы', 'empty'));
    rows.forEach((b) => box?.appendChild(textEl('div', `${b.category_name}: ${fmt(b.spent_base)} из ${fmt(b.limit_base)} (${b.percent}%)`, `mini-row ${Number(b.percent) >= 100 ? 'budget-over' : ''}`)));
  }

  function renderDebts(rows) {
    const box = $('debtsList'); clear(box);
    if (!rows.length) return box?.appendChild(textEl('p', 'Долгов пока нет', 'empty'));
    rows.forEach((d) => {
      const row = document.createElement('div'); row.className = 'mini-row';
      row.append(textEl('span', `${d.name}: осталось ${fmt(d.left_amount)} ${d.currency}`));
      const pay = textEl('button', 'Погасить', 'tiny'); pay.addEventListener('click', () => openDebtPayForm(d)); row.appendChild(pay);
      box?.appendChild(row);
    });
  }

  function renderGoals(rows) {
    const box = $('goalsList'); clear(box);
    if (!rows.length) return box?.appendChild(textEl('p', 'Целей пока нет', 'empty'));
    rows.forEach((g) => {
      const row = document.createElement('div'); row.className = 'mini-row';
      row.append(textEl('span', `${g.name}: ${fmt(g.current_amount)} из ${fmt(g.target_amount)} ${g.currency}`));
      const add = textEl('button', 'Пополнить', 'tiny'); add.addEventListener('click', () => openGoalAddForm(g)); row.appendChild(add);
      box?.appendChild(row);
    });
  }

  function renderSettings(d) {
    setText('inviteCode', d.family?.invite_code || '—');
    setText('familyNameText', d.family?.name || '—');
    setText('familyBaseCurrencyText', d.family?.base_currency || d.summary?.base_currency || '—');
    renderMembers(d.members || [], d.user || {});
    renderSimple('ratesList', d.rates || [], (r) => `1 ${r.currency} = ${fmt(r.rate_to_base)} ${d.family?.base_currency || ''}`);
    if ($('dailyEnabled') && d.notification_settings) $('dailyEnabled').checked = !!Number(d.notification_settings.daily_enabled);
    if ($('budgetAlertEnabled') && d.notification_settings) $('budgetAlertEnabled').checked = !!Number(d.notification_settings.budget_alert_enabled);
    if ($('scheduledPaymentEnabled') && d.notification_settings) $('scheduledPaymentEnabled').checked = !!Number(d.notification_settings.scheduled_payment_enabled);
  }

  function renderMembers(members, user) {
    const box = $('membersList'); clear(box);
    members.forEach((m) => {
      const row = document.createElement('div'); row.className = 'mini-row member-row';
      row.appendChild(textEl('b', `${m.full_name}${m.id === user.id ? ' · это вы' : ''}`));
      const role = document.createElement('select');
      ['admin', 'husband', 'wife', 'member'].forEach((r) => role.appendChild(option(r, r, r === m.role)));
      role.disabled = user.role !== 'admin';
      role.addEventListener('change', () => changeMemberRole(m.id, role.value));
      row.appendChild(role);
      if (user.role === 'admin') {
        const perms = textEl('button', 'Права', 'tiny');
        perms.addEventListener('click', () => openPermissionEditor(m));
        row.appendChild(perms);
      }
      if (user.role === 'admin' && m.id !== user.id) {
        const del = textEl('button', 'Удалить', 'tiny danger');
        del.addEventListener('click', () => removeMember(m.id, m.full_name));
        row.appendChild(del);
      }
      box?.appendChild(row);
    });
  }



  function renderWalletManagement(wallets) {
    const box = $('walletManageList'); clear(box);
    if (!wallets.length) return box?.appendChild(textEl('p', 'Кошельков пока нет', 'empty'));
    wallets.forEach((w) => {
      const row = document.createElement('div'); row.className = 'edit-row';
      const name = document.createElement('input'); name.value = w.name; name.placeholder = 'Название кошелька';
      const includeLabel = document.createElement('label'); includeLabel.className = 'check-row tiny-check';
      const include = document.createElement('input'); include.type = 'checkbox'; include.checked = w.include_in_free_money !== false && Number(w.include_in_free_money ?? 1) === 1;
      includeLabel.append(include, document.createTextNode(' Учитывать в свободных деньгах'));
      row.append(textEl('span', `${fmt(w.balance)} ${w.currency}`, 'muted'), name, includeLabel);
      const save = textEl('button', 'Сохранить', 'tiny'); save.addEventListener('click', () => updateWallet(w.id, name.value, include.checked)); row.appendChild(save);
      const del = textEl('button', 'Удалить', 'tiny danger'); del.addEventListener('click', () => deleteWallet(w.id, w.name)); row.appendChild(del);
      box?.appendChild(row);
    });
  }

  function renderCategoryManagement(categories) {
    const box = $('categoryManageList'); clear(box);
    if (!categories.length) return box?.appendChild(textEl('p', 'Категорий пока нет', 'empty'));
    categories.forEach((c) => {
      const row = document.createElement('div'); row.className = 'edit-row';
      const name = document.createElement('input'); name.value = c.name; name.placeholder = 'Название категории';
      row.append(textEl('span', `${c.type === 'income' ? 'Доход' : 'Расход'}${c.parent_name ? ' / ' + c.parent_name : ''}`, 'muted'), name);
      const save = textEl('button', 'Сохранить', 'tiny'); save.addEventListener('click', () => updateCategory(c.id, name.value)); row.appendChild(save);
      const del = textEl('button', 'Удалить', 'tiny danger'); del.addEventListener('click', () => deleteCategory(c.id, c.name)); row.appendChild(del);
      box?.appendChild(row);
    });
  }

  function renderSchedules(rows) {
    const box = $('scheduleList'); clear(box);
    if (!rows.length) return box?.appendChild(textEl('p', 'Напоминаний пока нет', 'empty'));
    rows.forEach((x) => {
      const row = document.createElement('div'); row.className = 'mini-row';
      row.append(textEl('span', `${x.enabled ? '🔔' : '🔕'} ${x.title}: ${fmt(x.amount)} ${x.currency}, день ${x.due_day}${x.auto_create_expense ? ' · автосписание' : ''}`));
      const toggle = textEl('button', x.enabled ? 'Выключить' : 'Включить', 'tiny'); toggle.addEventListener('click', () => updateSchedule(x.id, { enabled: x.enabled ? 0 : 1 })); row.appendChild(toggle);
      const del = textEl('button', 'Удалить', 'tiny danger'); del.addEventListener('click', () => deleteSchedule(x.id, x.title)); row.appendChild(del);
      box?.appendChild(row);
    });
  }

  function renderFinancialPlan(rows) {
    const box = $('financialPlanList'); clear(box);
    if (!rows.length) return box?.appendChild(textEl('p', 'Финансовый план пока пуст', 'empty'));
    rows.forEach((x) => {
      const row = document.createElement('div'); row.className = 'plan-row';
      row.append(textEl('b', `${x.title} · приоритет ${x.priority}`));
      row.append(textEl('span', `${fmt(x.current_amount)} из ${fmt(x.target_amount)} ${x.currency} · ${x.progress_percent || 0}% ${x.deadline ? '· до ' + x.deadline : ''}`));
      const bar = document.createElement('div'); bar.className = 'progress'; const fill = document.createElement('i'); fill.style.width = `${Math.min(100, Number(x.progress_percent || 0))}%`; bar.appendChild(fill); row.appendChild(bar);
      if (x.note) row.append(textEl('small', x.note));
      const actions = document.createElement('div'); actions.className = 'row-actions';
      const edit = textEl('button', 'Редактировать', 'tiny'); edit.addEventListener('click', () => openPlanEditForm(x)); actions.appendChild(edit);
      const del = textEl('button', 'Удалить', 'tiny danger'); del.addEventListener('click', () => deletePlanItem(x.id, x.title)); actions.appendChild(del);
      row.appendChild(actions);
      box?.appendChild(row);
    });
  }

  function renderQuickExpense(cats) {
    const chips = $('quickExpenseCategories'); const grid = $('quickExpenseCategoryGrid'); clear(chips); clear(grid);
    cats.slice(0, 8).forEach((c) => {
      const chip = textEl('button', c.name, 'chip'); chip.addEventListener('click', () => openQuickExpense(c.id)); chips?.appendChild(chip);
      const btn = textEl('button', c.name, 'quick-cat'); btn.addEventListener('click', () => { state.quickCategoryId = c.id; $$('.quick-cat').forEach((x) => x.classList.remove('active')); btn.classList.add('active'); }); grid?.appendChild(btn);
    });
  }

  function renderDashboard() { /* rendered by summary/charts/forecast */ }

  async function saveTransaction() {
    const res = await request('/api/transactions', { method: 'POST', idempotent: true, body: { type: state.txType, amount: val('amount'), currency: val('currency'), wallet_id: val('wallet'), category_id: val('category'), comment: val('comment') } });
    await finishMutation(res, 'Операция сохранена');
  }
  async function saveTransfer() {
    const res = await request('/api/transfers', { method: 'POST', idempotent: true, body: { from_wallet_id: val('transferFrom'), to_wallet_id: val('transferTo'), amount_from: val('transferAmountFrom'), amount_to: val('transferAmountTo'), comment: val('transferComment') } });
    await finishMutation(res, 'Перевод сохранен');
  }
  async function saveQuickExpense() {
    const categoryId = state.quickCategoryId || state.data?.expense_categories?.[0]?.id;
    const walletId = val('quickExpenseWallet');
    const res = await request('/api/transactions', { method: 'POST', idempotent: true, body: { type: 'expense', amount: val('quickExpenseAmount'), currency: walletCurrency(walletId), wallet_id: walletId, category_id: categoryId, comment: val('quickExpenseComment') } });
    closeQuickExpense(); await finishMutation(res, 'Расход сохранен');
  }
  async function saveDebt() { const res = await request('/api/debts', { method: 'POST', idempotent: true, body: { name: val('debtName'), amount: val('debtAmount'), currency: val('debtCurrency'), comment: val('debtComment') } }); await finishMutation(res, 'Долг добавлен'); }
  async function saveGoal() { const res = await request('/api/goals', { method: 'POST', idempotent: true, body: { name: val('goalName'), target_amount: val('goalTarget'), currency: val('goalCurrency'), deadline: val('goalDeadline') } }); await finishMutation(res, 'Цель добавлена'); }
  async function saveBudget() { const res = await request('/api/budgets', { method: 'POST', idempotent: true, body: { category_id: val('budgetCategory'), month: val('budgetMonth') || currentMonth(), limit_amount: val('budgetLimit'), currency: val('budgetCurrency') } }); await finishMutation(res, 'Лимит сохранен'); }

  async function updateWallet(id, name, include_in_free_money = true) { const res = await request(`/api/wallets/${id}`, { method: 'PUT', idempotent: true, body: { name, include_in_free_money } }); await finishMutation(res, 'Кошелек обновлен'); }
  async function deleteWallet(id, name) { if (!confirm(`Удалить кошелек ${name}?`)) return; const res = await request(`/api/wallets/${id}`, { method: 'DELETE', idempotent: true }); await finishMutation(res, 'Кошелек удален'); }
  async function updateCategory(id, name) { const res = await request(`/api/categories/${id}`, { method: 'PUT', idempotent: true, body: { name } }); await finishMutation(res, 'Категория обновлена'); }
  async function deleteCategory(id, name) { if (!confirm(`Удалить категорию ${name}?`)) return; const res = await request(`/api/categories/${id}`, { method: 'DELETE', idempotent: true }); await finishMutation(res, 'Категория удалена'); }
  async function saveSchedule() { const res = await request('/api/scheduled-payments', { method: 'POST', idempotent: true, body: { title: val('scheduleTitle'), amount: val('scheduleAmount'), currency: val('scheduleCurrency'), due_day: val('scheduleDueDay'), kind: 'expense', wallet_id: val('scheduleWallet'), category_id: val('scheduleCategory'), auto_create_expense: $('scheduleAutoCreate')?.checked } }); await finishMutation(res, 'Повторяющийся платеж добавлен'); }
  async function updateSchedule(id, body) { const res = await request(`/api/scheduled-payments/${id}`, { method: 'PUT', idempotent: true, body }); await finishMutation(res, 'Напоминание обновлено'); }
  async function deleteSchedule(id, title) { if (!confirm(`Удалить напоминание ${title}?`)) return; const res = await request(`/api/scheduled-payments/${id}`, { method: 'DELETE', idempotent: true }); await finishMutation(res, 'Напоминание удалено'); }
  async function savePlanItem() { const res = await request('/api/financial-plan', { method: 'POST', idempotent: true, body: { title: val('planTitle'), target_amount: val('planTarget'), current_amount: val('planCurrent') || 0, currency: val('planCurrency'), priority: val('planPriority'), deadline: val('planDeadline'), note: val('planNote') } }); await finishMutation(res, 'Пункт финансового плана добавлен'); }
  function openPlanEditForm(item) {
    state.activePlanItemId = item.id;
    setText('planEditTitle', `Редактировать: ${item.title}`);
    if ($('editPlanTitle')) $('editPlanTitle').value = item.title || '';
    if ($('editPlanTarget')) $('editPlanTarget').value = item.target_amount || '';
    if ($('editPlanCurrent')) $('editPlanCurrent').value = item.current_amount || '';
    if ($('editPlanCurrency')) $('editPlanCurrency').value = item.currency || 'UZS';
    if ($('editPlanPriority')) $('editPlanPriority').value = String(item.priority || 3);
    if ($('editPlanDeadline')) $('editPlanDeadline').value = item.deadline || '';
    if ($('editPlanNote')) $('editPlanNote').value = item.note || '';
    $('planEditSheet')?.classList.remove('hidden');
  }
  function closePlanEditForm() { $('planEditSheet')?.classList.add('hidden'); state.activePlanItemId = null; }
  async function savePlanEdit() {
    if (!state.activePlanItemId) throw new Error('Пункт финансового плана не выбран');
    const res = await request(`/api/financial-plan/${state.activePlanItemId}`, { method: 'PUT', idempotent: true, body: {
      title: val('editPlanTitle'), target_amount: val('editPlanTarget'), current_amount: val('editPlanCurrent') || 0,
      currency: val('editPlanCurrency'), priority: val('editPlanPriority'), deadline: val('editPlanDeadline'), note: val('editPlanNote')
    } });
    closePlanEditForm(); await finishMutation(res, 'Финансовый план обновлен');
  }
  async function deletePlanItem(id, title) { if (!confirm(`Удалить из плана: ${title}?`)) return; const res = await request(`/api/financial-plan/${id}`, { method: 'DELETE', idempotent: true }); await finishMutation(res, 'Пункт плана удален'); }

  async function saveWallet() { const res = await request('/api/wallets', { method: 'POST', idempotent: true, body: { name: val('newWalletName'), currency: val('newWalletCurrency'), initial_balance: val('newWalletBalance') || 0, include_in_free_money: true } }); await finishMutation(res, 'Кошелек добавлен'); }
  async function saveCategory() { const res = await request('/api/categories', { method: 'POST', idempotent: true, body: { name: val('newCategoryName'), type: val('newCategoryType'), parent_id: val('newCategoryParent') } }); await finishMutation(res, 'Категория добавлена'); }
  async function saveRate() { const res = await request('/api/rates', { method: 'POST', idempotent: true, body: { currency: val('rateCurrency'), rate_to_base: val('rateValue') } }); await finishMutation(res, 'Курс обновлен'); }
  async function saveNotifications() { const res = await request('/api/notification-settings', { method: 'POST', idempotent: true, body: { daily_enabled: $('dailyEnabled')?.checked, budget_alert_enabled: $('budgetAlertEnabled')?.checked, scheduled_payment_enabled: $('scheduledPaymentEnabled')?.checked } }); await finishMutation(res, 'Настройки уведомлений сохранены'); }

  async function loadOperations() {
    const p = new URLSearchParams();
    [['q', 'opSearch'], ['type', 'opType'], ['wallet_id', 'opWallet'], ['category_id', 'opCategory'], ['currency', 'opCurrency'], ['date_from', 'opFrom'], ['date_to', 'opTo']].forEach(([k, id]) => { if (val(id)) p.set(k, val(id)); });
    const data = await request(`/api/operations?${p}`);
    const box = $('operationsList'); clear(box);
    (data.operations || []).forEach((t) => box?.appendChild(txRow(t)));
  }

  async function loadReportsByMonth() {
    const p = new URLSearchParams();
    if (val('reportMonth')) p.set('month', val('reportMonth'));
    if (val('reportFrom')) p.set('date_from', val('reportFrom'));
    if (val('reportTo')) p.set('date_to', val('reportTo'));
    const data = await request(`/api/reports?${p}`);
    state.data = { ...state.data, ...data };
    renderReports(state.data);
  }


  async function renderOfflineQueue() {
    const box = $('offlineQueueList');
    if (!box || !window.FFOffline) return;
    const rows = await window.FFOffline.pending().catch(() => []);
    const conflicts = await window.FFOffline.conflicts().catch(() => []);
    clear(box);
    setText('offlineQueueCount', String(rows.length));
    if (!rows.length) {
      box.appendChild(textEl('p', 'Offline-очередь пуста', 'empty'));
    } else {
      rows.forEach((x) => {
        const row = document.createElement('div'); row.className = x.lastError ? 'history-box conflict' : 'history-box';
        row.appendChild(textEl('b', `${x.method} ${x.path}`));
        row.appendChild(textEl('small', `${x.createdAt} · попыток: ${x.attempts || 0}`));
        if (x.lastError) row.appendChild(textEl('p', `Конфликт/ошибка синхронизации: ${x.lastError}`, 'empty'));
        if (x.lastError) {
          const forget = textEl('button', 'Удалить из очереди', 'tiny danger');
          forget.addEventListener('click', async () => { await window.FFOffline.remove(x.id); await renderOfflineQueue(); });
          row.appendChild(forget);
        }
        box.appendChild(row);
      });
    }
    if (conflicts.length) {
      box.prepend(textEl('h4', `Конфликты синхронизации: ${conflicts.length}`));
    }
  }

  async function syncOfflineQueue() {
    if (!window.FFOffline) return;
    await window.FFOffline.sync({ authHeaders, toast, onDone: loadData });
    await renderOfflineQueue();
  }

  function renderCalendar(calendar) {
    const box = $('calendarList'); if (!box) return;
    clear(box);
    const weeks = calendar.weeks || [];
    if (!weeks.length) return box.appendChild(textEl('p', 'В календаре пока нет событий', 'empty'));
    const grid = document.createElement('div'); grid.className = 'month-grid';
    (calendar.weekdays || ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']).forEach((d) => grid.appendChild(textEl('b', d, 'month-head')));
    weeks.flat().forEach((cell) => {
      const day = document.createElement('div'); day.className = `month-cell ${cell.date ? '' : 'empty-cell'}`;
      day.appendChild(textEl('strong', cell.day || ''));
      (cell.events || []).slice(0, 3).forEach((e) => day.appendChild(textEl('small', `${e.kind === 'scheduled_payment' ? '🔔' : '💸'} ${e.title}: ${fmt(e.amount)}`)));
      if ((cell.events || []).length > 3) day.appendChild(textEl('small', `+${cell.events.length - 3} еще`));
      grid.appendChild(day);
    });
    box.appendChild(grid);
  }

  async function loadCalendar() {
    const month = val('calendarMonth') || currentMonth();
    const data = await request('/api/calendar?month=' + encodeURIComponent(month));
    renderCalendar(data.calendar || {});
  }

  function renderAiAnalysis(analysis) {
    const box = $('aiAnalysisBox'); if (!box) return;
    clear(box);
    if (!analysis) return box.appendChild(textEl('p', 'Выберите месяц и нажмите “Проанализировать”', 'empty'));
    box.appendChild(textEl('h4', `Оценка месяца: ${analysis.score}/100`));
    const addList = (title, arr) => { const section = document.createElement('div'); section.className = 'history-box'; section.appendChild(textEl('b', title)); (arr || []).forEach((x) => section.appendChild(textEl('p', '• ' + x))); box.appendChild(section); };
    addList('Выводы', analysis.insights);
    addList('Риски', analysis.risks);
    addList('Что сделать', analysis.recommended_actions);
    if (analysis.note) box.appendChild(textEl('p', analysis.note, 'empty'));
  }

  async function loadAiAnalysis() {
    const month = val('aiMonth') || currentMonth();
    const data = await request('/api/ai-analysis?month=' + encodeURIComponent(month));
    renderAiAnalysis(data.analysis || null); renderAiRules(data.analysis?.personal_rules || state.data?.ai_rules || []);
  }


  async function payMandatoryPayment(id) {
    const item = (state.data?.mandatory_payments?.items || []).find((x) => String(x.id) === String(id));
    const walletId = item?.wallet_id || val('scheduleWallet') || state.data?.wallets?.[0]?.id;
    const categoryId = item?.category_id || val('scheduleCategory') || state.data?.expense_categories?.[0]?.id;
    const res = await request(`/api/mandatory-payments/${id}/pay`, { method: 'POST', idempotent: true, body: { wallet_id: walletId, category_id: categoryId } });
    await finishMutation(res, 'Обязательный платеж оплачен');
  }
  async function markMandatoryZero(id) {
    const item = (state.data?.mandatory_payments?.items || []).find((x) => String(x.id) === String(id));
    const walletId = item?.wallet_id || val('scheduleWallet') || state.data?.wallets?.[0]?.id;
    const categoryId = item?.category_id || val('scheduleCategory') || state.data?.expense_categories?.[0]?.id;
    if (!confirm('Создать служебную отметку 0 без повторного списания?')) return;
    const res = await request(`/api/mandatory-payments/${id}/mark-paid`, { method: 'POST', idempotent: true, body: { wallet_id: walletId, category_id: categoryId, zero_note: true } });
    await finishMutation(res, 'Платеж отмечен без повторного списания');
  }
  async function linkMandatoryExisting(id) {
    const month = val('mandatoryMonth') || currentMonth();
    const data = await request(`/api/mandatory-payments/${id}/linkable-transactions?month=${encodeURIComponent(month)}`);
    const rows = data.transactions || [];
    if (!rows.length) return err('Нет подходящих ручных расходов для привязки');
    const box = $('mandatoryPaymentsBox');
    const panel = document.createElement('div'); panel.className = 'history-box';
    panel.appendChild(textEl('b', 'Выберите ручную операцию для привязки без повторного списания'));
    rows.forEach((t) => {
      const row = document.createElement('div'); row.className = 'mini-row';
      row.appendChild(textEl('span', `#${t.id}: ${fmt(t.amount)} ${t.currency} · ${t.wallet_name || ''} · ${t.category_name || ''} · ${t.comment || ''}`));
      const btn = document.createElement('button'); btn.className = 'tiny-btn'; btn.textContent = 'Связать';
      btn.onclick = async () => { const res = await request(`/api/mandatory-payments/${id}/link-existing`, { method: 'POST', idempotent: true, body: { transaction_id: t.id, month } }); await finishMutation(res, 'Операция привязана к обязательному платежу без повторного списания'); };
      row.appendChild(btn); panel.appendChild(row);
    });
    box?.prepend(panel);
  }

  function renderMandatoryPayments(data) {
    const box = $('mandatoryPaymentsBox'); if (!box) return;
    clear(box);
    box.appendChild(textEl('h4', `${data.month || currentMonth()}: оплачено ${data.paid_count || 0}/${data.total_count || 0}, осталось ${fmt(data.left_amount)} из ${fmt(data.total_amount)}`));
    const groups = [
      ['Просроченные платежи', data.overdue || [], 'danger-line'],
      ['Будущие платежи', data.upcoming || [], ''],
      ['Оплаченные платежи', data.paid || [], 'ok-line'],
    ];
    if (!(data.items || []).length) return box.appendChild(textEl('p', 'Обязательных платежей пока нет', 'empty'));
    groups.forEach(([title, rows, cls]) => {
      const section = document.createElement('div'); section.className = 'history-box';
      section.appendChild(textEl('b', `${title}: ${rows.length}`));
      if (!rows.length) section.appendChild(textEl('p', 'Нет', 'empty'));
      rows.forEach((x) => {
        const row = document.createElement('div'); row.className = `mini-row ${cls}`.trim();
        row.appendChild(textEl('span', `${x.paid ? '✅' : (x.status === 'overdue' ? '🔴' : '⏳')} ${x.title} — ${fmt(x.amount)} ${x.currency}, день ${x.due_day}${x.auto_create_expense ? ' · автосписание' : ''}`));
        if (!x.paid && hasPerm('manage_schedules')) {
          const pay = document.createElement('button'); pay.className = 'tiny-btn'; pay.textContent = 'Оплатить обязательный платеж'; pay.onclick = () => payMandatoryPayment(x.id).catch((e) => err(e.message));
          const link = document.createElement('button'); link.className = 'tiny-btn'; link.textContent = 'Связать с существующей операцией'; link.onclick = () => linkMandatoryExisting(x.id).catch((e) => err(e.message));
          const mark = document.createElement('button'); mark.className = 'tiny-btn'; mark.textContent = 'Отметить без списания'; mark.onclick = () => markMandatoryZero(x.id).catch((e) => err(e.message));
          row.appendChild(pay); row.appendChild(link); row.appendChild(mark);
        }
        section.appendChild(row);
      });
      box.appendChild(section);
    });
  }
  async function loadMandatoryPayments() {
    const month = val('mandatoryMonth') || currentMonth();
    const data = await request('/api/mandatory-payments?month=' + encodeURIComponent(month));
    renderMandatoryPayments(data.mandatory_payments || {});
  }


  async function retryScheduledPayment(id) { const res = await request(`/api/scheduled-payments/${id}/retry`, { method: 'POST', idempotent: true, body: {} }); await finishMutation(res, 'Автоплатеж повторен'); }
  async function disableScheduledAuto(id) { const res = await request(`/api/scheduled-payments/${id}/disable-auto`, { method: 'POST', idempotent: true, body: {} }); await finishMutation(res, 'Автосписание отключено'); }
  async function changeIssueWallet(id, selectId) { const walletId = val(selectId); if (!walletId) return err('Выберите кошелек'); const res = await request(`/api/scheduled-payments/${id}`, { method: 'PUT', idempotent: true, body: { wallet_id: walletId } }); await finishMutation(res, 'Кошелек автоплатежа изменен'); }
  async function changeIssueCategory(id, selectId) { const categoryId = val(selectId); if (!categoryId) return err('Выберите категорию'); const res = await request(`/api/scheduled-payments/${id}`, { method: 'PUT', idempotent: true, body: { category_id: categoryId } }); await finishMutation(res, 'Категория автоплатежа изменена'); }
  async function resolveScheduledIssue(issueId) { const res = await request(`/api/scheduled-payment-issues/${issueId}/resolve`, { method: 'POST', idempotent: true, body: {} }); await finishMutation(res, 'Ошибка скрыта как решенная'); }

  function renderScheduledIssues(rows) {
    const box = $('scheduledIssuesBox'); if (!box) return;
    clear(box);
    if (!rows.length) return box.appendChild(textEl('p', 'Ошибок автоплатежей пока нет', 'empty'));
    rows.forEach((x, idx) => {
      const sid = x.schedule_id || x.entity_id;
      const title = x.title || `Платеж #${sid || ''}`;
      const row = document.createElement('div'); row.className = 'mini-row danger-line';
      row.appendChild(textEl('span', `⚠️ ${title}: ${x.details || 'ошибка'} · ${x.created_at || ''}`));
      if (sid && hasPerm('manage_schedules')) {
        const retry = document.createElement('button'); retry.className = 'tiny-btn'; retry.textContent = 'Повторить'; retry.onclick = () => retryScheduledPayment(sid).catch((e) => err(e.message));
        const disable = document.createElement('button'); disable.className = 'tiny-btn'; disable.textContent = 'Отключить автосписание'; disable.onclick = () => disableScheduledAuto(sid).catch((e) => err(e.message));
        const select = document.createElement('select'); select.id = `issueWallet${idx}`; (state.data?.wallets || []).forEach((w) => { const opt = document.createElement('option'); opt.value = w.id; opt.textContent = `${w.name} · ${w.balance} ${w.currency}`; select.appendChild(opt); });
        const change = document.createElement('button'); change.className = 'tiny-btn'; change.textContent = 'Изменить кошелек'; change.onclick = () => changeIssueWallet(sid, select.id).catch((e) => err(e.message));
        const catSelect = document.createElement('select'); catSelect.id = `issueCategory${idx}`; (state.data?.expense_categories || []).forEach((c) => { const opt = document.createElement('option'); opt.value = c.id; opt.textContent = c.name; catSelect.appendChild(opt); });
        const changeCat = document.createElement('button'); changeCat.className = 'tiny-btn'; changeCat.textContent = 'Изменить категорию'; changeCat.onclick = () => changeIssueCategory(sid, catSelect.id).catch((e) => err(e.message));
        const resolve = document.createElement('button'); resolve.className = 'tiny-btn'; resolve.textContent = 'Скрыть как решенную'; resolve.onclick = () => resolveScheduledIssue(x.id).catch((e) => err(e.message));
        row.appendChild(retry); row.appendChild(select); row.appendChild(change); row.appendChild(catSelect); row.appendChild(changeCat); row.appendChild(disable); row.appendChild(resolve);
      }
      box.appendChild(row);
    });
  }
  async function loadScheduledIssues() {
    const data = await request('/api/scheduled-payment-issues');
    renderScheduledIssues(data.issues || []);
  }

  function renderMonthEndMoney(data) {
    const box = $('monthEndMoneyBox'); if (!box) return;
    clear(box);
    if (!data || !data.month) return box.appendChild(textEl('p', 'Нажмите “Рассчитать”, чтобы увидеть остаток до конца месяца', 'empty'));
    const cls = Number(data.free_after_mandatory || 0) < 0 ? 'history-box danger-line' : 'history-box';
    const top = document.createElement('div'); top.className = cls;
    top.appendChild(textEl('h4', `${data.month}: свободно после обязательных и переменных расходов ${fmt(data.free_after_mandatory_and_variable ?? data.free_after_mandatory)} ${data.base_currency || ''}`));
    top.appendChild(textEl('p', `Всего в кошельках для свободных денег: ${fmt(data.wallet_total_base)} ${data.base_currency || ''}`));
    top.appendChild(textEl('p', `Осталось обязательных платежей: ${fmt(data.mandatory_left_base)} ${data.base_currency || ''}`));
    top.appendChild(textEl('p', `Прогноз переменных расходов до конца месяца: ${fmt(data.variable_forecast_left_base || 0)} ${data.base_currency || ''}`));
    top.appendChild(textEl('p', `Дней до конца месяца: ${data.days_left}. Дневной лимит: ${fmt(data.daily_allowance)} ${data.base_currency || ''}`));
    box.appendChild(top);
    const rec = document.createElement('div'); rec.className = 'history-box'; rec.appendChild(textEl('b', 'Рекомендации'));
    (data.recommendations || []).forEach((x) => rec.appendChild(textEl('p', '• ' + x)));
    box.appendChild(rec);
    const overdue = data.overdue_mandatory_items || [];
    const upcoming = data.upcoming_mandatory_items || [];
    const addGroup = (title, rows, icon, cls = '') => {
      if (!rows.length) return;
      const list = document.createElement('div'); list.className = `history-box ${cls}`.trim(); list.appendChild(textEl('b', title));
      rows.forEach((x) => list.appendChild(textEl('p', `${icon} ${x.title}: ${fmt(x.left_amount || x.amount)} ${x.currency}, день ${x.due_day}`)));
      box.appendChild(list);
    };
    addGroup('Просрочено и еще не оплачено', overdue, '🔴', 'danger-line');
    addGroup('Что еще оплатить впереди', upcoming, '⏳');
  }
  async function loadMonthEndMoney() {
    const month = val('moneyMonth') || currentMonth();
    const data = await request('/api/month-end-money?month=' + encodeURIComponent(month));
    renderMonthEndMoney(data.month_end_money || {});
  }

  function renderAiRules(rows) {
    const box = $('aiRulesList'); if (!box) return;
    clear(box);
    if (!rows.length) return box.appendChild(textEl('p', 'Персональные правила пока не заданы', 'empty'));
    rows.forEach((r) => {
      const row = document.createElement('div'); row.className = 'mini-row';
      row.appendChild(textEl('span', `${r.enabled ? '✅' : '⛔'} ${r.title}: ${r.rule_type} ${fmt(r.threshold_amount)} ${r.currency}${r.category_name ? ' · ' + r.category_name : ''}`));
      const del = textEl('button', 'Удалить', 'tiny danger'); del.addEventListener('click', () => deleteAiRule(r.id)); row.appendChild(del);
      box.appendChild(row);
    });
  }
  async function saveAiRule() {
    const res = await request('/api/ai-rules', { method: 'POST', idempotent: true, body: { title: val('aiRuleTitle'), rule_type: val('aiRuleType'), category_id: val('aiRuleCategory'), threshold_amount: val('aiRuleThreshold'), currency: val('aiRuleCurrency'), enabled: true } });
    await finishMutation(res, 'AI-правило добавлено');
  }
  async function deleteAiRule(id) { if (!confirm('Удалить AI-правило?')) return; const res = await request(`/api/ai-rules/${id}`, { method: 'DELETE', idempotent: true }); await finishMutation(res, 'AI-правило удалено'); }

  function renderBudgetWizard(data) {
    const box = $('budgetWizardBox'); if (!box) return;
    clear(box);
    const profile = data.profile;
    if (profile) {
      if ($('wizardIncome')) $('wizardIncome').value = profile.monthly_income || '';
      if ($('wizardCurrency')) $('wizardCurrency').value = profile.base_currency || 'UZS';
      if ($('wizardRent')) $('wizardRent').value = profile.rent_amount || '';
      if ($('wizardKindergarten')) $('wizardKindergarten').value = profile.kindergarten_amount || '';
      if ($('wizardInstallment')) $('wizardInstallment').value = profile.installment_amount || '';
      if ($('wizardFood')) $('wizardFood').value = profile.food_amount || '';
      if ($('wizardTransport')) $('wizardTransport').value = profile.transport_amount || '';
      if ($('wizardSavings')) $('wizardSavings').value = profile.savings_target_percent || 10;
    }
    (data.recommendations || []).forEach((r) => box.appendChild(textEl('div', `${r.title}: ${fmt(r.amount)} · ${r.note}`, 'mini-row')));
  }
  async function saveBudgetWizard() {
    const res = await request('/api/budget-wizard', { method: 'POST', idempotent: true, body: { monthly_income: val('wizardIncome'), base_currency: val('wizardCurrency'), rent_amount: val('wizardRent'), kindergarten_amount: val('wizardKindergarten'), installment_amount: val('wizardInstallment'), food_amount: val('wizardFood'), transport_amount: val('wizardTransport'), savings_target_percent: val('wizardSavings') || 10 } });
    await finishMutation(res, 'Мастер бюджета сохранен');
  }

  function renderPermissionEditor(member, data) {
    const box = $('permissionEditor'); if (!box) return;
    clear(box);
    box.appendChild(textEl('h4', `Права: ${member.full_name}`));
    (data.all_permissions || []).forEach((perm) => {
      const label = document.createElement('label'); label.className = 'check-row';
      const cb = document.createElement('input'); cb.type = 'checkbox'; cb.value = perm; cb.checked = (data.effective_permissions || []).includes(perm);
      label.append(cb, document.createTextNode(' ' + perm)); box.appendChild(label);
    });
    const save = textEl('button', 'Сохранить права', 'small-submit');
    save.addEventListener('click', async () => {
      const permissions = Array.from(box.querySelectorAll('input[type="checkbox"]:checked')).map((x) => x.value);
      const res = await request(`/api/family/member/${member.id}/permissions`, { method: 'POST', idempotent: true, body: { permissions } });
      await finishMutation(res, 'Права участника обновлены');
    });
    box.appendChild(save);
  }

  async function openPermissionEditor(member) {
    const data = await request(`/api/family/member/${member.id}/permissions`);
    renderPermissionEditor(member, data);
  }

  async function loadAudit(target = 'settings') {
    const prefix = target === 'page' ? 'auditPage_' : 'audit_';
    const out = target === 'page' ? $('auditPageList') : $('auditList');
    const p = new URLSearchParams();
    ['action', 'entity_type', 'entity_id', 'user_id', 'date_from', 'date_to'].forEach((k) => { if (val(prefix + k)) p.set(k, val(prefix + k)); });
    const data = await request(`/api/audit-logs?${p}`);
    clear(out);
    (data.audit_logs || []).forEach((h) => out?.appendChild(textEl('div', `${h.created_at} · ${h.user_name || ''} · ${h.action} · ${h.entity_type || ''}#${h.entity_id || ''} · ${h.details || ''}`, 'history-box')));
  }

  async function showOperationHistory(id) { await loadAudit('page'); showPage('audit'); }
  async function deleteTransaction(id) { if (!confirm('Удалить операцию?')) return; const res = await request(`/api/transactions/${id}`, { method: 'DELETE', idempotent: true }); await finishMutation(res, 'Операция удалена'); if (!res?.offline_queued) await loadOperations(); }
  function openDebtPayForm(debt) {
    state.activeDebtId = debt.id;
    setText('debtPayTitle', `Погасить: ${debt.name}`);
    setText('debtPayLeft', `Осталось: ${fmt(debt.left_amount)} ${debt.currency}`);
    if ($('debtPayAmount')) $('debtPayAmount').value = '';
    $('debtPaySheet')?.classList.remove('hidden');
  }
  function closeDebtPayForm() { $('debtPaySheet')?.classList.add('hidden'); state.activeDebtId = null; }
  async function payDebt() {
    if (!state.activeDebtId) throw new Error('Долг не выбран');
    const res = await request('/api/debts/pay', { method: 'POST', idempotent: true, body: { debt_id: state.activeDebtId, amount: val('debtPayAmount'), wallet_id: val('debtPayWallet') } });
    closeDebtPayForm(); await finishMutation(res, 'Платеж по долгу сохранен');
  }
  function openGoalAddForm(goal) {
    state.activeGoalId = goal.id;
    setText('goalAddTitle', `Пополнить: ${goal.name}`);
    setText('goalAddProgress', `Накоплено: ${fmt(goal.current_amount)} из ${fmt(goal.target_amount)} ${goal.currency}`);
    if ($('goalAddAmount')) $('goalAddAmount').value = '';
    $('goalAddSheet')?.classList.remove('hidden');
  }
  function closeGoalAddForm() { $('goalAddSheet')?.classList.add('hidden'); state.activeGoalId = null; }
  async function addGoalMoney() {
    if (!state.activeGoalId) throw new Error('Цель не выбрана');
    const res = await request('/api/goals/add', { method: 'POST', idempotent: true, body: { goal_id: state.activeGoalId, amount: val('goalAddAmount'), wallet_id: val('goalAddWallet') } });
    closeGoalAddForm(); await finishMutation(res, 'Цель пополнена');
  }
  async function changeMemberRole(memberId, role) { const res = await request('/api/family/member/role', { method: 'POST', idempotent: true, body: { member_id: memberId, role } }); await finishMutation(res, 'Роль обновлена'); }
  async function removeMember(memberId, name) { if (!confirm(`Удалить участника ${name}?`)) return; const res = await request('/api/family/member/remove', { method: 'POST', idempotent: true, body: { member_id: memberId } }); await finishMutation(res, 'Участник удален'); }
  async function joinFamily() { const res = await request('/api/family/join', { method: 'POST', idempotent: true, body: { invite_code: val('joinCode'), role: val('joinRole') } }); await finishMutation(res, 'Вы присоединились к семье'); }
  async function deleteAccount() { await request('/api/account', { method: 'DELETE', idempotent: true, body: { confirm: val('deleteAccountConfirm') } }); toast('Аккаунт удален'); }
  async function deleteFamily() { await request('/api/family', { method: 'DELETE', idempotent: true, body: { confirm: val('deleteFamilyConfirm') } }); toast('Семья удалена'); }

  function openQuickExpense(categoryId = null) { state.quickCategoryId = categoryId; $('quickExpenseSheet')?.classList.remove('hidden'); }
  function closeQuickExpense() { $('quickExpenseSheet')?.classList.add('hidden'); state.quickCategoryId = null; }

  function showPage(page) {
    $$('main[id^="page"]').forEach((m) => m.classList.toggle('hidden', m.id !== `page${page[0].toUpperCase()}${page.slice(1)}`));
    $$('[data-page]').forEach((b) => b.classList.toggle('active', b.dataset.page === page));
    if (page === 'operations') loadOperations().catch((e) => err(e.message));
    if (page === 'audit') loadAudit('page').catch((e) => err(e.message));
    if (page === 'calendar') loadCalendar().catch((e) => err(e.message));
    if (page === 'ai') loadAiAnalysis().catch((e) => err(e.message));
    if (page === 'mandatory') loadMandatoryPayments().catch((e) => err(e.message));
    if (page === 'money') loadMonthEndMoney().catch((e) => err(e.message));
  }

  function bind(id, event, fn) { const el = $(id); if (el) el.addEventListener(event, fn); }

  function bindEvents() {
    tg?.ready?.(); tg?.expand?.();
    $$('[data-page]').forEach((b) => b.addEventListener('click', () => showPage(b.dataset.page)));
    bind('incomeBtn', 'click', () => { state.txType = 'income'; $('incomeBtn')?.classList.add('active'); $('expenseBtn')?.classList.remove('active'); renderSelects(state.data || {}); });
    bind('expenseBtn', 'click', () => { state.txType = 'expense'; $('expenseBtn')?.classList.add('active'); $('incomeBtn')?.classList.remove('active'); renderSelects(state.data || {}); });
    bind('wallet', 'change', () => syncCurrencyWithWallet());
    bind('saveTransactionBtn', 'click', () => withBusy('saveTransactionBtn', saveTransaction));
    bind('saveTransferBtn', 'click', () => withBusy('saveTransferBtn', saveTransfer));
    bind('saveQuickExpenseBtn', 'click', () => withBusy('saveQuickExpenseBtn', saveQuickExpense));
    bind('saveDebtBtn', 'click', () => withBusy('saveDebtBtn', saveDebt));
    bind('saveDebtPaymentBtn', 'click', () => withBusy('saveDebtPaymentBtn', payDebt));
    bind('closeDebtPayBtn', 'click', closeDebtPayForm);
    bind('saveGoalBtn', 'click', () => withBusy('saveGoalBtn', saveGoal));
    bind('saveGoalContributionBtn', 'click', () => withBusy('saveGoalContributionBtn', addGoalMoney));
    bind('closeGoalAddBtn', 'click', closeGoalAddForm);
    bind('saveBudgetBtn', 'click', () => withBusy('saveBudgetBtn', saveBudget));
    bind('createWalletBtn', 'click', () => withBusy('createWalletBtn', saveWallet));
    bind('createCategoryBtn', 'click', () => withBusy('createCategoryBtn', saveCategory));
    bind('saveRateBtn', 'click', () => withBusy('saveRateBtn', saveRate));
    bind('saveNotificationSettingsBtn', 'click', () => withBusy('saveNotificationSettingsBtn', saveNotifications));
    bind('saveScheduleBtn', 'click', () => withBusy('saveScheduleBtn', saveSchedule));
    bind('savePlanBtn', 'click', () => withBusy('savePlanBtn', savePlanItem));
    bind('savePlanEditBtn', 'click', () => withBusy('savePlanEditBtn', savePlanEdit));
    bind('closePlanEditBtn', 'click', closePlanEditForm);
    bind('loadOperationsBtn', 'click', () => loadOperations().catch((e) => err(e.message)));
    bind('loadReportsBtn', 'click', () => loadReportsByMonth().catch((e) => err(e.message)));
    bind('loadAuditFilteredBtn', 'click', () => loadAudit('settings').catch((e) => err(e.message)));
    bind('loadAuditPageBtn', 'click', () => loadAudit('page').catch((e) => err(e.message)));
    bind('loadCalendarBtn', 'click', () => loadCalendar().catch((e) => err(e.message)));
    bind('loadAiBtn', 'click', () => loadAiAnalysis().catch((e) => err(e.message)));
    bind('loadMandatoryBtn', 'click', () => loadMandatoryPayments().catch((e) => err(e.message)));
    bind('loadMoneyBtn', 'click', () => loadMonthEndMoney().catch((e) => err(e.message)));
    bind('loadScheduleIssuesBtn', 'click', () => loadScheduledIssues().catch((e) => err(e.message)));
    bind('saveAiRuleBtn', 'click', () => withBusy('saveAiRuleBtn', saveAiRule));
    bind('saveWizardBtn', 'click', () => withBusy('saveWizardBtn', saveBudgetWizard));
    bind('syncOfflineBtn', 'click', () => syncOfflineQueue().catch((e) => err(e.message)));
    bind('joinFamilyBtn', 'click', () => withBusy('joinFamilyBtn', joinFamily));
    bind('deleteAccountBtn', 'click', () => withBusy('deleteAccountBtn', deleteAccount));
    bind('deleteFamilyBtn', 'click', () => withBusy('deleteFamilyBtn', deleteFamily));
    bind('openQuickExpenseBtn', 'click', () => openQuickExpense()); bind('fabExpense', 'click', () => openQuickExpense()); bind('closeQuickExpenseBtn', 'click', closeQuickExpense);
    $$('[data-sheet-close="quickExpenseSheet"]').forEach((el) => el.addEventListener('click', closeQuickExpense));
    $$('[data-sheet-close="debtPaySheet"]').forEach((el) => el.addEventListener('click', closeDebtPayForm));
    $$('[data-sheet-close="goalAddSheet"]').forEach((el) => el.addEventListener('click', closeGoalAddForm));
    $$('[data-sheet-close="planEditSheet"]').forEach((el) => el.addEventListener('click', closePlanEditForm));
    bind('dismissOnboardingBtn', 'click', () => { localStorage.setItem('ff_onboarding_hidden', '1'); $('onboardingCard')?.classList.add('hidden'); });
    bind('downloadPdfBtn', 'click', () => downloadFile('/api/report.pdf?month=' + encodeURIComponent(val('reportMonth') || currentMonth()), `family_report_${val('reportMonth') || currentMonth()}.pdf`).catch((e) => err(e.message)));
    bind('exportExcelBtn', 'click', (e) => { e.preventDefault(); downloadFile('/api/export.xlsx?month=' + encodeURIComponent(val('reportMonth') || currentMonth()), `family_finance_${val('reportMonth') || currentMonth()}.xlsx`).catch((er) => err(er.message)); });
  }

  document.addEventListener('DOMContentLoaded', async () => {
    bindEvents();
    if (localStorage.getItem('ff_onboarding_hidden') === '1') $('onboardingCard')?.classList.add('hidden');
    window.addEventListener('online', () => syncOfflineQueue().catch((e) => err(e.message)));
    window.addEventListener('ff-offline-queued', () => renderOfflineQueue());
    try { await loadData(); }
    catch (e) { err(e.message); }
  });
})();
