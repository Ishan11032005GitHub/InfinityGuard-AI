import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { login } from "../lib/api.js";

export default function Login() {
  const [email, setEmail] = useState("admin@infinityguard.ai");
  const [password, setPassword] = useState("AdminPass123");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <main className="grid min-h-screen place-items-center bg-ink px-4">
      <form onSubmit={submit} className="w-full max-w-md rounded-lg bg-white p-7 shadow-soft">
        <div className="mb-6 flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-md bg-mint/10 text-mint"><ShieldCheck /></div>
          <div>
            <h1 className="text-2xl font-semibold">InfinityGuard AI</h1>
            <p className="text-sm text-steel">AI finance operations layer for cross-border SMB payments.</p>
          </div>
        </div>
        <label className="text-sm font-medium">Email</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-mint" />
        <label className="mt-4 block text-sm font-medium">Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-mint" />
        {error && <div className="mt-3 rounded-md bg-coral/10 p-3 text-sm text-coral">{error}</div>}
        <button className="mt-5 w-full rounded-md bg-mint px-4 py-2.5 font-medium text-white hover:bg-emerald-700">Sign in</button>
        <div className="mt-4 text-xs text-steel">Seed users: finance@infinityguard.ai / FinancePass123, viewer@infinityguard.ai / ViewerPass123</div>
      </form>
    </main>
  );
}
