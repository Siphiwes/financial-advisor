(() => {
  "use strict";

  const state = {
    token: null,
    user: null,
    financeEnabled: false,
    accounts: [],
    categories: [],
    selectedFile: null,
    importPreview: null,
  };
  const $ = (id) => document.getElementById(id);

  class ApiError extends Error {
    constructor(status, detail) {
      super(detail || "The request could not be completed.");
      this.status = status;
    }
  }

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  }

  function money(value, currency) {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return "Not available";
    try {
      return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: currency || "ZAR",
        maximumFractionDigits: 2,
      }).format(amount);
    } catch {
      return (currency || "") + " " + amount.toFixed(2);
    }
  }

  function message(id, value, type) {
    const node = $(id);
    node.textContent = value || "";
    node.className = "form-message" + (type ? " " + type : "");
  }

  function globalMessage(value, warning) {
    const node = $("global-message");
    node.textContent = value || "";
    node.classList.toggle("hidden", !value);
    node.classList.toggle("notice-warning", Boolean(warning));
  }

  async function api(path, options) {
    const settings = options || {};
    const headers = new Headers(settings.headers || {});
    if (state.token) headers.set("Authorization", "Bearer " + state.token);
    const isForm = settings.body instanceof FormData;
    if (settings.body && !isForm && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    let response;
    try {
      response = await fetch(path, {
        ...settings,
        headers,
        credentials: "same-origin",
      });
    } catch {
      throw new ApiError(0, "The API could not be reached. Check the connection and try again.");
    }
    const contentType = response.headers.get("content-type") || "";
    let payload = null;
    if (response.status !== 204) {
      if (contentType.includes("application/json")) {
        payload = await response.json().catch(() => null);
      } else {
        payload = await response.text().catch(() => "");
      }
    }
    if (!response.ok) {
      const detail = payload && typeof payload === "object" ? payload.detail : payload;
      if (response.status === 401 && state.token) signOut();
      throw new ApiError(response.status, typeof detail === "string" ? detail : "The API request failed.");
    }
    return payload;
  }

  function gateError(error) {
    return error instanceof ApiError && error.status === 503;
  }

  function signOut() {
    state.token = null;
    state.user = null;
    state.accounts = [];
    state.categories = [];
    state.selectedFile = null;
    state.importPreview = null;
    $("fnb-file").value = "";
    $("import-consent").checked = false;
    $("advisor-consent").checked = false;
    $("advisor-answer").classList.add("hidden");
    $("import-preview").classList.add("hidden");
    $("import-confirm-form").reset();
    ["password","register-password","registration-invite","password-current",
     "password-new","revoke-current-password","delete-password"].forEach((id) => {
      const field = $(id);
      if (field) field.value = "";
    });
    $("workspace").classList.add("hidden");
    $("login-shell").classList.remove("hidden");
    $("login-panel").classList.remove("hidden");
    $("register-panel").classList.add("hidden");
    $("logout-button").classList.add("hidden");
    message("login-message", "", "");
    message("register-message", "", "");
  }

  function setGate(enabled) {
    state.financeEnabled = enabled;
    $("finance-gate").textContent = enabled ? "Financial storage enabled" : "Financial data locked";
    $("finance-gate").className = "status-pill " + (enabled ? "status-success" : "status-warning");
    $("finance-lock-notice").classList.toggle("hidden", enabled);
    ["accounts-lock","transactions-lock","budgets-lock","goals-lock","categories-lock"]
      .forEach((id) => $(id).classList.toggle("hidden", enabled));
    $("import-gate-message").classList.toggle("hidden", enabled);
    $("confirm-import-button").disabled = !enabled || !state.selectedFile;
    ["account-form","transaction-form","budget-form","goal-form","category-form","advisor-form"]
      .forEach((id) => {
        $(id).querySelectorAll("input,select,textarea,button").forEach((control) => {
          control.disabled = !enabled;
        });
      });
    $("advisor-submit").disabled = !enabled || !$("advisor-consent").checked;
  }

  function switchView(id) {
    document.querySelectorAll(".view").forEach((view) => {
      view.classList.toggle("hidden", view.id !== id);
    });
    document.querySelectorAll(".tab").forEach((button) => {
      button.classList.toggle("active", button.dataset.view === id);
    });
  }

  function setOptions(select, options, placeholder) {
    while (select.firstChild) select.removeChild(select.firstChild);
    const blank = el("option", placeholder);
    blank.value = "";
    select.append(blank);
    options.forEach((entry) => {
      const option = el("option", entry.label);
      option.value = entry.value;
      select.append(option);
    });
  }

  function refreshSelects() {
    const accounts = state.accounts.filter((item) => item.is_active).map((item) => ({
      value: item.id,
      label: item.display_name + " · •••• " + item.account_last_four,
    }));
    setOptions($("transaction-account"), accounts, "Select account");
    setOptions($("transaction-account-filter"), accounts, "All accounts");
    setOptions($("import-account"), accounts, "Select matching FNB account");
    const categories = state.categories.filter((item) => item.is_active);
    setOptions($("transaction-category"), categories.map((item) => ({
      value: item.name,
      label: item.name,
    })), "Uncategorised");
    setOptions($("budget-category"), categories.filter((item) => item.kind === "expense").map((item) => ({
      value: item.name,
      label: item.name,
    })), "Select expense category");
  }

  function renderAccounts() {
    const target = $("account-list");
    target.replaceChildren();
    if (!state.accounts.length) target.append(el("p", "No linked financial accounts.", "empty-state"));
    state.accounts.forEach((account) => {
      const card = el("article", undefined, "record-card");
      const top = el("div", undefined, "record-card-top");
      const details = el("div");
      details.append(el("h3", account.display_name));
      details.append(el("p", account.institution + " · " + account.account_type.replaceAll("_", " ") + " · •••• " + account.account_last_four + " · " + account.currency));
      top.append(details);
      top.append(el("span", account.is_active ? "Active" : "Inactive", "status-pill status-success"));
      card.append(top);
      const actions = el("div", undefined, "record-actions");
      const deactivate = el("button", "Deactivate", "button button-secondary");
      deactivate.type = "button";
      deactivate.disabled = !account.is_active;
      deactivate.addEventListener("click", async () => {
        if (!window.confirm("Deactivate this linked account? Existing transactions will remain.")) return;
        try {
          await api("/api/v1/accounts/" + encodeURIComponent(account.id), { method: "DELETE" });
          await loadData();
        } catch (error) {
          globalMessage(error.message, true);
        }
      });
      actions.append(deactivate);
      card.append(actions);
      target.append(card);
    });
  }

  function renderCategories() {
    const target = $("category-list");
    target.replaceChildren();
    if (!state.categories.length) target.append(el("p", "Categories are not available.", "empty-state"));
    state.categories.forEach((category) => {
      const card = el("article", undefined, "record-card");
      const top = el("div", undefined, "record-card-top");
      const details = el("div");
      details.append(el("h3", category.name));
      details.append(el("p", category.kind + " · " + (category.is_system ? "Built-in" : "Custom")));
      top.append(details);
      top.append(el("span", category.is_system ? "System" : "Your category", "status-pill"));
      card.append(top);
      target.append(card);
    });
  }

  function renderTransactions(items) {
    const target = $("transaction-list");
    target.replaceChildren();
    if (!items || !items.length) {
      target.append(el("p", "No transactions match this view.", "empty-state"));
      return;
    }
    const table = el("table");
    const head = el("thead");
    const header = el("tr");
    ["Date","Description","Reference","Category","Amount","Actions"].forEach((label) => header.append(el("th", label)));
    head.append(header);
    table.append(head);
    const body = el("tbody");
    items.forEach((item) => {
      const row = el("tr");
      row.append(el("td", item.transaction_date));
      row.append(el("td", item.description));
      row.append(el("td", item.reference || "Not provided"));
      row.append(el("td", item.category || "Uncategorised"));
      row.append(el("td", money(item.amount, item.currency), Number(item.amount) < 0 ? "amount-negative" : "amount-positive"));
      const actions = el("td");
      const edit = el("button", "Edit", "button button-secondary");
      edit.type = "button";
      edit.addEventListener("click", () => editTransaction(item));
      const suggest = el("button", "Suggest category with AI", "button button-secondary");
      suggest.type = "button";
      suggest.addEventListener("click", async () => {
        const consent = window.confirm(
          "Send this transaction's date, description, amount and currency, plus your allowed category names, to IBM watsonx.ai for a category suggestion?"
        );
        if (!consent) return;
        try {
          const result = await api(
            "/api/v1/advisor/transactions/" + encodeURIComponent(item.id) + "/suggest-category",
            {
              method: "POST",
              body: JSON.stringify({ consent_to_share_transaction: true }),
            }
          );
          const apply = window.confirm(
            "AI suggests: " + result.suggested_category +
            "\n\nReason: " + result.explanation +
            "\n\nApply this category? The original imported transaction details will remain preserved."
          );
          if (apply) {
            await api("/api/v1/transactions/" + encodeURIComponent(item.id), {
              method: "PATCH",
              body: JSON.stringify({ category: result.suggested_category }),
            });
            await loadData();
          }
        } catch (error) {
          globalMessage(error.message, true);
        }
      });
      const remove = el("button", "Delete", "button button-quiet");
      remove.type = "button";
      remove.addEventListener("click", async () => {
        if (!window.confirm("Remove this transaction from your active history?")) return;
        try {
          await api("/api/v1/transactions/" + encodeURIComponent(item.id), { method: "DELETE" });
          await loadData();
        } catch (error) {
          globalMessage(error.message, true);
        }
      });
      actions.append(edit, suggest, remove);
      row.append(actions);
      body.append(row);
    });
    table.append(body);
    target.append(table);
  }

  async function editTransaction(item) {
    const description = window.prompt("Transaction description", item.description);
    if (description === null) return;
    const amountText = window.prompt("Amount (negative for debit)", String(item.amount));
    if (amountText === null) return;
    const amount = Number(amountText);
    if (!Number.isFinite(amount)) {
      globalMessage("Enter a valid amount.", true);
      return;
    }
    try {
      await api("/api/v1/transactions/" + encodeURIComponent(item.id), {
        method: "PATCH",
        body: JSON.stringify({ description, amount: amount.toFixed(2) }),
      });
      await loadData();
    } catch (error) {
      globalMessage(error.message, true);
    }
  }

  function renderBudgets(items) {
    const target = $("budget-list");
    target.replaceChildren();
    if (!items || !items.length) target.append(el("p", "No budgets have been created.", "empty-state"));
    (items || []).forEach((budget) => {
      const card = el("article", undefined, "record-card");
      const top = el("div", undefined, "record-card-top");
      const details = el("div");
      details.append(el("h3", budget.name));
      details.append(el("p", budget.category + " · " + budget.period + " · " + budget.period_start + " to " + budget.period_end));
      top.append(details, el("strong", money(budget.amount, budget.currency)));
      card.append(top);
      const bar = el("div", undefined, "progress");
      const fill = el("span");
      const percent = Math.max(0, Math.min(100, Number(budget.percent_used)));
      fill.style.width = percent + "%";
      bar.append(fill);
      card.append(bar);
      card.append(el("p", money(budget.spent, budget.currency) + " spent · " + money(budget.remaining, budget.currency) + " remaining · " + percent.toFixed(1) + "% used", "muted small"));
      target.append(card);
    });
  }

  function renderGoals(items) {
    const target = $("goal-list");
    target.replaceChildren();
    if (!items || !items.length) target.append(el("p", "No financial goals have been added.", "empty-state"));
    (items || []).forEach((goal) => {
      const card = el("article", undefined, "record-card");
      const top = el("div", undefined, "record-card-top");
      const details = el("div");
      details.append(el("h3", goal.name));
      details.append(el("p", goal.description || "No description provided"));
      top.append(details, el("strong", money(goal.target_amount, goal.currency)));
      card.append(top);
      const bar = el("div", undefined, "progress");
      const fill = el("span");
      const percent = Math.max(0, Math.min(100, Number(goal.saved_amount) / Number(goal.target_amount) * 100));
      fill.style.width = (Number.isFinite(percent) ? percent : 0) + "%";
      bar.append(fill);
      card.append(bar);
      card.append(el("p", money(goal.saved_amount, goal.currency) + " saved · " + (Number.isFinite(percent) ? percent : 0).toFixed(1) + "% of target", "muted small"));

      const form = el("form", undefined, "form-actions");
      const amount = el("input");
      amount.type = "number"; amount.min = "0.01"; amount.step = "0.01";
      amount.required = true; amount.placeholder = "Amount";
      amount.setAttribute("aria-label", "Contribution amount");
      const direction = el("select");
      [["contribution","Add"],["withdrawal","Withdraw"]].forEach((entry) => {
        const option = el("option", entry[1]); option.value = entry[0]; direction.append(option);
      });
      const submit = el("button", "Record", "button button-secondary");
      submit.type = "submit";
      form.append(amount, direction, submit);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
          await api("/api/v1/goals/" + encodeURIComponent(goal.id) + "/contributions", {
            method: "POST",
            body: JSON.stringify({
              amount: Number(amount.value).toFixed(2),
              transaction_date: new Date().toISOString().slice(0, 10),
              direction: direction.value,
            }),
          });
          await loadData();
        } catch (error) {
          globalMessage(error.message, true);
        }
      });
      card.append(form);
      target.append(card);
    });
  }

  function renderImportHistory(items) {
    const target = $("import-history-list");
    target.replaceChildren();
    if (!items || !items.length) {
      target.append(el("p", "No confirmed statement imports have been recorded.", "empty-state"));
      return;
    }
    items.forEach((item) => {
      const card = el("article", undefined, "record-card");
      const top = el("div", undefined, "record-card-top");
      const details = el("div");
      details.append(el("h3", (item.source || "FNB_CSV").replace("_", " ") + " import"));
      details.append(el("p", "Statement date: " + (item.statement_date || "Not supplied")));
      top.append(details, el("span", item.status, "status-pill"));
      card.append(top);
      const counts = el("p",
        "Processed: " + item.transaction_count +
        " · Imported: " + item.imported_count +
        " · Duplicates: " + item.duplicate_count,
        "muted small"
      );
      card.append(counts);
      card.append(el(
        "p",
        "Started: " + (item.started_at || item.created_at || "Not available") +
        " · Completed: " + (item.completed_at || "Not completed"),
        "muted small"
      ));
      target.append(card);
    });
  }

  function renderSummary(summary, recurring) {
    const cards = $("summary-cards");
    cards.replaceChildren();
    const values = summary && summary.currencies ? summary.currencies : [];
    [["Income","income"],["Expenses","expenses"],["Net cash flow","net_cash_flow"]].forEach((item) => {
      const card = el("article", undefined, "metric-card");
      card.append(el("span", item[0]));
      if (!values.length) {
        card.append(el("strong", "No recorded data"), el("small", "Awaiting saved transactions"));
      } else {
        values.forEach((currency) => card.append(el("strong", money(currency[item[1]], currency.currency))));
        card.append(el("small", "Calculated per currency"));
      }
      cards.append(card);
    });

    const categoryTarget = $("category-summary");
    categoryTarget.replaceChildren();
    const categories = summary && summary.expenses_by_category ? summary.expenses_by_category : [];
    if (!categories.length) categoryTarget.append(el("p", "No categorised expenses are available.", "empty-state"));
    categories.forEach((item) => {
      const row = el("div", undefined, "key-value");
      row.append(el("span", item.category + " (" + item.transaction_count + ")"));
      row.append(el("strong", money(item.expenses, item.currency)));
      categoryTarget.append(row);
    });

    const recurringTarget = $("recurring-list");
    recurringTarget.replaceChildren();
    if (!recurring || !recurring.length) recurringTarget.append(el("p", "No recurring-payment candidates were found.", "empty-state"));
    (recurring || []).forEach((item) => {
      const row = el("div", undefined, "key-value");
      row.append(el("span", item.description + " · " + item.frequency + " · " + item.occurrence_count + " records"));
      row.append(el("strong", money(item.average_amount, item.currency)));
      recurringTarget.append(row);
    });
    if (summary && summary.data_limit_reached) {
      globalMessage("The summary used the first 10,000 records. Refine the date range for a complete period.", true);
    }
  }

  function renderImportPreview(preview) {
    state.importPreview = preview;
    const isPdfPreview = preview.source_format === "FNB PDF";
    $("pdf-preview-notice").classList.toggle("hidden", !isPdfPreview);
    $("import-preview").classList.remove("hidden");
    $("import-metadata").textContent = [
      preview.statement_date ? "Statement date: " + preview.statement_date : "Statement date not supplied",
      preview.account_last_four ? "Account ending " + preview.account_last_four : "Account digits not found in parsed metadata",
    ].join(" · ");
    $("import-count").textContent = preview.transaction_count + " transactions";
    const container = $("import-transactions");
    container.replaceChildren();
    const table = el("table");
    const head = el("thead");
    const header = el("tr");
    ["Date","Description","Reference","Service fee","Amount","Balance"].forEach((label) => header.append(el("th", label)));
    head.append(header); table.append(head);
    const body = el("tbody");
    (preview.transactions || []).forEach((item) => {
      const row = el("tr");
      row.append(el("td", item.effective_date));
      row.append(el("td", item.description));
      row.append(el("td", item.reference || "Not supplied"));
      row.append(el("td", item.service_fee === null ? "Not supplied" : item.service_fee));
      row.append(el("td", item.amount));
      row.append(el("td", item.balance === null ? "Not supplied" : item.balance));
      body.append(row);
    });
    table.append(body); container.append(table);
    if (preview.transaction_count > preview.preview_limit) {
      container.append(el("p", "Showing " + preview.preview_limit + " of " + preview.transaction_count + " transactions. The confirmation endpoint processes the full validated statement.", "muted small"));
    }
    $("confirm-import-button").disabled = !state.financeEnabled;
  }

  async function loadFinanceData() {
    try {
      state.accounts = await api("/api/v1/accounts");
      setGate(true);
      const results = await Promise.all([
        api("/api/v1/categories"),
        api("/api/v1/transactions?limit=100"),
        api("/api/v1/budgets/progress"),
        api("/api/v1/goals"),
        api("/api/v1/analytics/summary"),
        api("/api/v1/analytics/recurring-payments"),
        api("/imports"),
      ]);
      state.categories = results[0];
      renderAccounts();
      renderCategories();
      renderTransactions(results[1].items || []);
      renderBudgets(results[2]);
      renderGoals(results[3]);
      renderSummary(results[4], results[5]);
      renderImportHistory(results[6]);
      $("confirm-import-button").disabled = !state.importPreview;
    } catch (error) {
      if (error instanceof ApiError && error.status === 503) {
        setGate(false);
        state.accounts = [];
        state.categories = [];
        renderAccounts();
        renderCategories();
        renderTransactions([]);
        renderBudgets([]);
        renderGoals([]);
        renderSummary(null, []);
        return;
      }
      globalMessage(error.message, true);
    }
  }

  async function loadTransactionsByFilter() {
    const params = new URLSearchParams();
    [["account_id","transaction-account-filter"],["from_date","transaction-from"],
     ["to_date","transaction-to"],["search","transaction-search"]].forEach((item) => {
      const value = $(item[1]).value.trim();
      if (value) params.set(item[0], value);
    });
    try {
      const data = await api("/api/v1/transactions?" + params.toString());
      renderTransactions(data.items || []);
    } catch (error) {
      globalMessage(error.message, true);
    }
  }

  async function beginWorkspace() {
    $("login-shell").classList.add("hidden");
    $("workspace").classList.remove("hidden");
    $("logout-button").classList.remove("hidden");
    $("user-email").textContent = state.user.email;
    await loadFinanceData();
    switchView("dashboard-view");
  }

  $("show-register").addEventListener("click", () => {
    $("login-panel").classList.add("hidden");
    $("register-panel").classList.remove("hidden");
    message("register-message", "", "");
  });

  $("back-to-login").addEventListener("click", () => {
    $("register-panel").classList.add("hidden");
    $("login-panel").classList.remove("hidden");
    message("login-message", "", "");
  });

  $("register-panel").addEventListener("submit", async (event) => {
    event.preventDefault();
    message("register-message", "Creating account...");
    try {
      await api("/auth/register", {
        method: "POST",
        headers: {
          "X-Registration-Invite": $("registration-invite").value,
        },
        body: JSON.stringify({
          email: $("register-email").value.trim(),
          password: $("register-password").value,
        }),
      });
      $("email").value = $("register-email").value.trim();
      $("register-password").value = "";
      $("registration-invite").value = "";
      $("register-panel").classList.add("hidden");
      $("login-panel").classList.remove("hidden");
      message("login-message", "Account created. Check your email for the verification link before signing in.", "success");
    } catch (error) {
      message("register-message", error.message, "error");
    } finally {
      $("registration-invite").value = "";
    }
  });

  $("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    message("login-message", "Signing in...");
    try {
      const token = await api("/auth/token", {
        method: "POST",
        body: JSON.stringify({
          email: $("email").value.trim(),
          password: $("password").value,
        }),
      });
      state.token = token.access_token;
      state.user = await api("/auth/me");
      $("password").value = "";
      message("login-message", "", "");
      await beginWorkspace();
    } catch (error) {
      state.token = null;
      message("login-message", error.message, "error");
    }
  });

  $("resend-verification-button").addEventListener("click", async () => {
    const email = $("email").value.trim();
    if (!email) {
      message("login-message", "Enter your email address above first.", "error");
      $("email").focus();
      return;
    }
    message("login-message", "Requesting a verification email...");
    try {
      const result = await api("/auth/email/resend", {
        method: "POST",
        body: JSON.stringify({ email: email.trim() }),
      });
      message("login-message", result.message, "success");
    } catch (error) {
      message("login-message", error.message, "error");
    }
  });

  $("forgot-password-button").addEventListener("click", async () => {
    const email = $("email").value.trim();
    if (!email) {
      message("login-message", "Enter your email address above first.", "error");
      $("email").focus();
      return;
    }
    message("login-message", "Requesting a password reset...");
    try {
      const result = await api("/auth/password/reset/request", {
        method: "POST",
        body: JSON.stringify({ email: email.trim() }),
      });
      message("login-message", result.message, "success");
    } catch (error) {
      message("login-message", error.message, "error");
    }
  });

  async function processAccountLink() {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const verifyToken = params.get("verify_token");
    const resetToken = params.get("reset_token");
    if (!verifyToken && !resetToken) return;
    window.history.replaceState({}, document.title, window.location.pathname);
    if (verifyToken) {
      try {
        const result = await api("/auth/verify-email", {
          method: "POST",
          body: JSON.stringify({ token: verifyToken }),
        });
        message("login-message", result.message, "success");
      } catch (error) {
        message("login-message", error.message, "error");
      }
      return;
    }
    const password = window.prompt("Enter a new password (at least 12 characters):");
    if (!password) {
      message("login-message", "Password reset cancelled.", "error");
      return;
    }
    const confirmation = window.prompt("Confirm the new password:");
    if (password !== confirmation) {
      message("login-message", "The passwords do not match.", "error");
      return;
    }
    try {
      const result = await api("/auth/password/reset/confirm", {
        method: "POST",
        body: JSON.stringify({ token: resetToken, new_password: password }),
      });
      message("login-message", result.message, "success");
    } catch (error) {
      message("login-message", error.message, "error");
    }
  }

  $("logout-button").addEventListener("click", signOut);
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });

  $("account-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/v1/accounts", {
        method: "POST",
        body: JSON.stringify({
          institution: "FNB",
          display_name: $("account-name").value.trim(),
          account_type: $("account-type").value,
          currency: $("account-currency").value.trim().toUpperCase(),
          account_last_four: $("account-last-four").value.trim(),
        }),
      });
      event.target.reset();
      $("account-currency").value = "ZAR";
      message("account-message", "Account added.", "success");
      await loadFinanceData();
    } catch (error) {
      message("account-message", error.message, "error");
    }
  });
  $("refresh-accounts").addEventListener("click", loadFinanceData);
  $("refresh-import-history").addEventListener("click", loadFinanceData);

  $("transaction-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/v1/transactions", {
        method: "POST",
        body: JSON.stringify({
          account_id: $("transaction-account").value,
          transaction_date: $("transaction-date").value,
          description: $("transaction-description").value.trim(),
          amount: Number($("transaction-amount").value).toFixed(2),
          category: $("transaction-category").value || null,
        }),
      });
      event.target.reset();
      message("transaction-message", "Transaction saved.", "success");
      await loadFinanceData();
    } catch (error) {
      message("transaction-message", error.message, "error");
    }
  });
  $("transaction-filter").addEventListener("submit", (event) => {
    event.preventDefault(); loadTransactionsByFilter();
  });
  $("refresh-transactions").addEventListener("click", loadFinanceData);

  $("import-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = $("fnb-file").files[0];
    if (!file) return;
    if (file.size > 20 * 1024 * 1024) {
      message("import-message", "The file exceeds the 20 MB limit.", "error"); return;
    }
    const extension = file.name.toLowerCase().split(".").pop();
    if (!["pdf", "csv"].includes(extension)) {
      message("import-message", "Select an FNB PDF or CSV statement.", "error"); return;
    }
    state.selectedFile = file;
    const form = new FormData(); form.append("file", file);
    message("import-message", "Reading statement...");
    try {
      const previewPath = extension === "pdf" ? "/imports/fnb/pdf/preview" : "/imports/fnb/csv/preview";
      const preview = await api(previewPath, { method: "POST", body: form });
      renderImportPreview(preview);
      message("import-message", "Preview ready. No transactions have been saved.", "success");
    } catch (error) {
      message("import-message", error.message, "error");
    }
  });

  $("import-confirm-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.selectedFile || !state.importPreview) return;
    if (!$("import-consent").checked) {
      message("confirm-import-message", "Explicit confirmation is required.", "error"); return;
    }
    const form = new FormData();
    form.append("account_id", $("import-account").value);
    form.append("consent", "true");
    form.append("file", state.selectedFile);
    message("confirm-import-message", "Importing transactions...");
    try {
      const result = await api("/imports/fnb/confirm", { method: "POST", body: form });
      message("confirm-import-message",
        result.message + " Imported: " + result.imported_count + ". Duplicates: " + result.duplicate_count,
        "success");
      await loadFinanceData();
    } catch (error) {
      message("confirm-import-message", error.message, "error");
    }
  });

  $("budget-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/v1/budgets", {
        method: "POST",
        body: JSON.stringify({
          name: $("budget-name").value.trim(),
          category: $("budget-category").value,
          amount: Number($("budget-amount").value).toFixed(2),
          currency: "ZAR",
          period: $("budget-period").value,
          start_date: $("budget-start").value,
        }),
      });
      event.target.reset();
      message("budget-message", "Budget created.", "success");
      await loadFinanceData();
    } catch (error) {
      message("budget-message", error.message, "error");
    }
  });
  $("refresh-budgets").addEventListener("click", loadFinanceData);

  $("goal-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/v1/goals", {
        method: "POST",
        body: JSON.stringify({
          name: $("goal-name").value.trim(),
          target_amount: Number($("goal-target").value).toFixed(2),
          currency: "ZAR",
          target_date: $("goal-date").value || null,
        }),
      });
      event.target.reset();
      message("goal-message", "Goal created.", "success");
      await loadFinanceData();
    } catch (error) {
      message("goal-message", error.message, "error");
    }
  });
  $("refresh-goals").addEventListener("click", loadFinanceData);

  $("category-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/v1/categories", {
        method: "POST",
        body: JSON.stringify({
          name: $("category-name").value.trim(),
          kind: $("category-kind").value,
        }),
      });
      event.target.reset();
      message("category-message", "Category added.", "success");
      await loadFinanceData();
    } catch (error) {
      message("category-message", error.message, "error");
    }
  });
  $("refresh-categories").addEventListener("click", loadFinanceData);

  $("advisor-consent").addEventListener("change", () => {
    $("advisor-submit").disabled = !state.financeEnabled || !$("advisor-consent").checked;
  });

  $("advisor-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const answer = $("advisor-answer");
    answer.classList.remove("hidden");
    answer.textContent = "Preparing your approved summary and contacting IBM watsonx.ai...";
    try {
      const result = await api("/api/v1/advisor/chat", {
        method: "POST",
        body: JSON.stringify({
          question: $("advisor-question").value.trim(),
          consent_to_share_summary: true,
        }),
      });
      answer.textContent = result.answer + "\n\nData shared: " + result.data_shared.join("; ") + ".";
    } catch (error) {
      answer.textContent = error.message;
    }
  });

  async function loadAuditHistory() {
    const target = $("audit-list");
    target.replaceChildren();
    try {
      const events = await api("/api/v1/privacy/audit?limit=100");
      if (!events.length) {
        target.append(el("p", "No recent account activity is available.", "empty-state"));
        return;
      }
      events.forEach((item) => {
        const row = el("div", undefined, "key-value");
        row.append(
          el("span", item.action + " · " + item.resource_type),
          el("strong", item.occurred_at || item.created_at || "")
        );
        target.append(row);
      });
    } catch (error) {
      target.append(el("p", error.message, "empty-state"));
    }
  }

  $("refresh-audit-button").addEventListener("click", loadAuditHistory);

  $("password-change-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    message("password-change-message", "Changing password...");
    try {
      const result = await api("/auth/password/change", {
        method: "POST",
        body: JSON.stringify({
          current_password: $("password-current").value,
          new_password: $("password-new").value,
        }),
      });
      $("password-current").value = "";
      $("password-new").value = "";
      signOut();
      message("login-message", result.message, "success");
    } catch (error) {
      message("password-change-message", error.message, "error");
    }
  });

  $("revoke-sessions-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    message("revoke-sessions-message", "Invalidating existing sessions...");
    try {
      const result = await api("/auth/sessions/revoke", {
        method: "POST",
        body: JSON.stringify({
          current_password: $("revoke-current-password").value,
        }),
      });
      $("revoke-current-password").value = "";
      signOut();
      message("login-message", result.message + " Sign in again on this device.", "success");
    } catch (error) {
      message("revoke-sessions-message", error.message, "error");
    }
  });

  $("export-data-button").addEventListener("click", async () => {
    message("export-message", "Preparing your data export...");
    try {
      const data = await api("/api/v1/privacy/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "financial-advisor-data-export.json";
      document.body.append(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      message("export-message", "Your data export has been downloaded.", "success");
    } catch (error) {
      message("export-message", error.message, "error");
    }
  });

  function updateDeleteButtonState() {
    $("delete-account-button").disabled =
      $("delete-confirmation").value.trim() !== "DELETE" ||
      !$("delete-password").value;
  }
  $("delete-confirmation").addEventListener("input", updateDeleteButtonState);
  $("delete-password").addEventListener("input", updateDeleteButtonState);

  $("delete-account-button").addEventListener("click", async () => {
    if (
      $("delete-confirmation").value.trim() !== "DELETE" ||
      !$("delete-password").value
    ) return;
    const accepted = window.confirm(
      "This permanently deletes your login and financial records. It cannot be undone. Continue?"
    );
    if (!accepted) return;
    message("delete-message", "Deleting account and financial records...");
    $("delete-account-button").disabled = true;
    try {
      const result = await api("/api/v1/privacy/data", {
        method: "DELETE",
        body: JSON.stringify({ current_password: $("delete-password").value }),
      });
      state.token = null;
      state.user = null;
      $("delete-password").value = "";
      $("workspace").classList.add("hidden");
      $("logout-button").classList.add("hidden");
      $("login-shell").classList.remove("hidden");
      $("login-panel").classList.remove("hidden");
      $("register-panel").classList.add("hidden");
      message("login-message", result.message, "success");
    } catch (error) {
      message("delete-message", error.message, "error");
      $("delete-account-button").disabled = false;
    }
  });

  processAccountLink();

  fetch("/health", { credentials: "same-origin" })
    .then((response) => {
      $("connection-status").textContent = response.ok ? "API online" : "API issue";
      $("connection-status").className = "status-pill " + (response.ok ? "status-success" : "status-error");
    })
    .catch(() => {
      $("connection-status").textContent = "API unavailable";
      $("connection-status").className = "status-pill status-error";
    });
})();
