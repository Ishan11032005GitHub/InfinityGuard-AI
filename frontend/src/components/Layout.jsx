import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Bell, Bot, CircleDollarSign, FileText, Flag, Gauge, History, LineChart, Link2, LockKeyhole, LogOut, PlugZap, Receipt, RefreshCw, SearchCheck, Settings, ShieldAlert, Users, WalletCards } from "lucide-react";
import { accountCommandTitle, accountSubtitle, readStoredUser } from "../lib/account.js";
import CommandPalette from "./CommandPalette.jsx";
import FloatingCopilot from "./FloatingCopilot.jsx";

const nav = [
  ["Dashboard", "/", Gauge, () => import("../pages/Dashboard.jsx").then((module) => module.prefetchDashboard())],
  ["Payments", "/payments", CircleDollarSign, () => import("../pages/DataPage.jsx").then((module) => module.prefetchDataPage("payments"))],
  ["Payment App", "/payment-app", PlugZap],
  ["QuickLinks", "/quicklinks", Link2],
  ["Action Center", "/action-center", Bell],
  ["Timeline", "/payment-timeline", History],
  ["Receipts", "/receipt-center", FileText],
  ["Invoices", "/invoices", Receipt, () => import("../pages/DataPage.jsx").then((module) => module.prefetchDataPage("invoices"))],
  ["Clients", "/clients", Users, () => import("../pages/DataPage.jsx").then((module) => module.prefetchDataPage("customers"))],
  ["Country Codes", "/country-codes", Flag],
  ["FX Intelligence", "/fx", LineChart],
  ["Fraud Detection", "/fraud", ShieldAlert],
  ["Cash Forecast", "/cash", WalletCards],
  ["Compliance", "/compliance", SearchCheck],
  ["AI Copilot", "/copilot", Bot, () => import("../pages/Copilot.jsx")],
  ["Reconcile", "/reconciliation", RefreshCw],
  ["Audit Log", "/audit-log", LockKeyhole],
  ["Settings", "/settings", Settings],
];

const shellMotion = {
  sidebar: {
    initial: { opacity: 0, x: -28 },
    animate: { opacity: 1, x: 0 },
    transition: { duration: 0.34, ease: [0.22, 1, 0.36, 1] },
  },
  header: {
    initial: { opacity: 0, y: -18 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.32, delay: 0.05, ease: [0.22, 1, 0.36, 1] },
  },
  body: {
    initial: { opacity: 0, x: 24 },
    animate: { opacity: 1, x: 0 },
    transition: { duration: 0.32, delay: 0.08, ease: [0.22, 1, 0.36, 1] },
  },
};

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState(readStoredUser);

  useEffect(() => {
    function handleUserUpdated(event) {
      setUser(event.detail || readStoredUser());
    }
    window.addEventListener("ig-user-updated", handleUserUpdated);
    return () => window.removeEventListener("ig-user-updated", handleUserUpdated);
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [location.pathname]);

  function logout() {
    const refreshToken = localStorage.getItem("ig_refresh_token");
    if (refreshToken) {
      fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }).catch(() => {});
    }
    localStorage.clear();
    navigate("/login");
  }
  return (
    <div className="app-frame min-h-screen lg:grid lg:grid-cols-[280px_1fr]">
      <motion.aside {...shellMotion.sidebar} className="sidebar-surface text-white p-5 lg:min-h-screen">
        <div className="mb-8">
          <div className="text-2xl font-semibold text-white">LedgerOps</div>
          <div className="mt-1 text-sm text-cyan-50/70">Payments risk operating system</div>
        </div>
        <nav className="grid gap-1">
          {nav.map(([label, path, Icon, prefetch]) => (
            <NavLink key={path} to={path} end={path === "/"} onPointerEnter={() => prefetch?.().catch(() => {})} onFocus={() => prefetch?.().catch(() => {})} className={({ isActive }) => `relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-all duration-150 ${isActive ? "bg-white text-ink shadow-soft" : "text-cyan-50/75 hover:bg-white/[0.09] hover:text-white hover:translate-x-0.5"}`}>
              {({ isActive }) => (
                <>
                  {isActive && <motion.span layoutId="activeNav" className="absolute left-0 h-6 w-1 rounded-r bg-coral" transition={{ type: "spring", stiffness: 400, damping: 35 }} />}
                  <Icon size={18} className={isActive ? "text-mint" : "text-cyan-50/70"} />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </motion.aside>
      <main className="min-w-0">
        <motion.header {...shellMotion.header} className="sticky top-0 z-10 flex items-center justify-between border-b border-white/70 bg-white/90 px-5 py-4 shadow-[0_1px_0_rgba(15,23,42,0.04)] backdrop-blur">
          <div className="min-w-0 pr-4">
            <div className="truncate text-sm text-steel">{accountSubtitle(user)}</div>
            <h1 className="truncate text-xl font-semibold">{accountCommandTitle(user)}</h1>
          </div>
          <div className="flex items-center gap-3">
            <CommandPalette />
            <div className="hidden text-right sm:block">
              <div className="text-sm font-medium">{user.name || "Guest"}</div>
              <div className="text-xs text-steel">{user.role || "Viewer"}</div>
            </div>
            <button title="Log out" onClick={logout} className="grid h-10 w-10 place-items-center rounded-md border border-slate-200 bg-white text-steel hover:text-coral">
              <LogOut size={18} />
            </button>
          </div>
        </motion.header>
        <motion.div key={location.pathname} {...shellMotion.body} className="page-shell p-5 lg:p-8">
          <Outlet />
        </motion.div>
        <FloatingCopilot />
      </main>
    </div>
  );
}
