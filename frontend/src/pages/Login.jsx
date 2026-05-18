import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { login, signup } from "../lib/api.js";

export default function Login({ mode = "login" }) {
  const isSignup = mode === "signup";
  const [name, setName] = useState("Avery Shah");
  const [email, setEmail] = useState("admin@infinityguard.ai");
  const [password, setPassword] = useState("AdminPass123");
  const [role, setRole] = useState("Finance Manager");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      if (isSignup) await signup({ name, email, password, role });
      else await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <main className="grid min-h-screen place-items-center bg-ink px-4 py-8">
      <form onSubmit={submit} className="w-full max-w-xl rounded-lg border border-white/10 bg-white p-7 shadow-soft">
        <div className="mb-6 flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-md bg-mint/10 text-mint"><ShieldCheck /></div>
          <div>
            <h1 className="text-2xl font-semibold">{isSignup ? "Create your Infinity workspace" : "Welcome back"}</h1>
            <p className="text-sm text-steel">Connect your payment app, detect risky receivables, and operate finance from one command center.</p>
          </div>
        </div>
        {isSignup && (
          <>
            <label className="text-sm font-medium">Full name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-mint" />
            <label className="mt-4 block text-sm font-medium">Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-mint">
              <option>Admin</option>
              <option>Finance Manager</option>
              <option>Viewer</option>
            </select>
          </>
        )}
        <label className={`${isSignup ? "mt-4 block" : ""} text-sm font-medium`}>Email</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-mint" />
        <label className="mt-4 block text-sm font-medium">Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-mint" />
        {error && <div className="mt-3 rounded-md bg-coral/10 p-3 text-sm text-coral">{error}</div>}
        <button className="mt-5 flex w-full items-center justify-center gap-2 rounded-md bg-mint px-4 py-2.5 font-medium text-white hover:bg-emerald-700">
          {isSignup ? "Create account" : "Sign in"} <ArrowRight size={17} />
        </button>
        <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_auto] sm:items-center">
          <div className="text-sm text-steel">{isSignup ? "Already have an account?" : "New to InfinityGuard?"}</div>
          <Link className="inline-flex items-center justify-center rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-ink hover:bg-panel" to={isSignup ? "/login" : "/signup"}>
            {isSignup ? "Go to sign in" : "Create account"}
          </Link>
        </div>
        {!isSignup && <div className="mt-4 text-xs text-steel">Seed users: finance@infinityguard.ai / FinancePass123, viewer@infinityguard.ai / ViewerPass123</div>}
      </form>
    </main>
  );
}
