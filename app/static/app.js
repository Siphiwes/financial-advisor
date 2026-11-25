(() => {
  "use strict";

  const state = {
    token: null,
    user: null,
    financeEnabled: false,
    accounts: [],
    categories: [],
    debts: [],
    debtSummary: null,
    selectedFile: null,
    importPreview: null,
  };
  const $ = (id) => document.getElementById(id);

  class ApiError extends Error {
    constructor(status, detail, diagnostic) {
      super(detail || "The request could not be completed.");
      this.status = status;
      this.diagnostic = diagnostic || null;
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
      throw new ApiError(0, "Problem found on Server connection. The API could not be reached. Check the network connection and try again.", {
        category: "network_error", module: "Server connection", endpoint: path, method: settings.method || "GET"
      });
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
      const diagnostic = payload && typeof payload === "object" ? payload.error : null;
      if (response.status === 401) signOut();
      let messageText = typeof detail === "string" ? detail : "The API request failed.";
      if (diagnostic && diagnostic.diagnostic_id) {
        messageText = "Problem found on " + (diagnostic.module || "Server connection") +
          ". Issue caused by API " + (diagnostic.method || settings.method || "GET") +
          " " + (diagnostic.endpoint || path) + ". Reference: " + diagnostic.diagnostic_id +
          " (HTTP " + response.status + ").";
      } else if (response.status >= 500) {
        messageText = "Problem found on Server connection. Issue caused by API " +
          (settings.method || "GET") + " " + path + ". " + messageText;
      }
      throw new ApiError(response.status, messageText, diagnostic);
    }
    return payload;
  }

  function gateError(error) {
    return error instanceof ApiError && error.status === 503;
  }

  function signOut() {
    fetch("/auth/logout", { method: "POST", credentials: "same-origin" }).catch(() => {});
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
    $("finance-lock-notice").classList.add("hidden");
    ["accounts-lock","transactions-lock","budgets-lock","goals-lock","categories-lock","debts-lock"]
      .forEach((id) => $(id).classList.toggle("hidden", enabled));
    $("storage-overview-status").textContent = enabled ? "Storage enabled" : "Storage disabled";
    $("storage-overview-status").className = "status-pill " + (enabled ? "status-success" : "status-warning");
    const modules = [["Accounts","Account storage"],["Transactions","Transaction storage"],["Budgets","Budget storage"],["Goals","Goal storage"],["Categories","Category management storage"],["Debts","Debt storage"]];
    const statusList = $("storage-status-list");
    statusList.replaceChildren();
    modules.forEach(([name, detail]) => {
      const item = el("div", undefined, "storage-status-item");
      item.append(el("span", name), el("strong", enabled ? "Enabled" : "Disabled"));
      item.append(el("small", detail));
      statusList.append(item);
    });
    $("import-gate-message").classList.toggle("hidden", enabled);
    updateImportConfirmState();
    ["account-form","transaction-form","budget-form","goal-form","debt-form","category-form","advisor-form"]
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
    if (!select.multiple) {
      const blank = el("option", placeholder);
      blank.value = "";
      select.append(blank);
    }
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
    setOptions($("budget-category"), categories.filter((item) => item.kind === "expense" || item.kind === "income").map((item) => ({
      value: item.name,
      label: item.name + " (" + item.kind + ")",
    })), "Select income or expense categories");
  }

  function updateImportConfirmState() {
    const accountSelected = Boolean($("import-account").value);
    const consentGiven = $("import-consent").checked;
    $("confirm-import-button").disabled = !(
      state.financeEnabled &&
      state.selectedFile &&
      state.importPreview &&
      accountSelected &&
      consentGiven
    );
  }

  $("import-account").addEventListener("change", updateImportConfirmState);
  $("import-consent").addEventListener("change", updateImportConfirmState);


  function showAppDialog({title, description, fields = [], submitLabel = "Save changes"}) {
    const dialog = $("app-dialog");
    const form = $("app-dialog-form");
    const content = $("app-dialog-content");
    $("app-dialog-title").textContent = title;
    $("app-dialog-submit").textContent = submitLabel;
    content.replaceChildren();
    if (description) content.append(el("p", description, "muted"));
    const controls = {};
    fields.forEach((field) => {
      const wrapper = el("div", undefined, "app-dialog-field");
      const label = el("label", field.label);
      const id = "dialog-field-" + field.name;
      label.htmlFor = id;
      let control;
      if (field.type === "select") {
        control = el("select");
        (field.options || []).forEach((entry) => {
          const option = el("option", entry.label);
          option.value = entry.value;
          control.append(option);
        });
      } else if (field.type === "textarea") {
        control = el("textarea");
        control.rows = field.rows || 3;
      } else {
        control = el("input");
        control.type = field.type || "text";
      }
      control.id = id;
      control.name = field.name;
      control.value = field.value === null || field.value === undefined ? "" : String(field.value);
      if (field.required) control.required = true;
      if (field.min !== undefined) control.min = String(field.min);
      if (field.max !== undefined) control.max = String(field.max);
      if (field.step !== undefined) control.step = String(field.step);
      if (field.maxLength !== undefined) control.maxLength = field.maxLength;
      if (field.pattern) control.pattern = field.pattern;
      wrapper.append(label, control);
      content.append(wrapper);
      controls[field.name] = control;
    });
    return new Promise((resolve) => {
      let settled = false;
      const finish = (value) => {
        if (settled) return;
        settled = true;
        dialog.removeEventListener("close", onClose);
        form.removeEventListener("submit", onSubmit);
        $("app-dialog-cancel").removeEventListener("click", onCancel);
        $("app-dialog-close").removeEventListener("click", onCancel);
        resolve(value);
      };
      const onClose = () => finish(null);
      const onCancel = () => dialog.close();
      const onSubmit = (event) => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        const values = {};
        fields.forEach((field) => {
          const control = controls[field.name];
          values[field.name] = field.type === "number" ? Number(control.value) :
            (field.type === "textarea" || field.type === "text" ? control.value.trim() : control.value);
        });
        dialog.close();
        finish(values);
      };
      dialog.addEventListener("close", onClose);
      form.addEventListener("submit", onSubmit);
      $("app-dialog-cancel").addEventListener("click", onCancel);
      $("app-dialog-close").addEventListener("click", onCancel);
      dialog.showModal();
      const first = content.querySelector("input,select,textarea");
      if (first) first.focus();
    });
  }

  async function confirmInApp(description, confirmLabel = "Confirm") {
    const result = await showAppDialog({
      title: "Confirm action",
      description,
      fields: [],
      submitLabel: confirmLabel,
    });
    return result !== null;
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
      const edit = el("button", "Edit details", "button button-secondary");
      edit.type = "button";
      edit.addEventListener("click", async () => {
        const values = await showAppDialog({title:"Edit financial account",fields:[
          {name:"display_name",label:"Display name",value:account.display_name,required:true,maxLength:80},
          {name:"account_type",label:"Account type",type:"select",value:account.account_type,options:[
            {value:"cheque",label:"Cheque"},{value:"savings",label:"Savings"},{value:"credit_card",label:"Credit card"},
            {value:"investment",label:"Investment"},{value:"loan",label:"Loan"},{value:"other",label:"Other"}]},
          {name:"account_last_four",label:"Last four digits",value:account.account_last_four,required:true,pattern:"[0-9]{4}",maxLength:4}
        ]});
        if (!values) return;
        try {
          await api("/api/v1/accounts/" + encodeURIComponent(account.id),{method:"PATCH",body:JSON.stringify(values)});
          await loadFinanceData();
        } catch(error){globalMessage(error.message,true);}
      });
      const toggle = el("button", account.is_active ? "Deactivate" : "Reactivate", "button button-secondary");
      toggle.type = "button";
      toggle.addEventListener("click", async () => {
        const accepted = await confirmInApp(account.is_active ?
          "Deactivate this linked account? Existing transactions will remain." :
          "Reactivate this linked account?");
        if (!accepted) return;
        try {
          await api("/api/v1/accounts/" + encodeURIComponent(account.id),{
            method:"PATCH",body:JSON.stringify({is_active:!account.is_active})
          });
          await loadFinanceData();
        } catch(error){globalMessage(error.message,true);}
      });
      actions.append(edit,toggle);
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
        const consent = await confirmInApp(
          "Send this transaction's full stored details, including its description, reference and account identifier, plus the associated account record and category names, to IBM watsonx.ai for a category suggestion?",
          "Continue"
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
          const apply = await confirmInApp(
            "AI suggests: " + result.suggested_category +
            ". Reason: " + result.explanation +
            ". Apply this category? The original imported transaction details will remain preserved.",
            "Apply category"
          );
          if (apply) {
            await api("/api/v1/transactions/" + encodeURIComponent(item.id), {
              method: "PATCH",
              body: JSON.stringify({ category: result.suggested_category }),
            });
            await loadFinanceData();
          }
        } catch (error) {
          globalMessage(error.message, true);
        }
      });
      const remove = el("button", "Delete", "button button-quiet");
      remove.type = "button";
      remove.addEventListener("click", async () => {
        if (!await confirmInApp("Remove this transaction from your active history?")) return;
        try {
          await api("/api/v1/transactions/" + encodeURIComponent(item.id), { method: "DELETE" });
          await loadFinanceData();
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
    const values = await showAppDialog({title:"Edit transaction",fields:[
      {name:"transaction_date",label:"Transaction date",type:"date",value:item.transaction_date,required:true},
      {name:"description",label:"Description",value:item.description,required:true,maxLength:500},
      {name:"reference",label:"Reference",value:item.reference || "",maxLength:160},
      {name:"amount",label:"Amount (negative for debit)",type:"number",value:item.amount,required:true,step:"0.01"},
      {name:"category",label:"Category",type:"select",value:item.category || "",options:[
        {value:"",label:"Uncategorised"},...state.categories.filter((entry)=>entry.is_active).map((entry)=>({value:entry.name,label:entry.name}))
      ]},
      {name:"notes",label:"Notes",type:"textarea",value:item.notes || "",maxLength:2000}
    ]});
    if (!values) return;
    try {
      await api("/api/v1/transactions/" + encodeURIComponent(item.id), {
        method:"PATCH",
        body:JSON.stringify({...values,amount:Number(values.amount).toFixed(2),reference:values.reference || null,category:values.category || null,notes:values.notes || null})
      });
      await loadFinanceData();
    } catch(error){globalMessage(error.message,true);}
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
      card.append(el("p", money(budget.spent, budget.currency) + " recorded across selected categories · " + money(budget.remaining, budget.currency) + " remaining · " + percent.toFixed(1) + "% used", "muted small"));
      card.append(el("p", "Categories: " + (budget.categories || [budget.category]).join(", "), "muted small"));
      const actions = el("div",undefined,"record-actions");
      const edit = el("button","Edit budget","button button-secondary"); edit.type="button";
      edit.addEventListener("click",async()=>{
        const values=await showAppDialog({title:"Edit budget",fields:[
          {name:"name",label:"Budget name",value:budget.name,required:true,maxLength:100},
          {name:"categories",label:"Categories (comma-separated)",value:(budget.categories || [budget.category]).join(", "),required:true,maxLength:1200},
          {name:"amount",label:"Budget limit",type:"number",value:budget.amount,required:true,min:0.01,step:0.01},
          {name:"period",label:"Period",type:"select",value:budget.period,options:[{value:"weekly",label:"Weekly"},{value:"monthly",label:"Monthly"},{value:"quarterly",label:"Quarterly"},{value:"yearly",label:"Yearly"}]},
          {name:"start_date",label:"Start date",type:"date",value:budget.start_date,required:true},
          {name:"end_date",label:"End date",type:"date",value:budget.end_date || ""}
        ]});
        if(!values)return;
        try{
          const categories=values.categories.split(",").map(v=>v.trim()).filter(Boolean);
          await api("/api/v1/budgets/"+encodeURIComponent(budget.id),{method:"PATCH",body:JSON.stringify({
            name:values.name,categories,category:categories[0],amount:Number(values.amount).toFixed(2),
            period:values.period,start_date:values.start_date,end_date:values.end_date || null
          })});
          await loadFinanceData();
        }catch(error){globalMessage(error.message,true);}
      });
      const remove=el("button","Delete","button button-quiet");remove.type="button";
      remove.addEventListener("click",async()=>{
        if(!await confirmInApp("Delete this budget? Its record will be deactivated and won't be used for future progress."))return;
        try{await api("/api/v1/budgets/"+encodeURIComponent(budget.id),{method:"DELETE"});await loadFinanceData();}
        catch(error){globalMessage(error.message,true);}
      });
      actions.append(edit,remove);card.append(actions);
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
          await loadFinanceData();
        } catch (error) {
          globalMessage(error.message, true);
        }
      });
      card.append(form);
      const actions=el("div",undefined,"record-actions");
      const edit=el("button","Edit goal","button button-secondary");edit.type="button";
      edit.addEventListener("click",async()=>{
        const values=await showAppDialog({title:"Edit financial goal",fields:[
          {name:"name",label:"Goal name",value:goal.name,required:true,maxLength:100},
          {name:"description",label:"Description",type:"textarea",value:goal.description || "",maxLength:1000},
          {name:"target_amount",label:"Target amount",type:"number",value:goal.target_amount,required:true,min:0.01,step:0.01},
          {name:"target_date",label:"Target date",type:"date",value:goal.target_date || ""}
        ]});
        if(!values)return;
        try{await api("/api/v1/goals/"+encodeURIComponent(goal.id),{method:"PATCH",body:JSON.stringify({
          name:values.name,description:values.description || null,target_amount:Number(values.target_amount).toFixed(2),target_date:values.target_date || null
        })});await loadFinanceData();}
        catch(error){globalMessage(error.message,true);}
      });
      const remove=el("button","Delete goal","button button-quiet");remove.type="button";
      remove.addEventListener("click",async()=>{
        if(!await confirmInApp("Delete this goal? Its record will be deactivated. Existing contribution history will be retained."))return;
        try{await api("/api/v1/goals/"+encodeURIComponent(goal.id),{method:"DELETE"});await loadFinanceData();}
        catch(error){globalMessage(error.message,true);}
      });
      actions.append(edit,remove);card.append(actions);
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
      details.append(el("h3", (item.source || "FNB_CSV").replaceAll("_", " ") + " import"));
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
      const total=Number(item.transaction_count || 0);
      const finished=Number(item.imported_count || 0)+Number(item.duplicate_count || 0);
      const percent=item.status==="completed" ? 100 : (total ? Math.min(99,finished/total*100) : 0);
      const progress=el("div",undefined,"progress import-progress");
      const fill=el("span");fill.style.width=percent+"%";progress.append(fill);card.append(progress);
      card.append(el("p",Math.round(percent)+"% processed","muted small"));
      card.append(el(
        "p",
        "Started: " + (item.started_at || item.created_at || "Not available") +
        " · Completed: " + (item.completed_at || "Not completed"),
        "muted small"
      ));
      target.append(card);
    });
  }

  function renderDebts(debts, summary) {
    state.debts = debts || [];
    state.debtSummary = summary || null;
    const currencies = summary && summary.currencies ? summary.currencies : [];
    const buildCards = (target, compact) => {
      target.replaceChildren();
      if (!currencies.length) {
        const card = el("article", undefined, "metric-card");
        card.append(el("span", "Outstanding debt"), el("strong", "No recorded debt"), el("small", "Add debts to track balances and repayments"));
        target.append(card);
        return;
      }
      currencies.forEach((item) => {
        const outstanding = el("article", undefined, "metric-card");
        outstanding.append(el("span", "Outstanding debt · " + item.currency));
        outstanding.append(el("strong", money(item.outstanding_total, item.currency)));
        outstanding.append(el("small", item.debt_count + " active debts · Original " + money(item.original_total, item.currency)));
        if (compact) {
          outstanding.append(el("small", "Monthly repayments " + money(item.monthly_repayments, item.currency)));
          outstanding.append(el("small", "Average monthly income " + money(item.average_monthly_income, item.currency)));
          outstanding.append(el("small", "Repayment-to-income " + (item.debt_to_income_percent === null ? "Not available" : Number(item.debt_to_income_percent).toFixed(1) + "%")));
          outstanding.append(el("small", item.trend === "increasing" ? "Debt increasing" : item.trend === "decreasing" ? "Debt decreasing" : item.trend === "unchanged" ? "No change" : "Trend needs more history"));
          target.append(outstanding);
          return;
        }
        target.append(outstanding);
        const repayment = el("article", undefined, "metric-card");
        repayment.append(el("span", "Monthly repayments · " + item.currency));
        repayment.append(el("strong", money(item.monthly_repayments, item.currency)));
        repayment.append(el("small", "Average monthly income " + money(item.average_monthly_income, item.currency)));
        target.append(repayment);
        const ratio = el("article", undefined, "metric-card");
        ratio.append(el("span", "Debt-to-income · " + item.currency));
        ratio.append(el("strong", item.debt_to_income_percent === null ? "Not available" : Number(item.debt_to_income_percent).toFixed(1) + "%"));
        ratio.append(el("small", "Monthly repayments compared with average monthly income"));
        target.append(ratio);
        const trend = el("article", undefined, "metric-card");
        trend.append(el("span", "Balance trend · " + item.currency));
        trend.append(el("strong", item.trend === "increasing" ? "Debt increasing" : item.trend === "decreasing" ? "Debt decreasing" : item.trend === "unchanged" ? "No change" : "Building history"));
        trend.append(el("small", item.trend === "insufficient_history" ? "Update balances to establish a trend" : "Recorded change " + money(item.balance_change, item.currency)));
        target.append(trend);
      });
    };
    buildCards($("debt-summary-cards"), false);
    buildCards($("debt-overview-cards"), true);
    const list = $("debt-list");
    list.replaceChildren();
    if (!state.debts.length) list.append(el("p", "No debts recorded. Add a debt above to begin tracking.", "empty-state"));
    state.debts.forEach((debt) => {
      const card = el("article", undefined, "record-card");
      const top = el("div", undefined, "record-card-top");
      const details = el("div");
      details.append(el("h3", debt.debt_name));
      details.append(el("p", debt.creditor + " · " + debt.debt_type.replaceAll("_", " ") + " · " + debt.status));
      top.append(details, el("strong", money(debt.current_balance, debt.currency)));
      card.append(top);
      card.append(el("p", "Original " + money(debt.original_amount, debt.currency) + " · Monthly repayment " + money(debt.monthly_payment, debt.currency) + (debt.interest_rate === null ? "" : " · Interest " + debt.interest_rate + "%"), "muted small"));
      const actions = el("div", undefined, "record-actions");
      const update = el("button", "Update balance", "button button-secondary");
      update.type = "button";
      update.addEventListener("click", async () => {
        const value = window.prompt("Enter the latest outstanding balance", String(debt.current_balance));
        if (value === null) return;
        const amount = Number(value);
        if (!Number.isFinite(amount) || amount < 0) {
          globalMessage("Enter a valid outstanding balance.", true);
          return;
        }
        try {
          await api("/api/v1/debts/" + encodeURIComponent(debt.id), {method:"PATCH",body:JSON.stringify({current_balance:amount.toFixed(2)})});
          await loadFinanceData();
        } catch (error) { globalMessage(error.message, true); }
      });
      const edit = el("button", "Edit details", "button button-secondary");
      edit.type = "button";
      edit.addEventListener("click", async () => {
        const creditor = window.prompt("Creditor / lender", debt.creditor);
        if (creditor === null) return;
        const name = window.prompt("Debt name", debt.debt_name);
        if (name === null) return;
        const payment = window.prompt("Monthly repayment", String(debt.monthly_payment));
        if (payment === null) return;
        const rate = window.prompt("Annual interest rate (%)", debt.interest_rate === null ? "" : String(debt.interest_rate));
        if (rate === null) return;
        const amount = Number(payment);
        const interest = rate.trim() ? Number(rate) : null;
        if (!creditor.trim() || !name.trim() || !Number.isFinite(amount) || amount < 0 || (interest !== null && (!Number.isFinite(interest) || interest < 0 || interest > 100))) {
          globalMessage("Enter valid creditor, debt name, repayment and interest values.", true);
          return;
        }
        try {
          await api("/api/v1/debts/" + encodeURIComponent(debt.id), {method:"PATCH",body:JSON.stringify({creditor:creditor.trim(),debt_name:name.trim(),monthly_payment:amount.toFixed(2),interest_rate:interest===null?null:interest.toFixed(3)})});
          await loadFinanceData();
        } catch (error) { globalMessage(error.message, true); }
      });
      actions.append(update, edit);
      card.append(actions);
      const history = debt.balance_history || [];
      card.append(el("p", history.length > 1 ? "Balance updates recorded: " + (history.length - 1) : "Initial balance recorded. Update it over time to track the trend.", "muted small"));
      list.append(card);
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
    $("import-confirm-form").classList.remove("hidden");
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
    updateImportConfirmState();
  }

  async function loadFinanceData() {
    // Treat every module, including Accounts, as an independent request. A
    // failed account-list request must not prevent the rest of the workspace
    // from loading or make every navigation view appear broken.
    const paths = [
      "/api/v1/accounts",
      "/api/v1/categories",
      "/api/v1/transactions?limit=100",
      "/api/v1/budgets/progress",
      "/api/v1/goals",
      "/api/v1/debts",
      "/api/v1/analytics/debts",
      "/api/v1/analytics/summary",
      "/api/v1/analytics/recurring-payments",
      "/imports",
    ];
    if (state.loadingFinanceData) return;
    state.loadingFinanceData = true;
    const results = [];
    for (const path of paths) {
      try { results.push({status:"fulfilled",value:await api(path)}); }
      catch (reason) { results.push({status:"rejected",reason}); }
    }
    const value = (index, fallback) =>
      results[index].status === "fulfilled" ? results[index].value : fallback;
    const failed = results
      .map((result, index) => result.status === "rejected" ? index : -1)
      .filter((index) => index >= 0);
    const gateDisabled = results.some((result) =>
      result.status === "rejected" &&
      result.reason instanceof ApiError &&
      result.reason.status === 503 &&
      /financial data storage is disabled/i.test(result.reason.message)
    );

    setGate(!gateDisabled);
    state.accounts = value(0, []);
    state.categories = value(1, []);
    refreshSelects();
    renderAccounts();
    renderCategories();
    renderTransactions((value(2, {items: []}).items) || []);
    renderBudgets(value(3, []));
    renderGoals(value(4, []));
    renderDebts(value(5, []), value(6, null));
    renderSummary(value(7, null), value(8, []));
    renderImportHistory(value(9, []));
    updateImportConfirmState();

    if (failed.length) {
      const names = [
        "accounts", "categories", "transactions", "budget progress", "goals",
        "debts", "debt analytics", "financial analytics", "recurring payments",
        "import history",
      ];
      globalMessage(
        "Some sections could not be refreshed: " +
        failed.map((index) => names[index]).join(", ") +
        ". Other available sections remain usable. Retry the affected section.",
        true
      );
    } else {
      globalMessage("", false);
    }
    state.loadingFinanceData = false;
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
    if (!state.financeRefreshTimer) {
      state.financeRefreshTimer = window.setInterval(() => {
        if (state.user && !document.hidden) loadFinanceData();
      }, 45000);
    }
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
      await api("/auth/token", {
        method: "POST",
        body: JSON.stringify({
          email: $("email").value.trim(),
          password: $("password").value,
        }),
      });
      // The access token is held in an HttpOnly cookie, not JavaScript memory.
      state.token = null;
      state.user = await api("/auth/me");
      $("password").value = "";
      message("login-message", "", "");
      await beginWorkspace();
    } catch (error) {
      state.token = null;
      fetch("/auth/logout", { method: "POST", credentials: "same-origin" }).catch(() => {});
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
  async function runRefresh(buttonId, label, operation) {
    const button = $(buttonId);
    if (button.disabled) return;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "Refreshing...";
    try {
      await operation();
      globalMessage(label + " refreshed.", false);
    } catch (error) {
      globalMessage(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = originalText;
    }
  }

  $("refresh-accounts").addEventListener("click", () => runRefresh(
    "refresh-accounts", "Accounts", async () => {
      state.accounts = await api("/api/v1/accounts");
      refreshSelects();
      renderAccounts();
      updateImportConfirmState();
    }
  ));
  $("refresh-import-history").addEventListener("click", () => runRefresh(
    "refresh-import-history", "Import history", async () => renderImportHistory(await api("/imports"))
  ));

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
  $("refresh-transactions").addEventListener("click", () => runRefresh(
    "refresh-transactions", "Transactions", async () => {
      const params = new URLSearchParams();
      [["account_id","transaction-account-filter"],["from_date","transaction-from"],
       ["to_date","transaction-to"],["search","transaction-search"]].forEach((item) => {
        const value = $(item[1]).value.trim();
        if (value) params.set(item[0], value);
      });
      const data = await api("/api/v1/transactions?" + params.toString());
      renderTransactions(data.items || []);
    }
  ));

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
      const extension = state.selectedFile.name.toLowerCase().split(".").pop();
      const confirmPath = extension === "pdf" ? "/imports/fnb/pdf/confirm" : "/imports/fnb/csv/confirm";
      const result = await api(confirmPath, { method: "POST", body: form });
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
          categories: Array.from($("budget-category").selectedOptions).map((option)=>option.value),
          category: Array.from($("budget-category").selectedOptions).map((option)=>option.value)[0],
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
  $("refresh-budgets").addEventListener("click", () => runRefresh(
    "refresh-budgets", "Budgets", async () => renderBudgets(await api("/api/v1/budgets/progress"))
  ));

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
  $("refresh-goals").addEventListener("click", () => runRefresh(
    "refresh-goals", "Goals", async () => renderGoals(await api("/api/v1/goals"))
  ));

  $("debt-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/v1/debts", {
        method: "POST",
        body: JSON.stringify({
          creditor: $("debt-creditor").value.trim(),
          debt_name: $("debt-name").value.trim(),
          debt_type: $("debt-type").value,
          original_amount: Number($("debt-original").value).toFixed(2),
          current_balance: Number($("debt-balance").value).toFixed(2),
          monthly_payment: Number($("debt-payment").value || 0).toFixed(2),
          interest_rate: $("debt-rate").value ? Number($("debt-rate").value).toFixed(3) : null,
          currency: "ZAR",
          opened_date: $("debt-opened").value || null,
          due_date: $("debt-due").value || null,
          notes: $("debt-notes").value.trim() || null,
        }),
      });
      event.target.reset();
      $("debt-payment").value = "0";
      message("debt-message", "Debt saved.", "success");
      await loadFinanceData();
    } catch (error) {
      message("debt-message", error.message, "error");
    }
  });
  $("refresh-debts").addEventListener("click", () => runRefresh(
    "refresh-debts", "Debts", async () => {
      const [debts, analytics] = await Promise.all([
        api("/api/v1/debts"), api("/api/v1/analytics/debts")
      ]);
      renderDebts(debts, analytics);
    }
  ));


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
  $("refresh-categories").addEventListener("click", () => runRefresh(
    "refresh-categories", "Categories", async () => {
      state.categories = await api("/api/v1/categories");
      refreshSelects();
      renderCategories();
    }
  ));

  $("advisor-consent").addEventListener("change", () => {
    $("advisor-submit").disabled = !state.financeEnabled || !$("advisor-consent").checked;
  });

  $("advisor-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const answer = $("advisor-answer");
    answer.classList.remove("hidden");
    answer.textContent = "Preparing your complete approved financial records and contacting IBM watsonx.ai...";
    try {
      const result = await api("/api/v1/advisor/chat", {
        method: "POST",
        body: JSON.stringify({
          question: $("advisor-question").value.trim(),
          consent_to_share_all_financial_records: true,
        }),
      });
      answer.textContent = result.answer + "\n\nData shared: " + result.data_shared.join("; ") + ".";
    } catch (error) {
      answer.textContent = error.message;
    }
  });

  async function loadDiagnostics() {
    const target = $("diagnostics-list");
    target.replaceChildren();
    try {
      const records = await api("/api/v1/diagnostics?limit=50");
      if (!records.length) {
        target.append(el("p", "No application errors have been recorded.", "empty-state"));
        return;
      }
      records.forEach((record) => {
        const card = el("article", undefined, "record-card");
        const top = el("div", undefined, "record-card-top");
        const details = el("div");
        details.append(el("h3", record.exception_type || "Application error"));
        details.append(el("p",
          (record.occurred_at || "") + " · HTTP " + record.status_code +
          " · " + record.method + " " + record.path
        ));
        top.append(details, el("span", record.diagnostic_id || "No reference", "status-pill status-error"));
        card.append(top);
        card.append(el("p", record.message || "No additional error message.", "muted small"));
        const disclosure = el("details");
        const summary = el("summary", "Technical details");
        const stack = el("pre", record.stack_trace || "No stack trace recorded.");
        stack.className = "diagnostic-stack";
        disclosure.append(summary, stack);
        card.append(disclosure);
        target.append(card);
      });
    } catch (error) {
      throw error;
    }
  }

  $("refresh-diagnostics-button").addEventListener("click", () => runRefresh(
    "refresh-diagnostics-button", "System diagnostics", loadDiagnostics
  ));

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
      throw error;
    }
  }

  $("refresh-audit-button").addEventListener("click", () => runRefresh(
    "refresh-audit-button", "Account activity", loadAuditHistory
  ));

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
      fetch("/auth/logout", { method: "POST", credentials: "same-origin" }).catch(() => {});
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

  async function restoreSession() {
    try {
      state.user = await api("/auth/me");
      await beginWorkspace();
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) {
        globalMessage(error.message, true);
      }
    }
  }
  restoreSession();

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
