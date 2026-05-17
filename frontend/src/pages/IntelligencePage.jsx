import { useState } from "react";
import { Activity, Brain, Landmark, ShieldAlert } from "lucide-react";
import { Card } from "../components/Card.jsx";
import { api } from "../lib/api.js";

const modes = {
  fx: { title: "FX Intelligence Engine", icon: Landmark, endpoint: "/api/predict/fx", body: { payload: { currency: "EUR" } } },
  fraud: { title: "Fraud / Anomaly Detection", icon: ShieldAlert, endpoint: "/api/predict/anomaly", body: { payload: { amount: 82000, country: "ZA", currency: "ZAR", hour: 2, first_time_payer: true } } },
  cash: { title: "Cash Runway Forecasting", icon: Activity, endpoint: "/api/predict/runway", body: { payload: {} } },
  compliance: { title: "Compliance Engine", icon: Brain, endpoint: "/api/compliance/check", body: { amount: 76000, country: "AE", payer_name: "Kairo Retail Group", invoice_amount: 73000, documents: ["invoice"] } },
};

export default function IntelligencePage({ mode }) {
  const config = modes[mode];
  const Icon = config.icon;
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  async function run() {
    setLoading(true);
    try { setResult(await api(config.endpoint, { method: "POST", body: JSON.stringify(config.body) })); }
    finally { setLoading(false); }
  }
  return (
    <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
      <Card>
        <div className="flex items-center gap-3"><div className="grid h-11 w-11 place-items-center rounded-md bg-mint/10 text-mint"><Icon /></div><h2 className="text-xl font-semibold">{config.title}</h2></div>
        <p className="mt-4 text-sm leading-6 text-steel">Runs against current seeded finance state and mock integration payloads. Outputs are recommendations for operational decisions, not deterministic market or fraud claims.</p>
        <button onClick={run} disabled={loading} className="mt-5 rounded-md bg-ink px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60">{loading ? "Running..." : "Run engine"}</button>
      </Card>
      <Card title="Model output">
        <pre className="mt-4 max-h-[560px] overflow-auto rounded-md bg-ink p-4 text-sm text-white scrollbar-thin">{JSON.stringify(result || { status: "ready" }, null, 2)}</pre>
      </Card>
    </div>
  );
}
