import { useState } from "react";
import { Send } from "lucide-react";
import { Card } from "../components/Card.jsx";
import { api } from "../lib/api.js";

export default function Copilot() {
  const [question, setQuestion] = useState("Which invoices are dangerous?");
  const [messages, setMessages] = useState([]);
  async function ask(e) {
    e.preventDefault();
    const q = question;
    setQuestion("");
    const result = await api("/api/copilot", { method: "POST", body: JSON.stringify({ question: q }) });
    setMessages((prev) => [...prev, { role: "user", text: q }, { role: "assistant", text: result.answer, state: result.state_used }]);
  }
  return (
    <Card title="AI Finance Copilot">
      <div className="mt-4 grid gap-3">
        {messages.map((m, i) => <div key={i} className={`rounded-md p-4 ${m.role === "user" ? "bg-panel" : "bg-ink text-white"}`}><div>{m.text}</div>{m.state && <pre className="mt-3 overflow-auto text-xs text-white/70">{JSON.stringify(m.state, null, 2)}</pre>}</div>)}
      </div>
      <form onSubmit={ask} className="mt-5 flex gap-2">
        <input value={question} onChange={(e) => setQuestion(e.target.value)} className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-mint" />
        <button title="Ask copilot" className="grid h-10 w-10 place-items-center rounded-md bg-mint text-white"><Send size={18} /></button>
      </form>
    </Card>
  );
}
