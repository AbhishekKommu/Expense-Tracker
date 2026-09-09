// Dashboard logic: fetches expenses from the REST API, renders the ledger
// into the DOM, and wires up create / update / delete / filter / logout.

const CATEGORY_ICONS = {
  Food: '🍽️', Transport: '🚗', Housing: '🏠', Utilities: '💡',
  Health: '💊', Entertainment: '🎬', Shopping: '🛍️', Education: '📚', Other: '📎',
};

const state = { expenses: [], editingId: null };

const els = {
  form: document.getElementById('expenseForm'),
  title: document.getElementById('title'),
  amount: document.getElementById('amount'),
  date: document.getElementById('date'),
  category: document.getElementById('category'),
  note: document.getElementById('note'),
  expenseId: document.getElementById('expenseId'),
  submitBtn: document.getElementById('submitBtn'),
  cancelEditBtn: document.getElementById('cancelEditBtn'),
  formTitle: document.getElementById('formTitle'),
  ledgerList: document.getElementById('ledgerList'),
  categoryFilter: document.getElementById('categoryFilter'),
  summaryTotal: document.getElementById('summaryTotal'),
  summaryCount: document.getElementById('summaryCount'),
  summaryTopCat: document.getElementById('summaryTopCat'),
  summaryTopCatAmt: document.getElementById('summaryTopCatAmt'),
  summaryAvg: document.getElementById('summaryAvg'),
  logoutBtn: document.getElementById('logoutBtn'),
  toast: document.getElementById('toast'),
};

function money(n) {
  return '₹' + Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function showToast(message, type = 'success') {
  els.toast.textContent = message;
  els.toast.className = 'toast show ' + type;
  setTimeout(() => { els.toast.className = 'toast'; }, 2600);
}

function formatDate(iso) {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

// ---------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------
async function apiRequest(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (res.status === 401) {
    window.location.href = '/login';
    return null;
  }
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, data };
}

async function fetchExpenses() {
  const category = els.categoryFilter.value;
  const url = category && category !== 'All'
    ? `/api/expenses?category=${encodeURIComponent(category)}`
    : '/api/expenses';
  const result = await apiRequest(url);
  if (!result) return;
  if (result.ok) {
    state.expenses = result.data.expenses;
    renderLedger();
    renderSummary(result.data);
  } else {
    showToast(result.data.error || 'Could not load expenses', 'error');
  }
}

async function createExpense(payload) {
  const result = await apiRequest('/api/expenses', { method: 'POST', body: JSON.stringify(payload) });
  if (!result) return;
  if (result.ok) {
    showToast('Expense added');
    resetForm();
    fetchExpenses();
  } else {
    showToast(result.data.error || 'Could not add expense', 'error');
  }
}

async function updateExpense(id, payload) {
  const result = await apiRequest(`/api/expenses/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
  if (!result) return;
  if (result.ok) {
    showToast('Expense updated');
    resetForm();
    fetchExpenses();
  } else {
    showToast(result.data.error || 'Could not update expense', 'error');
  }
}

async function deleteExpense(id) {
  const result = await apiRequest(`/api/expenses/${id}`, { method: 'DELETE' });
  if (!result) return;
  if (result.ok) {
    showToast('Expense deleted');
    fetchExpenses();
  } else {
    showToast(result.data.error || 'Could not delete expense', 'error');
  }
}

// ---------------------------------------------------------------------
// DOM rendering
// ---------------------------------------------------------------------
function renderLedger() {
  els.ledgerList.innerHTML = '';

  if (state.expenses.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.innerHTML = `<div class="glyph">🗒️</div><div>No expenses logged yet. Add your first one on the left.</div>`;
    els.ledgerList.appendChild(empty);
    return;
  }

  state.expenses.forEach((exp) => {
    const row = document.createElement('div');
    row.className = 'ledger-row';

    const badge = document.createElement('div');
    badge.className = 'cat-badge';
    badge.textContent = CATEGORY_ICONS[exp.category] || '📎';

    const info = document.createElement('div');
    info.className = 'ledger-info';
    const titleEl = document.createElement('div');
    titleEl.className = 'title';
    titleEl.textContent = exp.title;
    const metaEl = document.createElement('div');
    metaEl.className = 'meta';
    metaEl.textContent = `${exp.category} · ${formatDate(exp.date)}${exp.note ? ' · ' + exp.note : ''}`;
    info.appendChild(titleEl);
    info.appendChild(metaEl);

    const amountEl = document.createElement('div');
    amountEl.className = 'ledger-amount mono';
    amountEl.textContent = '−' + money(exp.amount);

    const actions = document.createElement('div');
    actions.className = 'ledger-actions';
    const editBtn = document.createElement('button');
    editBtn.title = 'Edit';
    editBtn.textContent = '✎';
    editBtn.addEventListener('click', () => startEdit(exp));
    const delBtn = document.createElement('button');
    delBtn.title = 'Delete';
    delBtn.textContent = '🗑';
    delBtn.addEventListener('click', () => {
      if (confirm(`Delete "${exp.title}"?`)) deleteExpense(exp.id);
    });
    actions.appendChild(editBtn);
    actions.appendChild(delBtn);

    row.appendChild(badge);
    row.appendChild(info);
    row.appendChild(amountEl);
    row.appendChild(actions);
    els.ledgerList.appendChild(row);
  });
}

function renderSummary(data) {
  els.summaryTotal.textContent = money(data.total);
  els.summaryCount.textContent = `${data.count} ${data.count === 1 ? 'entry' : 'entries'}`;

  const byCat = data.by_category || {};
  const catEntries = Object.entries(byCat);
  if (catEntries.length === 0) {
    els.summaryTopCat.textContent = '—';
    els.summaryTopCatAmt.textContent = 'No expenses yet';
  } else {
    catEntries.sort((a, b) => b[1] - a[1]);
    const [topCat, topAmt] = catEntries[0];
    els.summaryTopCat.textContent = topCat;
    els.summaryTopCatAmt.textContent = money(topAmt) + ' spent';
  }

  const avg = data.count > 0 ? data.total / data.count : 0;
  els.summaryAvg.textContent = money(avg);
}

// ---------------------------------------------------------------------
// Form handling (create / edit)
// ---------------------------------------------------------------------
function startEdit(exp) {
  state.editingId = exp.id;
  els.expenseId.value = exp.id;
  els.title.value = exp.title;
  els.amount.value = exp.amount;
  els.date.value = exp.date;
  els.category.value = exp.category;
  els.note.value = exp.note || '';
  els.formTitle.textContent = 'Edit expense';
  els.submitBtn.textContent = 'Save changes';
  els.cancelEditBtn.style.display = 'inline-block';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function resetForm() {
  state.editingId = null;
  els.form.reset();
  els.expenseId.value = '';
  els.date.value = new Date().toISOString().slice(0, 10);
  els.formTitle.textContent = 'Add an expense';
  els.submitBtn.textContent = 'Add expense';
  els.cancelEditBtn.style.display = 'none';
}

els.form.addEventListener('submit', (e) => {
  e.preventDefault();
  const payload = {
    title: els.title.value.trim(),
    amount: parseFloat(els.amount.value),
    date: els.date.value,
    category: els.category.value,
    note: els.note.value.trim(),
  };
  if (state.editingId) {
    updateExpense(state.editingId, payload);
  } else {
    createExpense(payload);
  }
});

els.cancelEditBtn.addEventListener('click', resetForm);
els.categoryFilter.addEventListener('change', fetchExpenses);

els.logoutBtn.addEventListener('click', async () => {
  await fetch('/api/logout', { method: 'POST' });
  window.location.href = '/login';
});

// ---------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------
els.date.value = new Date().toISOString().slice(0, 10);
fetchExpenses();