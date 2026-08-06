import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";

const commands = [
  ["Dashboard", "/", "Operating snapshot, charts, alerts"],
  ["Payments", "/payments", "Payment records and search"],
  ["Payment App", "/payment-app", "Gateway, cards, chat, transfers"],
  ["QuickLinks", "/quicklinks", "International card collection links"],
  ["Invoices", "/invoices", "Receivables and invoice search"],
  ["Clients", "/clients", "Client records"],
  ["Action Center", "/action-center", "Overdue, risk, compliance, failed links"],
  ["Payment Timeline", "/payment-timeline", "Created, authorized, settled, receipt, reconciled"],
  ["Receipt Center", "/receipt-center", "Receipts and remittance documents"],
  ["Client Profiles", "/client-profiles", "Payments, invoices, risk history by client"],
  ["Approval Workflows", "/approvals", "Manager and admin approval queue"],
  ["Audit Log", "/audit-log", "Tamper-resistant activity trail"],
  ["Notifications", "/notifications", "Payment and risk attention feed"],
  ["Reconciliation", "/reconciliation", "Processor and ledger matching"],
  ["Role Permissions", "/permissions", "Role capabilities and visibility"],
  ["Country Codes", "/country-codes", "Country code decoder"],
  ["FX Intelligence", "/fx", "Currency exposure and conversion guidance"],
  ["Fraud Detection", "/fraud", "Anomaly and payment review"],
  ["Cash Forecast", "/cash", "Runway and cash projection"],
  ["Compliance", "/compliance", "KYC and settlement review"],
  ["AI Finance Copilot", "/copilot", "Account-grounded answers about cash, invoices, risk, and FX"],
  ["Demo Story Mode", "/demo-story", "Guided product presentation flow"],
  ["Settings", "/settings", "Profile, security, team access"],
];

export default function CommandPalette() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    function onKeyDown(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
      }
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return commands;
    return commands.filter(([title, path, helper]) => `${title} ${path} ${helper}`.toLowerCase().includes(needle));
  }, [query]);

  function go(path) {
    setOpen(false);
    setQuery("");
    navigate(path);
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="hidden rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-steel hover:text-ink md:inline-flex">
        Ctrl K
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-[70] bg-ink/40 px-4 pt-[12vh] backdrop-blur-sm" onMouseDown={() => setOpen(false)}>
      <section className="mx-auto max-w-2xl overflow-hidden rounded-lg border border-slate-200 bg-white shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
        <label className="flex items-center gap-3 border-b border-slate-200 px-4 py-3">
          <Search size={18} className="text-steel" />
          <input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search pages, payments, receipts, workflows..." className="min-w-0 flex-1 outline-none" />
        </label>
        <div className="max-h-[420px] overflow-auto p-2">
          {matches.map(([title, path, helper]) => (
            <button key={path} type="button" onClick={() => go(path)} className="flex w-full items-center justify-between gap-4 rounded-md px-3 py-3 text-left hover:bg-panel">
              <span>
                <span className="block font-medium">{title}</span>
                <span className="mt-0.5 block text-xs text-steel">{helper}</span>
              </span>
              <span className="text-xs text-steel">{path}</span>
            </button>
          ))}
          {!matches.length && <div className="px-3 py-8 text-center text-sm text-steel">No command found.</div>}
        </div>
      </section>
    </div>
  );
}
