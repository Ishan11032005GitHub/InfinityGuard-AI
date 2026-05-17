import { useEffect, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, Skeleton } from "../components/Card.jsx";
import { api } from "../lib/api.js";

const money = (n) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n || 0);

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api("/api/dashboard").then(setData).catch((err) => setError(err.message)); }, []);
  if (error) return <Card title="Dashboard unavailable" helper={error}><div className="mt-4 text-sm text-steel">Sign out and sign back in if your session token is stale.</div></Card>;
  if (!data) return <div className="grid gap-4 md:grid-cols-3"><Skeleton /><Skeleton /><Skeleton /></div>;
  const exposure = Object.entries(data.currency_exposure).map(([currency, amount]) => ({ currency, amount }));
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <Card title="Total transaction volume" value={money(data.total_volume)} helper="Settled inbound payments" />
        <Card title="Pending invoices" value={data.pending_invoices} helper="Open receivables" />
        <Card title="Cash runway" value={`${data.cash_runway} days`} helper="Forecast adjusted" />
        <Card title="Currency exposure" value={exposure.length} helper="Active currencies" />
        <Card title="Risk score" value={data.risk_score || 24} helper="Anomaly-weighted" />
      </div>
      <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
        <Card title="Monthly transaction chart">
          <div className="mt-4 h-80"><ResponsiveContainer><AreaChart data={data.monthly_transactions}><defs><linearGradient id="volume" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#00a676" stopOpacity="0.5"/><stop offset="100%" stopColor="#00a676" stopOpacity="0.05"/></linearGradient></defs><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0"/><XAxis dataKey="month"/><YAxis/><Tooltip/><Area dataKey="volume" stroke="#00a676" fill="url(#volume)" /></AreaChart></ResponsiveContainer></div>
        </Card>
        <Card title="Recent alerts">
          <div className="mt-4 space-y-3">{data.alerts.map((alert, i) => <div key={i} className="rounded-md border border-slate-200 p-3"><div className="text-xs uppercase text-coral">{alert.severity} / {alert.category}</div><div className="mt-1 text-sm">{alert.message}</div></div>)}</div>
        </Card>
      </div>
      <div className="grid gap-5 xl:grid-cols-3">
        <Card title="Cash flow chart"><div className="mt-4 h-64"><ResponsiveContainer><BarChart data={data.cash_flow}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0"/><XAxis dataKey="month"/><YAxis/><Tooltip/><Bar dataKey="incoming" fill="#00a676"/><Bar dataKey="expenses" fill="#f25f5c"/></BarChart></ResponsiveContainer></div></Card>
        <Card title="FX trend chart"><div className="mt-4 h-64"><ResponsiveContainer><LineChart data={data.fx_trends.slice(-35)}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0"/><XAxis dataKey="currency"/><YAxis/><Tooltip/><Line dataKey="rate" stroke="#2563eb" dot={false}/><Line dataKey="volatility" stroke="#f25f5c" dot={false}/></LineChart></ResponsiveContainer></div></Card>
        <Card title="Country-wise payment heatmap"><div className="mt-4 space-y-3">{data.country_heatmap.map((item) => <div key={item.country}><div className="mb-1 flex justify-between text-sm"><span>{item.country}</span><span>{money(item.volume)}</span></div><div className="h-2 rounded bg-slate-100"><div className="h-2 rounded bg-mint" style={{ width: `${Math.min(100, item.volume / 2000)}%` }} /></div></div>)}</div></Card>
      </div>
      <Card title="Anomaly chart"><div className="mt-4 h-72"><ResponsiveContainer><BarChart data={data.anomalies}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0"/><XAxis dataKey="name" hide/><YAxis/><Tooltip/><Bar dataKey="score" fill="#f25f5c"/></BarChart></ResponsiveContainer></div></Card>
    </div>
  );
}
