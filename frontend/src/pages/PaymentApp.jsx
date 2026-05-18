import { useEffect, useState } from "react";
import { CheckCircle2, CreditCard, Link as LinkIcon, RefreshCw, ShieldCheck } from "lucide-react";
import { Card, Skeleton } from "../components/Card.jsx";
import { api } from "../lib/api.js";

const money = (amount, currency = "USD") =>
  new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount || 0);

export default function PaymentApp() {
  const [status, setStatus] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [invoiceId, setInvoiceId] = useState("");
  const [message, setMessage] = useState("");
  const [link, setLink] = useState(null);
  const [loading, setLoading] = useState("");

  async function load() {
    const [statusData, invoiceData] = await Promise.all([api("/api/payment-app/status"), api("/api/invoices")]);
    setStatus(statusData);
    setInvoices(invoiceData.filter((invoice) => invoice.status === "pending"));
    if (!invoiceId && invoiceData.length) {
      const pending = invoiceData.find((invoice) => invoice.status === "pending") || invoiceData[0];
      setInvoiceId(String(pending.id));
    }
  }

  useEffect(() => { load().catch((err) => setMessage(err.message)); }, []);

  async function connect() {
    setLoading("connect");
    setMessage("");
    try {
      const result = await api("/api/payment-app/connect", {
        method: "POST",
        body: JSON.stringify({ provider: "Stripe", account_name: "InfinityGuard Treasury", mode: "test" }),
      });
      setMessage(`${result.provider} ${result.mode} account connected.`);
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
      setMessage(`Imported ${result.imported_payments} payment from the payment app.`);
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
    try {
      const result = await api("/api/payment-app/payment-link", {
        method: "POST",
        body: JSON.stringify({ invoice_id: Number(invoiceId) }),
      });
      setLink(result);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setLoading("");
    }
  }

  if (!status) return <Skeleton />;

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[1fr_1.2fr]">
        <Card>
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-md bg-mint/10 text-mint"><CreditCard /></div>
              <div>
                <h2 className="text-xl font-semibold">Payment App Connection</h2>
                <p className="text-sm text-steel">Stripe-compatible ingestion for payments, webhooks, and checkout links.</p>
              </div>
            </div>
            <span className="rounded-full bg-mint/10 px-3 py-1 text-xs font-medium text-mint">{status.connected ? "Connected" : "Not connected"}</span>
          </div>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <button onClick={connect} disabled={loading === "connect"} className="flex items-center justify-center gap-2 rounded-md bg-ink px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60">
              <ShieldCheck size={17} /> {loading === "connect" ? "Connecting..." : "Connect provider"}
            </button>
            <button onClick={syncDemo} disabled={loading === "sync"} className="flex items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-ink hover:bg-panel disabled:opacity-60">
              <RefreshCw size={17} /> {loading === "sync" ? "Syncing..." : "Sync latest payments"}
            </button>
          </div>
          {message && <div className="mt-4 rounded-md bg-panel p-3 text-sm text-steel">{message}</div>}
        </Card>

        <Card title="Integration Health">
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <Metric label="Provider" value={status.provider} />
            <Metric label="Health" value={status.sync_health} />
            <Metric label="Mapped payments" value={status.mapped_payments} />
            <Metric label="Webhook events" value={status.webhook_events} />
          </div>
          <div className="mt-5 rounded-md border border-slate-200 p-4">
            <div className="flex items-center gap-2 text-sm font-medium"><CheckCircle2 size={17} className="text-mint" /> Production workflow</div>
            <p className="mt-2 text-sm leading-6 text-steel">Payment app events are normalized into InfinityGuard payments, invoices, transactions, risk signals, alerts, and copilot context.</p>
          </div>
        </Card>
      </div>

      <Card title="Create Payment Link">
        <form onSubmit={createLink} className="mt-4 grid gap-3 lg:grid-cols-[1fr_auto]">
          <select value={invoiceId} onChange={(e) => setInvoiceId(e.target.value)} className="rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-mint">
            {invoices.map((invoice) => (
              <option key={invoice.id} value={invoice.id}>
                {invoice.invoice_number} · {money(invoice.amount, invoice.currency)} · {invoice.currency}
              </option>
            ))}
          </select>
          <button disabled={!invoiceId || loading === "link"} className="flex items-center justify-center gap-2 rounded-md bg-mint px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-60">
            <LinkIcon size={17} /> {loading === "link" ? "Creating..." : "Create checkout link"}
          </button>
        </form>
        {link && (
          <div className="mt-4 rounded-md border border-slate-200 bg-panel p-4">
            <div className="text-sm font-medium">{link.invoice_number} checkout link</div>
            <div className="mt-2 break-all text-sm text-steel">{link.checkout_url}</div>
          </div>
        )}
      </Card>
    </div>
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
