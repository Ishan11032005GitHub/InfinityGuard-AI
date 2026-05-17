import { useEffect, useState } from "react";
import { Card, Skeleton } from "../components/Card.jsx";
import { api } from "../lib/api.js";

export default function DataPage({ type }) {
  const [rows, setRows] = useState(null);
  useEffect(() => {
    if (type === "settings") setRows([{ setting: "API mode", value: "Mock integrations" }, { setting: "Webhook retries", value: "3 attempts" }, { setting: "Deployment", value: "Docker, Render, Vercel ready" }]);
    else api(`/api/${type}`).then(setRows);
  }, [type]);
  if (!rows) return <Skeleton />;
  const columns = Object.keys(rows[0] || {}).filter((k) => !["hashed_password", "metadata_json"].includes(k)).slice(0, 7);
  return (
    <Card title={type.replace("-", " ").toUpperCase()}>
      <div className="mt-4 overflow-auto scrollbar-thin">
        <table className="min-w-full text-left text-sm">
          <thead><tr>{columns.map((c) => <th key={c} className="border-b border-slate-200 px-3 py-2 font-medium text-steel">{c}</th>)}</tr></thead>
          <tbody>{rows.map((row, i) => <tr key={row.id || i} className="hover:bg-panel">{columns.map((c) => <td key={c} className="border-b border-slate-100 px-3 py-2">{String(row[c] ?? "")}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </Card>
  );
}
