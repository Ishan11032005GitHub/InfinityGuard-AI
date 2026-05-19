import { useEffect, useMemo, useState } from "react";
import { ArrowDownLeft, ArrowUpRight, CheckCircle2, Link as LinkIcon, QrCode, RefreshCw, ScanLine, ShieldCheck } from "lucide-react";
import { Card, Skeleton } from "../components/Card.jsx";
import { api } from "../lib/api.js";

const contacts = [
  { name: "Northstar Robotics", handle: "northstar@pay", currency: "USD", color: "bg-mint" },
  { name: "Kairo Retail Group", handle: "kairo@pay", currency: "AED", color: "bg-blue-600" },
  { name: "Sakura Supply KK", handle: "sakura@pay", currency: "JPY", color: "bg-coral" },
  { name: "Atlas Minerals", handle: "atlas@pay", currency: "ZAR", color: "bg-amber-500" },
];

const money = (amount, currency = "USD") =>
  new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount || 0);

export default function PaymentApp() {
  const [status, setStatus] = useState(null);
  const [payments, setPayments] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [mode, setMode] = useState("pay");
  const [selected, setSelected] = useState(contacts[0]);
  const [amount, setAmount] = useState("2500");
  const [note, setNote] = useState("Invoice settlement");
  const [invoiceId, setInvoiceId] = useState("");
  const [message, setMessage] = useState("");
  const [linkMessage, setLinkMessage] = useState("");
  const [verifyStatus, setVerifyStatus] = useState("");
  const [link, setLink] = useState(null);
  const [loading, setLoading] = useState("");

  async function load() {
    const [statusData, invoiceData, paymentData] = await Promise.all([api("/api/payment-app/status"), api("/api/invoices"), api("/api/payments")]);
    setStatus(statusData);
    setInvoices(invoiceData.filter((invoice) => invoice.status === "pending"));
    setPayments(paymentData.slice(0, 6));
    if (!invoiceId && invoiceData.length) {
      const pending = invoiceData.find((invoice) => invoice.status === "pending") || invoiceData[0];
      setInvoiceId(String(pending.id));
    }
  }

  useEffect(() => { load().catch((err) => setMessage(err.message)); }, []);

  const selectedInvoice = useMemo(() => invoices.find((invoice) => String(invoice.id) === invoiceId), [invoiceId, invoices]);

  async function connect() {
    setLoading("connect");
    setMessage("");
    try {
      const result = await api("/api/payment-app/connect", {
        method: "POST",
        body: JSON.stringify({ provider: "Wallet Pay", account_name: "InfinityGuard Treasury", mode: "test" }),
      });
      setMessage(`${result.provider} account connected.`);
      await load();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setLoading("");
    }
  }

  async function syncDemo() {
    setLoading("sync");
    setMessage("");
    try {
      const result = await api("/api/payment-app/sync-demo", { method: "POST" });
      setMessage(`Synced ${result.imported_payments} latest wallet payment.`);
      await load();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setLoading("");
    }
  }

  async function submitWallet(e) {
    e.preventDefault();
    setLoading(mode);
    setMessage("");
    setLink(null);
    const endpoint = mode === "pay" ? "/api/payment-app/pay" : "/api/payment-app/request";
    const payload = mode === "pay"
      ? { recipient_name: selected.name, recipient_handle: selected.handle, amount: Number(amount), currency: selected.currency, note, rail: "Wallet Pay" }
      : { payer_name: selected.name, payer_handle: selected.handle, amount: Number(amount), currency: selected.currency, note };
    try {
      const result = await api(endpoint, { method: "POST", body: JSON.stringify(payload) });
      setMessage(mode === "pay" ? `Payment to ${result.recipient} is ${result.status}.` : `Request sent to ${result.payer}.`);
      await load();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setLoading("");
    }
  }

  async function createLink(e) {
    e.preventDefault();
    setLoading("link");
    setMessage("");
    setLinkMessage("");
    setVerifyStatus("");
    try {
      const result = await api("/api/payment-app/payment-link", {
        method: "POST",
        body: JSON.stringify({ invoice_id: Number(invoiceId) }),
      });
      setLink(result);
      setLinkMessage(`Checkout link ready for ${result.invoice_number}. Open checkout, complete the test payment, then verify it here.`);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setLoading("");
    }
  }

  async function verifyCheckout() {
    if (!link?.checkout_id) return;
    setLoading("verify");
    setMessage("");
    setLinkMessage("Checking Stripe payment status...");
    setVerifyStatus("checking");
    try {
      const result = await api(`/api/payment-app/verify-checkout/${link.checkout_id}`, { method: "POST" });
      setLinkMessage(result.status === "verified" ? `Verified ${result.invoice_number || "checkout"} and recorded ${money(result.amount, result.currency)}.` : result.message);
      setVerifyStatus(result.status === "verified" ? "verified" : "unpaid");
      await load();
    } catch (err) {
      setLinkMessage(err.message);
      setVerifyStatus("error");
    } finally {
      setLoading("");
    }
  }

  if (!status) return <Skeleton />;

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[390px_1fr]">
        <section className="rounded-lg border border-slate-200 bg-white shadow-soft">
          <div className="border-b border-slate-200 p-5">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-mint">Infinity Pay</div>
                <h2 className="mt-1 text-2xl font-semibold">Wallet</h2>
              </div>
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${status.connected ? "bg-mint/10 text-mint" : "bg-amber-100 text-amber-700"}`}>{status.connected ? "Stripe test" : "Demo mode"}</span>
            </div>
            <div className="mt-5 rounded-lg bg-ink p-5 text-white">
              <div className="text-sm text-white/65">Available balance</div>
              <div className="mt-2 text-3xl font-semibold">$128,460</div>
              <div className="mt-4 flex items-center justify-between text-xs text-white/65">
                <span>Wallet ID: infinity@pay</span>
                <ShieldCheck size={16} />
              </div>
            </div>
            <div className="mt-4 grid grid-cols-4 gap-2">
              <Action icon={ScanLine} label="Scan" />
              <Action icon={ArrowUpRight} label="Pay" active={mode === "pay"} onClick={() => setMode("pay")} />
              <Action icon={ArrowDownLeft} label="Request" active={mode === "request"} onClick={() => setMode("request")} />
              <Action icon={QrCode} label="QR" />
            </div>
          </div>

          <form onSubmit={submitWallet} className="p-5">
            <div className="mb-4 flex rounded-md bg-panel p-1">
              <button type="button" onClick={() => setMode("pay")} className={`flex-1 rounded px-3 py-2 text-sm font-medium ${mode === "pay" ? "bg-white shadow-sm" : "text-steel"}`}>Pay</button>
              <button type="button" onClick={() => setMode("request")} className={`flex-1 rounded px-3 py-2 text-sm font-medium ${mode === "request" ? "bg-white shadow-sm" : "text-steel"}`}>Request</button>
            </div>

            <label className="text-sm font-medium">{mode === "pay" ? "Pay to" : "Request from"}</label>
            <div className="mt-2 grid grid-cols-4 gap-2">
              {contacts.map((contact) => (
                <button key={contact.handle} type="button" onClick={() => setSelected(contact)} className={`rounded-md border p-2 text-center ${selected.handle === contact.handle ? "border-mint bg-mint/5" : "border-slate-200"}`}>
                  <div className={`mx-auto grid h-9 w-9 place-items-center rounded-full text-sm font-semibold text-white ${contact.color}`}>{contact.name.slice(0, 1)}</div>
                  <div className="mt-2 truncate text-xs">{contact.name.split(" ")[0]}</div>
                </button>
              ))}
            </div>

            <div className="mt-4 rounded-md border border-slate-200 p-3">
              <div className="text-sm font-medium">{selected.name}</div>
              <div className="text-xs text-steel">{selected.handle}</div>
            </div>

            <label className="mt-4 block text-sm font-medium">Amount</label>
            <div className="mt-1 flex rounded-md border border-slate-300 focus-within:border-mint">
              <span className="border-r border-slate-200 px-3 py-2 text-sm text-steel">{selected.currency}</span>
              <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" className="min-w-0 flex-1 rounded-r-md px-3 py-2 outline-none" />
            </div>

            <label className="mt-4 block text-sm font-medium">Note</label>
            <input value={note} onChange={(e) => setNote(e.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-mint" />

            <button disabled={loading === mode || !Number(amount)} className="mt-5 flex w-full items-center justify-center gap-2 rounded-md bg-mint px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-60">
              {mode === "pay" ? <ArrowUpRight size={17} /> : <ArrowDownLeft size={17} />}
              {loading === mode ? "Processing..." : mode === "pay" ? "Pay now" : "Request money"}
            </button>
          </form>
        </section>

        <div className="space-y-5">
          <Card title="Payment Network">
            <div className="mt-4 grid gap-3 md:grid-cols-4">
              <Metric label="Provider" value={status.provider} />
              <Metric label="Mode" value={status.mode} />
              <Metric label="Payments" value={status.mapped_payments} />
              <Metric label="Events" value={status.webhook_events} />
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <button onClick={connect} disabled={loading === "connect"} className="flex items-center justify-center gap-2 rounded-md bg-ink px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60">
                <ShieldCheck size={17} /> {loading === "connect" ? "Connecting..." : "Connect wallet provider"}
              </button>
              <button onClick={syncDemo} disabled={loading === "sync"} className="flex items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-ink hover:bg-panel disabled:opacity-60">
                <RefreshCw size={17} /> {loading === "sync" ? "Syncing..." : "Sync activity"}
              </button>
            </div>
            {message && <div className="mt-4 rounded-md bg-panel p-3 text-sm text-steel">{message}</div>}
          </Card>

          <Card title="Payments List">
            <div className="mt-4 space-y-3">
              {payments.map((payment) => (
                <div key={payment.id} className="flex items-center justify-between rounded-md border border-slate-200 p-3">
                  <div className="flex items-center gap-3">
                    <div className="grid h-9 w-9 place-items-center rounded-full bg-panel text-sm font-semibold text-steel">{(payment.recipient || "P").slice(0, 1)}</div>
                    <div>
                      <div className="text-sm font-medium">{payment.recipient || "Unknown recipient"}</div>
                      <div className="text-xs text-steel">{payment.external_ref} | {payment.rail} | {payment.status || "settled"}</div>
                    </div>
                  </div>
                  <div className="text-sm font-semibold">{money(payment.amount, payment.currency || "USD")}</div>
                </div>
              ))}
            </div>
          </Card>

          <Card title="Recipients">
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {contacts.map((contact) => (
                <button key={contact.handle} type="button" onClick={() => setSelected(contact)} className="flex items-center gap-3 rounded-md border border-slate-200 p-3 text-left hover:bg-panel">
                  <div className={`grid h-10 w-10 place-items-center rounded-full text-sm font-semibold text-white ${contact.color}`}>{contact.name.slice(0, 1)}</div>
                  <div>
                    <div className="text-sm font-medium">{contact.name}</div>
                    <div className="text-xs text-steel">{contact.handle} | {contact.currency}</div>
                  </div>
                </button>
              ))}
            </div>
          </Card>
        </div>
      </div>

      <Card title="Collect From Invoice">
        <form onSubmit={createLink} className="mt-4 grid gap-3 lg:grid-cols-[1fr_auto]">
          <select value={invoiceId} onChange={(e) => setInvoiceId(e.target.value)} className="rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-mint">
            {invoices.map((invoice) => (
              <option key={invoice.id} value={invoice.id}>
                {invoice.invoice_number} | {money(invoice.amount, invoice.currency)} | {invoice.currency}
              </option>
            ))}
          </select>
          <button disabled={!invoiceId || loading === "link"} className="flex items-center justify-center gap-2 rounded-md bg-ink px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60">
            <LinkIcon size={17} /> {loading === "link" ? "Creating..." : "Create payment link"}
          </button>
        </form>
        {selectedInvoice && <div className="mt-3 text-sm text-steel">Ready to collect {money(selectedInvoice.amount, selectedInvoice.currency)} for {selectedInvoice.invoice_number}.</div>}
        {link && (
          <div className="mt-4 grid gap-4 rounded-md border border-slate-200 bg-panel p-4 md:grid-cols-[120px_1fr]">
            <div className="grid aspect-square place-items-center rounded-md bg-white">
              <QrCode size={64} className="text-ink" />
            </div>
            <div>
              <div className="flex items-center gap-2 text-sm font-medium"><CheckCircle2 size={17} className="text-mint" /> Payment link ready</div>
              <div className="mt-1 text-xs uppercase tracking-wide text-steel">{link.provider} | {link.mode || "demo"}</div>
              <div className="mt-2 break-all text-sm text-steel">{link.checkout_url}</div>
              <div className="mt-4 flex flex-wrap gap-2">
                <a href={link.checkout_url} target="_blank" rel="noreferrer" className="inline-flex items-center justify-center rounded-md bg-mint px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700">
                  Open checkout
                </a>
                <button type="button" onClick={verifyCheckout} disabled={loading === "verify" || !link.checkout_id} className={`inline-flex items-center justify-center rounded-md border px-4 py-2 text-sm font-medium disabled:opacity-60 ${verifyStatus === "verified" ? "border-mint bg-mint/10 text-mint" : verifyStatus === "unpaid" || verifyStatus === "error" ? "border-coral bg-coral/10 text-coral" : "border-slate-300 bg-white text-ink hover:bg-panel"}`}>
                  {verifyStatus === "checking" ? "Checking..." : verifyStatus === "verified" ? "Verified" : verifyStatus === "unpaid" ? "Not paid yet" : verifyStatus === "error" ? "Verification failed" : "Verify Stripe payment"}
                </button>
              </div>
              {linkMessage && <div className="mt-3 rounded-md bg-white p-3 text-sm text-steel">{linkMessage}</div>}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

function Action({ icon: Icon, label, active, onClick }) {
  return (
    <button type="button" onClick={onClick} className={`grid place-items-center gap-1 rounded-md border px-2 py-3 text-xs font-medium ${active ? "border-mint bg-mint/5 text-mint" : "border-slate-200 text-steel hover:bg-panel"}`}>
      <Icon size={18} />
      {label}
    </button>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-md border border-slate-200 p-3">
      <div className="text-xs uppercase tracking-wide text-steel">{label}</div>
      <div className="mt-1 text-sm font-semibold capitalize text-ink">{value || "Not available"}</div>
    </div>
  );
}
