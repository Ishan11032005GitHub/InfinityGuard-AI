import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";

const Dashboard = lazy(() => import("./pages/Dashboard.jsx"));
const DataPage = lazy(() => import("./pages/DataPage.jsx"));
const IntelligencePage = lazy(() => import("./pages/IntelligencePage.jsx"));
const Login = lazy(() => import("./pages/Login.jsx"));
const PasswordRecovery = lazy(() => import("./pages/PasswordRecovery.jsx"));
const PaymentApp = lazy(() => import("./pages/PaymentApp.jsx"));
const QuickLinks = lazy(() => import("./pages/QuickLinks.jsx"));
const QuickLinkCheckout = lazy(() => import("./pages/QuickLinkCheckout.jsx"));
const Settings = lazy(() => import("./pages/Settings.jsx"));
const CountryCodes = lazy(() => import("./pages/CountryCodes.jsx"));
const ProductOps = lazy(() => import("./pages/ProductOps.jsx"));
const Copilot = lazy(() => import("./pages/Copilot.jsx"));

function Protected({ children }) {
  return localStorage.getItem("ig_access_token") ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-steel">Loading LedgerOps...</div>}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Login mode="signup" />} />
        <Route path="/forgot-password" element={<PasswordRecovery />} />
        <Route path="/reset-password" element={<PasswordRecovery mode="reset" />} />
        <Route path="/pay/:publicId" element={<QuickLinkCheckout />} />
        <Route path="/index.html" element={<Navigate to="/" replace />} />
        <Route element={<Protected><Layout /></Protected>}>
          <Route index element={<Dashboard />} />
          <Route path="/payments" element={<DataPage type="payments" />} />
          <Route path="/payment-app" element={<PaymentApp />} />
          <Route path="/quicklinks" element={<QuickLinks />} />
          <Route path="/invoices" element={<DataPage type="invoices" />} />
          <Route path="/clients" element={<DataPage type="customers" />} />
          <Route path="/customers" element={<Navigate to="/clients" replace />} />
          <Route path="/country-codes" element={<CountryCodes />} />
          <Route path="/fx" element={<IntelligencePage mode="fx" />} />
          <Route path="/fraud" element={<IntelligencePage mode="fraud" />} />
          <Route path="/cash" element={<IntelligencePage mode="cash" />} />
          <Route path="/compliance" element={<IntelligencePage mode="compliance" />} />
          <Route path="/copilot" element={<Copilot />} />
          <Route path="/action-center" element={<ProductOps mode="action-center" />} />
          <Route path="/payment-timeline" element={<ProductOps mode="payment-timeline" />} />
          <Route path="/receipt-center" element={<ProductOps mode="receipt-center" />} />
          <Route path="/client-profiles" element={<ProductOps mode="client-profiles" />} />
          <Route path="/approvals" element={<ProductOps mode="approvals" />} />
          <Route path="/audit-log" element={<ProductOps mode="audit" />} />
          <Route path="/notifications" element={<ProductOps mode="notifications" />} />
          <Route path="/reconciliation" element={<ProductOps mode="reconciliation" />} />
          <Route path="/permissions" element={<ProductOps mode="permissions" />} />
          <Route path="/demo-story" element={<ProductOps mode="demo-story" />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/settings/recovery" element={<PasswordRecovery insideAccount />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
