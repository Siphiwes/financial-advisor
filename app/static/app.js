"use strict";

(() => {
  const state = { token: null, user: null, accounts: [], categories: [], file: null, previewed: false };
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const today = () => {
    const d = new Date();
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  };
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[c]);
  const money = (v, currency) => {
    const n = Number(v || 0);
    try { return new Intl.NumberFormat("en-ZA", { style: "currency", currency: currency || "ZAR" }).format(n); }
    catch { return String(v); }
  };
  function say(message, kind) {
    const n = $("#notice");
    n.textContent = message;
    n.className = "notice " + (kind || "");
    n.hidden = false;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  function formObject(form) {
    return Object.fromEntries(new FormData(form).entries());
  }
  async function api(path, options) {
    options = options || {};
    const headers = new Headers(options.headers || {});
    if (state.token) headers.set("Authorization", "Bearer " + state.token);
    if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
    const response = await fetch(path, { ...options, headers, cache: "no-store" });
    if (response.status === 204) return null;
    const type = response.headers.get("content-type") || "";
    const payload = type.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = payload && typeof payload === "object" ? payload.detail : payload;
      throw new Error(detail || "Request failed (" + response.status + ").");
    }
    return payload;
  }
  const send = (path, data, method, headers) => api(path, {
    method: method || "POST",
    headers: headers || {},
    body: JSON.stringify(data)
  });
  function showError(error) { say(error && error.message ? error.message : "Unexpected error.", "error"); }
  function activate(name) {
    $$(".workspace-section").forEach((s) => { s.hidden = s.dataset.panel !== name; });
    $$(".nav-link").forEach((b) => b.classList.toggle("active", b.dataset.section === name));
    const loaders = {
      dashboard: loadDashboard, accounts: loadAccounts, transactions: loadTransactions,
      imports: loadImports, planning: loadPlanning, categories: loadCategories, advisor: loadConsent
    };
    if (loaders[name]) loaders[name]().catch(showError);
  }
  async function signIn(token) {
    state.token = token;
    try {
      state.user = await api("/auth/me");
      $("#auth-panel").hidden = true;
      $("#app-panel").hidden = false;
      $("#account-strip").hidden = false;
      $("#signed-in-user").textContent = state.user.email;
      await Promise.all([loadAccounts(), loadCategories()]);
      await loadDashboard();
      say("Signed in. Your session token is held in memory and is cleared when you sign out or reload.", "success");
    } catch (error) {
      state.token = null;
      throw error;
    }
  }
  function dates() {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    const fmt = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
    $("#summary-from").value = fmt(start);
    $("#summary-to").value = fmt(end);
    $("#transaction-filter").elements.from_date.value = fmt(start);
    $("#transaction-filter").elements.to_date.value = fmt(end);
    $("#budget-form").elements.period.value = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0");
    $("#budget-progress-period").value = $("#budget-form").elements.period.value;
    $("#advisor-form").elements.from_date.value = fmt(start);
    $("#advisor-form").elements.to_date.value = fmt(end);
  }
  async function loadAccounts() {
    const result = await api("/api/v1/accounts");
    state.accounts = result.items || [];
    const options = state.accounts.map((a) => '<option value="' + esc(a.id) + '">' +
      esc(a.display_name) + ' (ending ' + esc(a.account_last_four || "----") + ')</option>').join("");
    $("#import-account").innerHTML = '<option value="">Select account</option>' + options;
    $("#transaction-account-filter").innerHTML = '<option value="">All accounts</option>' + options;
    $("#accounts-list").innerHTML = state.accounts.length ? state.accounts.map((a) =>
      '<div class="list-row"><div><strong>' + esc(a.display_name) + '</strong><small>FNB · ' +
      esc(a.account_type) + ' · ' + esc(a.currency) + ' · ending ' +
      esc(a.account_last_four || "not supplied") + '</small></div><small>' +
      (a.is_active ? "Active" : "Inactive") + '</small></div>'
    ).join("") : '<p class="empty-state">No financial accounts have been added.</p>';
    return result;
  }
  async function loadCategories() {
    const result = await api("/api/v1/categories");
    state.categories = result.items || [];
    const options = state.categories.filter((c) => c.is_active).map((c) =>
      '<option value="' + esc(c.id) + '">' + esc(c.name) + '</option>').join("");
    $("#budget-category").innerHTML = '<option value="">All spending</option>' + options;
    $("#categories-list").innerHTML = state.categories.length ? state.categories.map((c) =>
      '<div class="list-row"><div><strong>' + esc(c.name) + '</strong><small>' +
      esc(c.kind) + (c.description ? " · " + esc(c.description) : "") +
      '</small></div><small>' + (c.is_active ? "Active" : "Inactive") + '</small></div>'
    ).join("") : '<p class="empty-state">No categories have been created.</p>';
    return result;
  }
  function transactionTable(items, editable) {
    if (!items.length) return '<p class="table-empty">No transactions found.</p>';
    return '<table><thead><tr><th>Date</th><th>Description</th><th>Account</th><th class="numeric">Amount</th><th>Category</th></tr></thead><tbody>' +
      items.map((t) => {
        const account = state.accounts.find((a) => a.id === t.account_id);
        const category = state.categories.find((c) => c.id === t.category_id);
        const categoryText = editable
          ? '<select aria-label="Transaction category" data-transaction-category="' + esc(t.id) + '">' +
            '<option value="">Unclassified</option>' +
            state.categories.filter((c) => c.is_active).map((c) =>
              '<option value="' + esc(c.id) + '"' + (c.id === t.category_id ? " selected" : "") + '>' + esc(c.name) + '</option>'
            ).join("") + '</select>'
          : esc(category ? category.name : "Unclassified");
        return '<tr><td>' + esc(t.transaction_date) + '</td><td>' +
          esc(t.merchant_override || t.description) + '</td><td>' +
          esc(account ? account.display_name : "Account") + '</td><td class="numeric">' +
          esc(money(t.amount, t.currency)) + '</td><td>' + categoryText + '</td></tr>';
      }).join("") + '</tbody></table>';
  }
  async function loadDashboard() {
    const from = $("#summary-from").value;
    const to = $("#summary-to").value;
    if (!from || !to) return;
    const s = await api("/api/v1/analytics/summary?from_date=" + encodeURIComponent(from) +
      "&to_date=" + encodeURIComponent(to) + "&currency=ZAR");
    const metrics = [
      ["Income", money(s.income, s.currency)],
      ["Expenses", money(s.expenses, s.currency)],
      ["Net cash flow", money(s.net_cash_flow, s.currency)],
      ["Transactions", Number(s.transaction_count).toLocaleString("en-ZA")]
    ];
    $("#summary-cards").innerHTML = metrics.map((m) =>
      '<div class="metric"><span>' + esc(m[0]) + '</span><strong>' + esc(m[1]) + '</strong></div>'
    ).join("");
    $("#unclassified-count").textContent = String(s.unclassified_count);
    const totals = Object.entries(s.category_totals || {});
    $("#category-totals").innerHTML = totals.length
      ? '<table><thead><tr><th>Category ID</th><th class="numeric">Net amount</th></tr></thead><tbody>' +
        totals.map((t) => '<tr><td>' + esc(t[0]) + '</td><td class="numeric">' + esc(money(t[1], s.currency)) + '</td></tr>').join("") +
        '</tbody></table>'
      : '<p class="empty-state">No category totals for this period.</p>';
    const recent = await api("/api/v1/transactions?from_date=" + encodeURIComponent(from) +
      "&to_date=" + encodeURIComponent(to) + "&limit=10");
    $("#recent-transactions").innerHTML = transactionTable(recent.items || [], false);
  }
  async function loadTransactions() {
    const f = $("#transaction-filter");
    const q = new URLSearchParams({ limit: "100" });
    if (f.elements.from_date.value) q.set("from_date", f.elements.from_date.value);
    if (f.elements.to_date.value) q.set("to_date", f.elements.to_date.value);
    if (f.elements.account_id.value) q.set("account_id", f.elements.account_id.value);
    const result = await api("/api/v1/transactions?" + q.toString());
    $("#transactions-list").innerHTML = transactionTable(result.items || [], true);
  }
  async function loadImports() {
    const r = await api("/imports/fnb/imports?limit=50");
    const items = r.items || [];
    $("#import-history").innerHTML = items.length
      ? '<table><thead><tr><th>Statement date</th><th>Status</th><th>Transactions</th><th>Imported</th><th>Duplicates</th></tr></thead><tbody>' +
        items.map((i) => '<tr><td>' + esc(i.statement_date || "Not provided") + '</td><td>' +
          esc(i.status) + '</td><td>' + esc(i.transaction_count) + '</td><td>' +
          esc(i.imported_count) + '</td><td>' + esc(i.duplicate_count) + '</td></tr>').join("") +
        '</tbody></table>'
      : '<p class="empty-state">No FNB statements have been imported.</p>';
  }
  async function loadPlanning() {
    const period = $("#budget-progress-period").value;
    const progress = await api("/api/v1/budgets/progress?period=" + encodeURIComponent(period));
    $("#budget-progress").innerHTML = progress.length ? progress.map((p) =>
      '<div class="list-row"><div><strong>' + esc(p.name) + '</strong><small>' + esc(p.period) +
      ' · ' + esc(p.currency) + '</small></div><div><strong>' +
      esc(money(p.spent, p.currency)) + ' / ' + esc(money(p.amount, p.currency)) +
      '</strong><small>' + (p.is_over_budget ? "Over budget" : esc(money(p.remaining, p.currency)) + " remaining") +
      '</small></div></div>'
    ).join("") : '<p class="empty-state">No budgets for this period.</p>';
    const goals = await api("/api/v1/goals");
    $("#goals-list").innerHTML = (goals.items || []).length ? goals.items.map((g) =>
      '<div class="list-row"><div><strong>' + esc(g.name) + '</strong><small>Target ' +
      esc(money(g.target_amount, g.currency)) + (g.target_date ? " · by " + esc(g.target_date) : "") +
      '</small></div><div><strong>' + esc(money(g.contributed_amount, g.currency)) +
      ' saved</strong><button class="button button-quiet" type="button" data-goal-contribution="' +
      esc(g.id) + '">Add contribution</button></div></div>'
    ).join("") : '<p class="empty-state">No financial goals have been created.</p>';
  }
  async function loadConsent() {
    const c = await api("/api/v1/privacy/ai-consent");
    $("#ai-consent").checked = c.consent;
    $("#ai-consent-notice").textContent = c.data_sent;
  }
  async function previewStatement() {
    const file = $("#fnb-file").files[0];
    const account = $("#import-account").value;
    if (!file || !account) throw new Error("Select an FNB account and CSV statement first.");
    if (file.size > 20 * 1024 * 1024) throw new Error("The CSV file exceeds 20 MB.");
    state.file = file;
    state.previewed = false;
    $("#confirm-import").disabled = true;
    const body = new FormData();
    body.append("file", file);
    const p = await api("/imports/fnb/csv/preview", { method: "POST", body });
    state.previewed = true;
    $("#confirm-import").disabled = false;
    $("#import-preview").innerHTML = '<div class="preview-summary"><strong>' +
      esc(p.transaction_count) + ' transactions detected</strong> · Statement date ' +
      esc(p.statement_date || "not supplied") + ' · Account ending ' +
      esc(p.account_last_four || "not supplied") + '</div><div class="table-wrap"><table>' +
      '<thead><tr><th>Date</th><th>Description</th><th>Reference</th><th class="numeric">Amount</th><th class="numeric">Balance</th></tr></thead><tbody>' +
      (p.transactions || []).map((t) => '<tr><td>' + esc(t.effective_date) + '</td><td>' +
        esc(t.description) + '</td><td>' + esc(t.reference || "") + '</td><td class="numeric">' +
        esc(money(t.amount)) + '</td><td class="numeric">' + (t.balance == null ? "-" : esc(money(t.balance))) +
        '</td></tr>').join("") + '</tbody></table></div><p class="fine-print">Preview only. Confirm after reviewing the transactions.</p>';
  }
  async function confirmStatement() {
    if (!state.previewed || !state.file) throw new Error("Preview the statement before confirming.");
    const body = new FormData();
    body.append("account_id", $("#import-account").value);
    body.append("file", state.file);
    const result = await api("/imports/fnb/csv/confirm", { method: "POST", body });
    state.previewed = false;
    $("#confirm-import").disabled = true;
    await Promise.all([loadImports(), loadDashboard(), loadTransactions()]);
    say(result.already_imported
      ? "This exact statement was already imported. No new transactions were created."
      : "Import completed. " + result.imported_count + " imported, " + result.duplicate_count + " duplicates skipped.", "success");
  }
  async function contribution(button) {
    const amount = window.prompt("Enter the contribution amount in ZAR:");
    if (amount === null) return;
    if (!/^\d+(\.\d{1,2})?$/.test(amount) || Number(amount) <= 0) {
      throw new Error("Enter a positive amount with no more than two decimal places.");
    }
    await send("/api/v1/goals/" + encodeURIComponent(button.dataset.goalContribution) + "/contributions", {
      amount: amount, contribution_date: today(), note: null
    }, "POST", { "Idempotency-Key": crypto.randomUUID() });
    await loadPlanning();
    say("Goal contribution recorded.", "success");
  }
  function signOut() {
    state.token = null;
    state.user = null;
    state.file = null;
    state.previewed = false;
    $("#auth-panel").hidden = false;
    $("#app-panel").hidden = true;
    $("#account-strip").hidden = true;
    $("#fnb-file").value = "";
    $("#import-preview").replaceChildren();
    $("#confirm-import").disabled = true;
    say("You have signed out.", "success");
  }
  function init() {
    dates();
    $("#login-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const r = await send("/auth/token", {
          email: e.currentTarget.elements.email.value,
          password: e.currentTarget.elements.password.value
        });
        await signIn(r.access_token);
      } catch (error) { showError(error); }
    });
    $("#register-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const f = e.currentTarget;
        await api("/auth/register", {
          method: "POST",
          headers: { "X-Registration-Invite": f.elements.invite.value },
          body: JSON.stringify({ email: f.elements.email.value, password: f.elements.password.value })
        });
        say("Account created. Sign in using your new credentials.", "success");
        f.reset();
        $("[data-auth-tab='login']").click();
      } catch (error) { showError(error); }
    });
    $$("[data-auth-tab]").forEach((b) => b.addEventListener("click", () => {
      $$("[data-auth-tab]").forEach((x) => x.classList.toggle("active", x === b));
      const login = b.dataset.authTab === "login";
      $("#login-form").hidden = !login;
      $("#register-form").hidden = login;
    }));
    $("#logout-button").addEventListener("click", signOut);
    $$(".nav-link").forEach((b) => b.addEventListener("click", () => activate(b.dataset.section)));
    $$("[data-go]").forEach((b) => b.addEventListener("click", () => activate(b.dataset.go)));
    $("#refresh-summary").addEventListener("click", () => loadDashboard().catch(showError));
    $("#account-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const f = e.currentTarget;
        const d = formObject(f);
        if (!d.account_last_four) delete d.account_last_four;
        await send("/api/v1/accounts", { institution: "FNB", ...d });
        f.reset();
        await loadAccounts();
        say("FNB account added.", "success");
      } catch (error) { showError(error); }
    });
    $("#category-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const f = e.currentTarget;
        const d = formObject(f);
        if (!d.description) delete d.description;
        await send("/api/v1/categories", d);
        f.reset();
        await loadCategories();
        say("Category created.", "success");
      } catch (error) { showError(error); }
    });
    $("#budget-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const d = formObject(e.currentTarget);
        if (!d.category_id) d.category_id = null;
        d.currency = "ZAR";
        await send("/api/v1/budgets", d);
        await loadPlanning();
        say("Budget saved.", "success");
      } catch (error) { showError(error); }
    });
    $("#goal-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const d = formObject(e.currentTarget);
        if (!d.target_date) d.target_date = null;
        await send("/api/v1/goals", d);
        e.currentTarget.reset();
        await loadPlanning();
        say("Financial goal saved.", "success");
      } catch (error) { showError(error); }
    });
    $("#transaction-filter").addEventListener("submit", (e) => {
      e.preventDefault(); loadTransactions().catch(showError);
    });
    $("#transactions-list").addEventListener("change", async (e) => {
      if (!e.target.matches("[data-transaction-category]")) return;
      try {
        await send("/api/v1/transactions/" + encodeURIComponent(e.target.dataset.transactionCategory),
          { category_id: e.target.value || null }, "PATCH");
        await loadDashboard();
        say("Transaction category updated.", "success");
      } catch (error) { showError(error); }
    });
    $("#preview-import").addEventListener("click", () => previewStatement().catch(showError));
    $("#confirm-import").addEventListener("click", () => confirmStatement().catch(showError));
    $("#fnb-file").addEventListener("change", () => {
      state.file = null; state.previewed = false;
      $("#confirm-import").disabled = true;
      $("#import-preview").replaceChildren();
    });
    $("#import-account").addEventListener("change", () => {
      state.previewed = false; $("#confirm-import").disabled = true;
    });
    $("#budget-progress-period").addEventListener("change", () => loadPlanning().catch(showError));
    $("#goals-list").addEventListener("click", (e) => {
      const b = e.target.closest("[data-goal-contribution]");
      if (b) contribution(b).catch(showError);
    });
    $("#save-ai-consent").addEventListener("click", async () => {
      try {
        const result = await send("/api/v1/privacy/ai-consent", { consent: $("#ai-consent").checked }, "PUT");
        $("#ai-consent").checked = result.consent;
        say(result.consent ? "AI processing consent saved." : "AI processing consent withdrawn.", "success");
      } catch (error) { showError(error); }
    });
    $("#advisor-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        $("#advisor-answer").textContent = "Preparing the verified summary...";
        const result = await send("/api/v1/advisor/ask", formObject(e.currentTarget));
        $("#advisor-answer").innerHTML = '<div class="answer">' + esc(result.answer) +
          '</div><p class="fine-print">Model: ' + esc(result.model) + ' · ' +
          esc(result.data_scope) + '</p><p class="fine-print">' + esc(result.disclaimer) + '</p>';
      } catch (error) { $("#advisor-answer").textContent = ""; showError(error); }
    });
  }
  document.addEventListener("DOMContentLoaded", init);
})();
