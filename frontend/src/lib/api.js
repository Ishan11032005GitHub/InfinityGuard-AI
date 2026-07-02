import { accountStorageKey, isSeededDemoAccount, readStoredUser } from "./account.js";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const OFFLINE_DEMO_ENABLED = import.meta.env.VITE_ENABLE_OFFLINE_DEMO === "true";

const demoCustomers = [
  { id: 1, country: "US", risk_rating: "Low", kyc_status: "Verified", name: "Northstar Robotics", currency: "USD", avg_delay_days: 2 },
  { id: 2, country: "AE", risk_rating: "Medium", kyc_status: "Verified", name: "Kairo Retail Group", currency: "AED", avg_delay_days: 7 },
  { id: 3, country: "DE", risk_rating: "Low", kyc_status: "Verified", name: "Blue Harbor GmbH", currency: "EUR", avg_delay_days: 1 },
  { id: 4, country: "JP", risk_rating: "Medium", kyc_status: "Review", name: "Sakura Supply KK", currency: "JPY", avg_delay_days: 9 },
  { id: 5, country: "ZA", risk_rating: "High", kyc_status: "Review", name: "Atlas Minerals", currency: "ZAR", avg_delay_days: 13 },
  { id: 6, country: "CA", risk_rating: "Low", kyc_status: "Verified", name: "Maple Cloud Ltd", currency: "CAD", avg_delay_days: 3 },
];

const demoInvoices = [
  { invoice_number: "INV-2026-1041", id: 42, currency: "CAD", status: "paid", due_date: "2025-10-04", paid_at: "2025-10-18", amount: 12835.97 },
  { invoice_number: "INV-2026-1040", id: 41, currency: "ZAR", status: "pending", due_date: "2025-10-10", paid_at: "", amount: 58943.1 },
  { invoice_number: "INV-2026-1039", id: 40, currency: "JPY", status: "paid", due_date: "2025-10-16", paid_at: "2025-10-30", amount: 23990.25 },
  { invoice_number: "INV-2026-1038", id: 39, currency: "EUR", status: "paid", due_date: "2025-10-22", paid_at: "2025-11-07", amount: 34858.54 },
  { invoice_number: "INV-2026-1037", id: 38, currency: "AED", status: "paid", due_date: "2025-10-28", paid_at: "2025-11-07", amount: 16538.53 },
  { invoice_number: "INV-2026-1036", id: 37, currency: "USD", status: "pending", due_date: "2025-11-03", paid_at: "", amount: 15956.57 },
  { invoice_number: "INV-2026-1032", id: 33, currency: "EUR", status: "pending", due_date: "2025-11-27", paid_at: "", amount: 64381.63 },
];

const basePayments = [
  { id: 1, recipient: "Kairo Retail Group", country: "AE", rail: "SWIFT", external_ref: "pay_00001", invoice_id: 2, customer_id: 2, amount: 5538.38, currency: "AED", status: "settled" },
  { id: 3, recipient: "Sakura Supply KK", country: "JP", rail: "SWIFT", external_ref: "pay_00003", invoice_id: 4, customer_id: 4, amount: 10585.51, currency: "JPY", status: "settled" },
  { id: 2, recipient: "Blue Harbor GmbH", country: "DE", rail: "SWIFT", external_ref: "pay_00002", invoice_id: 3, customer_id: 3, amount: 14872.34, currency: "EUR", status: "settled" },
  { id: 4, recipient: "Maple Cloud Ltd", country: "CA", rail: "ACH", external_ref: "pay_00005", invoice_id: 6, customer_id: 6, amount: 22461.86, currency: "CAD", status: "settled" },
  { id: 5, recipient: "Northstar Robotics", country: "US", rail: "ACH", external_ref: "pay_00006", invoice_id: 7, customer_id: 1, amount: 19705.27, currency: "USD", status: "settled" },
  { id: 10, recipient: "Kairo Retail Group", country: "AE", rail: "SWIFT", external_ref: "pay_00013", invoice_id: 14, customer_id: 2, amount: 69280.95, currency: "AED", status: "settled" },
];

const defaultDemoAccounts = [
  { email: "asha.demo@ledgerops.ai", name: "Asha Mehta", balance: 25000, currency: "INR" },
  { email: "rohan.demo@ledgerops.ai", name: "Rohan Kapoor", balance: 18000, currency: "INR" },
];

function scopedKey(name, user = readStoredUser()) {
  return `${name}:${accountStorageKey(user)}`;
}

function storedPayments(user = readStoredUser()) {
  try {
    return JSON.parse(localStorage.getItem(scopedKey("ig_demo_payments", user)) || "[]");
  } catch {
    localStorage.removeItem(scopedKey("ig_demo_payments", user));
    return [];
  }
}

function storedMethods(user = readStoredUser()) {
  try {
    return JSON.parse(localStorage.getItem(scopedKey("ig_demo_methods", user)) || "[]");
  } catch {
    localStorage.removeItem(scopedKey("ig_demo_methods", user));
    return [];
  }
}

function storedQuickLinks(user = readStoredUser()) {
  try {
    return JSON.parse(localStorage.getItem(scopedKey("ig_quicklinks", user)) || "[]");
  } catch {
    localStorage.removeItem(scopedKey("ig_quicklinks", user));
    return [];
  }
}

function storedCompanyUsers() {
  try {
    return JSON.parse(localStorage.getItem("ig_company_users") || "[]");
  } catch {
    localStorage.removeItem("ig_company_users");
    return [];
  }
}

function saveCompanyUsers(users) {
  localStorage.setItem("ig_company_users", JSON.stringify(users));
}

function demoUser(payload = {}) {
  const accountType = payload.account_type || payload.accountType || "company";
  return {
    id: payload.email ? Math.abs([...payload.email].reduce((sum, char) => sum + char.charCodeAt(0), 0)) : 999,
    email: payload.email || "admin@ledgerops.ai",
    name: payload.name || "Avery Shah",
    role: accountType === "individual" ? "Admin" : payload.role || "Admin",
    account_type: accountType,
    workspace_name: payload.workspace_name || payload.workspaceName || (accountType === "individual" ? `${payload.name || "Personal"} account` : "LedgerOps workspace"),
  };
}

function demoTokenPair(user) {
  return { access_token: "offline-demo-token", refresh_token: "offline-demo-refresh", token_type: "bearer", user };
}

function demoResponse(path, options = {}) {
  const method = options.method || "GET";
  const body = options.body ? JSON.parse(options.body) : {};
  const employee = path === "/api/auth/login" ? storedCompanyUsers().find((member) => member.email.toLowerCase() === String(body.email || "").toLowerCase()) : null;
  if (path === "/api/auth/login" && employee && employee.demo_password && employee.demo_password !== body.password) throw new Error("Invalid credentials");
  const activeUser = path === "/api/auth/login" && employee ? employee : path === "/api/auth/login" || path === "/api/auth/signup" ? demoUser(body) : demoUser(readStoredUser());
  const seededDemo = isSeededDemoAccount(activeUser);
  const accountPayments = storedPayments(activeUser);
  const accountMethods = storedMethods(activeUser);
  const payments = seededDemo ? [...accountPayments, ...basePayments] : accountPayments;
  const invoices = seededDemo ? demoInvoices : [];
  const customers = seededDemo ? demoCustomers : [];
  const alerts = seededDemo ? [
    { severity: "medium", category: "cash", message: "Delayed invoices could reduce runway below 60 days." },
    { severity: "medium", category: "fx", message: "EUR exposure rose 18% while volatility is trending upward." },
    { severity: "high", category: "fraud", message: "JPY payment pattern changed outside normal settlement window." },
  ] : [];

  if (path === "/api/auth/login") return demoTokenPair(activeUser);
  if (path === "/api/auth/signup") return demoTokenPair(demoUser(body));
  if (path === "/api/auth/me" && method === "GET") return demoUser(JSON.parse(localStorage.getItem("ig_user") || "{}"));
  if (path === "/api/auth/me" && method === "PATCH") {
    const user = { ...demoUser(JSON.parse(localStorage.getItem("ig_user") || "{}")), name: body.name };
    return user;
  }
  if (path === "/api/auth/password" && method === "POST") return { status: "updated" };
  if (path === "/api/auth/forgot-password" && method === "POST") {
    return {
      message: "If this email is registered, a password reset link has been prepared.",
      reset_url: `${window.location.origin}/reset-password?token=offline-reset-token-for-local-testing`,
    };
  }
  if (path === "/api/auth/reset-password" && method === "POST") return { status: "updated", message: "Password reset complete. You can now sign in." };
  if (path === "/api/auth/preferences" && method === "GET") return JSON.parse(localStorage.getItem(scopedKey("ig_preferences", activeUser)) || JSON.stringify({ paymentAlerts: true, riskAlerts: true, weeklyDigest: false, currency: "USD", timezone: "Asia/Kolkata", oneTimePaymentLimit: 5000 }));
  if (path === "/api/auth/preferences" && method === "PATCH") {
    localStorage.setItem(scopedKey("ig_preferences", activeUser), JSON.stringify(body));
    return body;
  }
  if (path === "/api/auth/company/users" && method === "GET") {
    const members = storedCompanyUsers().filter((member) => member.workspace_name === activeUser.workspace_name);
    const owner = { ...activeUser, is_active: true, created_at: new Date().toISOString() };
    return [owner, ...members.filter((member) => member.email !== owner.email)];
  }
  if (path === "/api/auth/company/users" && method === "POST") {
    if (activeUser.account_type !== "company" || activeUser.role !== "Admin") throw new Error("Only company admins can manage employee accounts");
    const existing = storedCompanyUsers().find((member) => member.email.toLowerCase() === String(body.email || "").toLowerCase());
    if (existing) throw new Error("Email already registered");
    const member = {
      id: Date.now(),
      email: body.email,
      name: body.name,
      role: body.role || "Viewer",
      account_type: "company",
      workspace_name: activeUser.workspace_name,
      is_active: true,
      created_at: new Date().toISOString(),
      demo_password: body.password,
    };
    saveCompanyUsers([member, ...storedCompanyUsers()]);
    return member;
  }
  if (path === "/api/payments") return payments;
  if (path === "/api/invoices") return invoices;
  if (path === "/api/customers") return customers;
  if (path === "/api/alerts") return alerts;
  if (path === "/api/payment-app/audit-log") {
    return [
      { id: 1, created_at: new Date().toISOString(), action: "QuickLink created", entity_type: "quicklink", outcome: "success" },
      { id: 2, created_at: new Date(Date.now() - 3600000).toISOString(), action: "Payment reconciled", entity_type: "payment", outcome: "success" },
      { id: 3, created_at: new Date(Date.now() - 7200000).toISOString(), action: "CSV exported", entity_type: "report", outcome: "success" },
    ];
  }
  if (path === "/api/dashboard") {
    const currencyExposure = seededDemo ? { USD: 15956, EUR: 99240, JPY: 23990, AED: 85819, CAD: 35300, ZAR: 58943 } : {};
    return {
      total_volume: payments.reduce((sum, payment) => sum + Number(payment.amount || 0), 0),
      pending_invoices: invoices.filter((invoice) => invoice.status === "pending").length,
      cash_runway: seededDemo ? 49 : 0,
      currency_exposure: currencyExposure,
      risk_score: seededDemo ? 77.5 : 0,
      alerts,
      monthly_transactions: seededDemo ? [
        { month: "Oct", volume: 38000 }, { month: "Nov", volume: 84000 }, { month: "Dec", volume: 208000 },
        { month: "Jan", volume: 229000 }, { month: "Feb", volume: 235000 }, { month: "Mar", volume: 111000 },
        { month: "Apr", volume: 137000 }, { month: "May", volume: 108000 }, { month: "Jun", volume: 6000 },
      ] : [],
      cash_flow: seededDemo ? [
        { month: "Oct", incoming: 38000, expenses: 21000 }, { month: "Nov", incoming: 84000, expenses: 50000 },
        { month: "Dec", incoming: 208000, expenses: 120000 }, { month: "Jan", incoming: 236000, expenses: 134000 },
        { month: "Feb", incoming: 242000, expenses: 137000 }, { month: "Mar", incoming: 109000, expenses: 63000 },
        { month: "Apr", incoming: 138000, expenses: 81000 }, { month: "May", incoming: 107000, expenses: 62000 },
        { month: "Jun", incoming: 6000, expenses: 3000 },
      ] : [],
      fx_trends: seededDemo ? Array.from({ length: 35 }, (_, index) => ({ currency: ["EUR", "AED", "ZAR", "JPY"][index % 4], rate: 0.6 + (index % 7) / 10, volatility: 18 + ((index * 13) % 62) })) : [],
      country_heatmap: seededDemo ? [
        { country: "CA", volume: 239389 }, { country: "JP", volume: 219244 }, { country: "DE", volume: 162469 },
        { country: "AE", volume: 304613 }, { country: "ZA", volume: 95666 }, { country: "US", volume: 130398 },
      ] : [],
      anomalies: seededDemo ? [{ name: "Atlas Minerals", score: 76, amount: 58943 }, { name: "Sakura Supply KK", score: 82, amount: 23990 }] : [],
    };
  }
  if (path === "/api/payment-app/status") {
    return { provider: "Secure card network", processor: "offline-demo", mode: "offline test", connected: true, sync_health: payments.length ? "offline_ready" : "needs_data", last_payment_at: null, last_sync_at: localStorage.getItem(scopedKey("ig_demo_last_sync", activeUser)), webhook_events: accountPayments.length + (seededDemo ? 3 : 0), mapped_payments: payments.length, saved_methods: accountMethods.length, issuer_agnostic: true, card_networks: ["Visa", "Mastercard", "RuPay (demo)"] };
  }
  if (path === "/api/payment-app/demo/public-accounts" && method === "GET") return defaultDemoAccounts;
  if (path === "/api/payment-app/demo/public-reset" && method === "POST") {
    return {
      status: "reset",
      balances: Object.fromEntries(defaultDemoAccounts.map((account) => [account.email, account.balance])),
      currency: "INR",
    };
  }
  if (path === "/api/payment-app/connect" && method === "POST") {
    localStorage.setItem(scopedKey("ig_demo_payment_connected", activeUser), "true");
    return { status: "connected", provider: body.provider || "Card processor", account_name: body.account_name || "LedgerOps Treasury", mode: body.mode || "test", event_id: Date.now() };
  }
  if (path === "/api/payment-app/sync-demo" && method === "POST") {
    const payment = { id: Date.now(), country: "US", rail: "Card processor", external_ref: `card_sync_${Date.now()}`, invoice_id: "", customer_id: 1, amount: 18420.75 };
    localStorage.setItem(scopedKey("ig_demo_payments", activeUser), JSON.stringify([payment, ...storedPayments(activeUser)]));
    localStorage.setItem(scopedKey("ig_demo_last_sync", activeUser), new Date().toISOString());
    return { status: "synced", imported_payments: 1, payment_id: payment.id, external_ref: payment.external_ref, event_id: Date.now() };
  }
  if (path === "/api/payment-app/payment-link" && method === "POST") {
    const invoice = invoices.find((item) => item.id === body.invoice_id);
    if (!invoice) throw new Error("No pending invoices are available for this account yet.");
    return { status: "created", provider: "Card processor", invoice_number: invoice.invoice_number, amount: invoice.amount, currency: invoice.currency, checkout_url: `https://checkout.stripe.com/c/pay/ig_chk_${invoice.id}_${Date.now()}` };
  }
  if (path === "/api/payment-app/quicklinks" && method === "GET") return storedQuickLinks(activeUser);
  if (path === "/api/payment-app/quicklinks" && method === "POST") {
    const link = {
      id: Date.now(),
      public_id: `demo_${Date.now()}`,
      ...body,
      status: "active",
      provider: "LedgerOps Demo Network",
      mode: "demo",
      checkout_id: `ql_demo_${Date.now()}`,
      checkout_url: `${window.location.origin}/quicklinks?demo_checkout=${Date.now()}`,
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + Number(body.expires_in_days || 14) * 86400000).toISOString(),
      remittance_available: false,
    };
    localStorage.setItem(scopedKey("ig_quicklinks", activeUser), JSON.stringify([link, ...storedQuickLinks(activeUser)]));
    return link;
  }
  if (path.match(/^\/api\/payment-app\/quicklinks\/\d+\/verify$/) && method === "POST") {
    const linkId = Number(path.split("/")[4]);
    let result;
    const links = storedQuickLinks(activeUser).map((item) => {
      if (item.id !== linkId) return item;
      result = { ...item, status: "paid", paid_at: new Date().toISOString(), payment_id: Date.now(), remittance_available: true };
      return result;
    });
    localStorage.setItem(scopedKey("ig_quicklinks", activeUser), JSON.stringify(links));
    if (!result) throw new Error("QuickLink not found");
    return result;
  }
  if (path.match(/^\/api\/payment-app\/quicklinks\/\d+\/approve$/) && method === "POST") {
    const linkId = Number(path.split("/")[4]);
    let result;
    const links = storedQuickLinks(activeUser).map((item) => {
      if (item.id !== linkId) return item;
      result = {
        ...item,
        status: "active",
        checkout_id: item.checkout_id || `ql_demo_${Date.now()}`,
        checkout_url: item.checkout_url || `${window.location.origin}/quicklinks?demo_checkout=${Date.now()}`,
      };
      return result;
    });
    localStorage.setItem(scopedKey("ig_quicklinks", activeUser), JSON.stringify(links));
    if (!result) throw new Error("QuickLink not found");
    return { ...result, message: "Manual compliance approved. Checkout is ready to share." };
  }
  if (path.match(/^\/api\/payment-app\/quicklinks\/\d+\/refund$/) && method === "POST") {
    const linkId = Number(path.split("/")[4]);
    let result;
    const links = storedQuickLinks(activeUser).map((item) => {
      if (item.id !== linkId) return item;
      result = { ...item, status: "refunded" };
      return result;
    });
    localStorage.setItem(scopedKey("ig_quicklinks", activeUser), JSON.stringify(links));
    if (!result) throw new Error("QuickLink not found");
    return { status: "succeeded", amount: result.amount, currency: result.currency, quicklink_status: "refunded" };
  }
  if (path.match(/^\/api\/payment-app\/quicklinks\/\d+$/) && method === "DELETE") {
    const linkId = Number(path.split("/")[4]);
    let result;
    const links = storedQuickLinks(activeUser).map((item) => {
      if (item.id !== linkId) return item;
      result = { ...item, status: "disabled" };
      return result;
    });
    localStorage.setItem(scopedKey("ig_quicklinks", activeUser), JSON.stringify(links));
    if (!result) throw new Error("QuickLink not found");
    return result;
  }
  if (path === "/api/payment-app/payment-methods" && method === "GET") return accountMethods;
  if (path === "/api/payment-app/payment-methods/setup" && method === "POST") return { mode: "manual" };
  if (path === "/api/payment-app/payment-methods" && method === "POST") {
    const methods = storedMethods(activeUser);
    const saved = { id: Date.now(), ...body, is_default: methods.length === 0 };
    localStorage.setItem(scopedKey("ig_demo_methods", activeUser), JSON.stringify([saved, ...methods]));
    return saved;
  }
  if (path.match(/^\/api\/payment-app\/payment-methods\/\d+\/default$/) && method === "PATCH") {
    const methodId = Number(path.split("/")[4]);
    const methods = storedMethods(activeUser).map((item) => ({ ...item, is_default: item.id === methodId }));
    localStorage.setItem(scopedKey("ig_demo_methods", activeUser), JSON.stringify(methods));
    return methods.find((item) => item.id === methodId);
  }
  if (path.match(/^\/api\/payment-app\/payment-methods\/\d+$/) && method === "DELETE") {
    const methodId = Number(path.split("/")[4]);
    let methods = storedMethods(activeUser).filter((item) => item.id !== methodId);
    if (methods.length && !methods.some((item) => item.is_default)) methods = methods.map((item, index) => ({ ...item, is_default: index === 0 }));
    localStorage.setItem(scopedKey("ig_demo_methods", activeUser), JSON.stringify(methods));
    return { status: "removed", id: methodId };
  }
  if (path === "/api/payment-app/pay" && method === "POST") {
    const method = storedMethods(activeUser).find((item) => item.id === body.payment_method_id);
    const payment = {
      id: Date.now(),
      country: "US",
      rail: method ? `${method.brand} ending ${method.last_four}` : body.rail || "Wallet Pay",
      external_ref: `wallet_pay_${Date.now()}`,
      invoice_id: "",
      customer_id: 999,
      recipient: body.recipient_name,
      amount: body.amount,
      currency: body.currency,
      status: "processing",
    };
    localStorage.setItem(scopedKey("ig_demo_payments", activeUser), JSON.stringify([payment, ...storedPayments(activeUser)]));
    return { status: "processing", payment_id: payment.id, external_ref: payment.external_ref, recipient: body.recipient_name, amount: body.amount, currency: body.currency, funding_source: payment.rail };
  }
  if (path === "/api/payment-app/request" && method === "POST") {
    localStorage.setItem(scopedKey("ig_demo_last_sync", activeUser), new Date().toISOString());
    return { status: "requested", request_id: `wallet_req_${Date.now()}`, payer: body.payer_name, amount: body.amount, currency: body.currency };
  }
  if (path === "/api/payment-app/reconciliation" && method === "POST") {
    return { id: Date.now(), status: "completed", checked_count: payments.length, matched_count: payments.length, exception_count: 0, exceptions: [], completed_at: new Date().toISOString() };
  }
  if (path === "/api/payment-app/reconciliation" && method === "GET") {
    return [];
  }
  if (path.startsWith("/api/predict/") || path === "/api/compliance/check") return { status: "completed", mode: "offline test", recommendation: "Review high-value, delayed, or volatile-currency items before settlement." };
  if (path === "/api/copilot") return seededDemo ? { answer: "Offline test mode: the riskiest invoices are pending high-value invoices in ZAR and EUR, especially INV-2026-1040 and INV-2026-1032.", state_used: { pending_invoices: 3, highest_risk_currency: "ZAR" } } : { answer: "This account does not have finance data yet. Add payments, invoices, or a payment provider to start analysis.", state_used: { pending_invoices: 0 } };
  throw new Error("Offline test data is not available for this action.");
}

export function getToken() {
  return localStorage.getItem("ig_access_token");
}

export async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch {
    if (OFFLINE_DEMO_ENABLED) return demoResponse(path, options);
    throw new Error("LedgerOps could not reach the server. No payment or account change was created.");
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    const message = Array.isArray(detail.detail)
      ? detail.detail.map((item) => item.msg || String(item)).join(". ")
      : detail.detail;
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json();
}

export async function apiBlob(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    const message = Array.isArray(detail.detail)
      ? detail.detail.map((item) => item.msg || String(item)).join(". ")
      : detail.detail;
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.blob();
}

export async function login(email, password, otp = null) {
  const data = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password, otp: otp || null }) });
  localStorage.setItem("ig_access_token", data.access_token);
  localStorage.setItem("ig_refresh_token", data.refresh_token);
  localStorage.setItem("ig_user", JSON.stringify(data.user));
  window.dispatchEvent(new CustomEvent("ig-account-changed", { detail: data.user }));
  return data.user;
}

export async function signup(payload) {
  const data = await api("/api/auth/signup", { method: "POST", body: JSON.stringify(payload) });
  localStorage.setItem("ig_access_token", data.access_token);
  localStorage.setItem("ig_refresh_token", data.refresh_token);
  localStorage.setItem("ig_user", JSON.stringify(data.user));
  window.dispatchEvent(new CustomEvent("ig-account-changed", { detail: data.user }));
  return data.user;
}
