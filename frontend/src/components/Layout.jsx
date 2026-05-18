import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Bot, CircleDollarSign, Gauge, Landmark, LineChart, LogOut, PlugZap, Receipt, SearchCheck, Settings, ShieldAlert, Users, WalletCards } from "lucide-react";

const nav = [
  ["Dashboard", "/", Gauge],
  ["Payments", "/payments", CircleDollarSign],
  ["Payment App", "/payment-app", PlugZap],
  ["Invoices", "/invoices", Receipt],
  ["Customers", "/customers", Users],
  ["FX Intelligence", "/fx", LineChart],
  ["Fraud Detection", "/fraud", ShieldAlert],
  ["Cash Forecast", "/cash", WalletCards],
  ["Compliance", "/compliance", SearchCheck],
  ["AI Copilot", "/copilot", Bot],
  ["Settings", "/settings", Settings],
];

export default function Layout() {
  const navigate = useNavigate();
  let user = {};
  try {
    user = JSON.parse(localStorage.getItem("ig_user") || "{}");
  } catch {
    localStorage.removeItem("ig_user");
  }
  function logout() {
    localStorage.clear();
    navigate("/login");
  }
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[280px_1fr]">
      <aside className="bg-ink text-white p-5 lg:min-h-screen">
        <div className="mb-8">
          <div className="text-2xl font-semibold">InfinityGuard AI</div>
          <div className="text-sm text-white/60 mt-1">Payments risk operating system</div>
        </div>
        <nav className="grid gap-1">
          {nav.map(([label, path, Icon]) => (
            <NavLink key={path} to={path} className={({ isActive }) => `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition ${isActive ? "bg-white text-ink shadow-soft" : "text-white/75 hover:bg-white/10 hover:text-white"}`}>
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="min-w-0">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/95 px-5 py-4 backdrop-blur">
          <div>
            <div className="text-sm text-steel">Connected payments, cash, FX, fraud, and compliance intelligence</div>
            <h1 className="text-xl font-semibold">Finance command center</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <div className="text-sm font-medium">{user.name || "Guest"}</div>
              <div className="text-xs text-steel">{user.role || "Viewer"}</div>
            </div>
            <button title="Log out" onClick={logout} className="grid h-10 w-10 place-items-center rounded-md border border-slate-200 bg-white text-steel hover:text-coral">
              <LogOut size={18} />
            </button>
          </div>
        </header>
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="p-5 lg:p-8">
          <Outlet />
        </motion.div>
      </main>
    </div>
  );
}
