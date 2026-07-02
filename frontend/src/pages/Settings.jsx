import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Bell, CheckCircle2, Globe2, KeyRound, LogOut, MailCheck, ShieldCheck, Smartphone, Trash2, UserPlus, UserRound, Users } from "lucide-react";
import { Card } from "../components/Card.jsx";
import { accountStorageKey, readStoredUser } from "../lib/account.js";
import { api } from "../lib/api.js";
import { currencyName, supportedCurrencies } from "../lib/currencies.js";

const currencies = supportedCurrencies();

function readPreferences() {
  const defaults = {
    paymentAlerts: true,
    riskAlerts: true,
    weeklyDigest: false,
    currency: "USD",
    timezone: "Asia/Kolkata",
    oneTimePaymentLimit: 5000,
  };
  const key = `ig_preferences:${accountStorageKey()}`;
  try {
    return { ...defaults, ...JSON.parse(localStorage.getItem(key) || "{}") };
  } catch {
    return defaults;
  }
}

function Notice({ children, tone = "success" }) {
  if (!children) return null;
  const style = tone === "error" ? "bg-red-50 text-coral" : "bg-emerald-50 text-emerald-700";
  return <div className={`mt-4 rounded-md px-3 py-2 text-sm ${style}`}>{children}</div>;
}

function Toggle({ label, helper, checked, onChange }) {
  return (
    <label className="flex items-center justify-between gap-4 border-b border-slate-100 py-3 last:border-b-0">
      <span>
        <span className="block text-sm font-medium">{label}</span>
        <span className="block text-xs text-steel">{helper}</span>
      </span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="h-4 w-4 accent-emerald-600" />
    </label>
  );
}

export default function Settings() {
  const navigate = useNavigate();
  const account = readStoredUser();
  const preferencesKey = `ig_preferences:${accountStorageKey(account)}`;
  const [profile, setProfile] = useState({ name: account.name || "", email: account.email || "", role: account.role || "Viewer" });
  const [preferences, setPreferences] = useState(readPreferences);
  const [passwords, setPasswords] = useState({ current: "", next: "", confirm: "" });
  const [profileNotice, setProfileNotice] = useState({ message: "", tone: "success" });
  const [passwordNotice, setPasswordNotice] = useState({ message: "", tone: "success" });
  const [preferencesNotice, setPreferencesNotice] = useState("");
  const [team, setTeam] = useState([]);
  const [teamNotice, setTeamNotice] = useState({ message: "", tone: "success" });
  const [employee, setEmployee] = useState({ name: "", email: "", password: "", role: "Viewer" });
  const [identity, setIdentity] = useState({ email_verified: Boolean(account.email_verified), mfa_enabled: Boolean(account.mfa_enabled) });
  const [mfaSetup, setMfaSetup] = useState(null);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaPassword, setMfaPassword] = useState("");
  const [securityNotice, setSecurityNotice] = useState({ message: "", tone: "success" });
  const [busy, setBusy] = useState("");
  const canManageTeam = account.account_type === "company" && account.role === "Admin";

  useEffect(() => {
    api("/api/auth/preferences")
      .then((saved) => {
        setPreferences(saved);
        localStorage.setItem(preferencesKey, JSON.stringify(saved));
      })
      .catch(() => {});
  }, [preferencesKey]);

  useEffect(() => {
    api("/api/auth/me").then((current) => {
      setIdentity({ email_verified: Boolean(current.email_verified), mfa_enabled: Boolean(current.mfa_enabled) });
      localStorage.setItem("ig_user", JSON.stringify({ ...account, ...current }));
    }).catch(() => {});
    const token = new URLSearchParams(window.location.search).get("verify_email");
    if (token) {
      api("/api/auth/email-verification/confirm", { method: "POST", body: JSON.stringify({ token }) })
        .then(() => {
          setIdentity((current) => ({ ...current, email_verified: true }));
          setSecurityNotice({ message: "Email address verified.", tone: "success" });
          window.history.replaceState({}, "", "/settings");
        })
        .catch((error) => setSecurityNotice({ message: error.message, tone: "error" }));
    }
  }, []);

  useEffect(() => {
    if (!canManageTeam) return;
    api("/api/auth/company/users")
      .then(setTeam)
      .catch(() => setTeam([]));
  }, [canManageTeam]);

  async function saveProfile(event) {
    event.preventDefault();
    if (profile.name.trim().length < 2) {
      setProfileNotice({ message: "Enter your full name before saving.", tone: "error" });
      return;
    }
    setBusy("profile");
    setProfileNotice({ message: "", tone: "success" });
    try {
      const updated = await api("/api/auth/me", { method: "PATCH", body: JSON.stringify({ name: profile.name.trim() }) });
      localStorage.setItem("ig_user", JSON.stringify(updated));
      window.dispatchEvent(new CustomEvent("ig-user-updated", { detail: updated }));
      setProfile((current) => ({ ...current, ...updated }));
      setProfileNotice({ message: "Profile updated.", tone: "success" });
    } catch (error) {
      setProfileNotice({ message: error.message, tone: "error" });
    } finally {
      setBusy("");
    }
  }

  async function updatePassword(event) {
    event.preventDefault();
    if (passwords.next !== passwords.confirm) {
      setPasswordNotice({ message: "New passwords do not match.", tone: "error" });
      return;
    }
    setBusy("password");
    setPasswordNotice({ message: "", tone: "success" });
    try {
      await api("/api/auth/password", {
        method: "POST",
        body: JSON.stringify({ current_password: passwords.current, new_password: passwords.next }),
      });
      setPasswords({ current: "", next: "", confirm: "" });
      setPasswordNotice({ message: "Password updated securely.", tone: "success" });
    } catch (error) {
      setPasswordNotice({ message: error.message, tone: "error" });
    } finally {
      setBusy("");
    }
  }

  async function savePreferences(event) {
    event.preventDefault();
    setBusy("preferences");
    setPreferencesNotice("");
    try {
      const saved = await api("/api/auth/preferences", { method: "PATCH", body: JSON.stringify(preferences) });
      localStorage.setItem(preferencesKey, JSON.stringify(saved));
      setPreferences(saved);
      setPreferencesNotice("Preferences saved to your account.");
    } catch (error) {
      setPreferencesNotice(error.message);
    } finally {
      setBusy("");
    }
  }

  async function createEmployee(event) {
    event.preventDefault();
    setBusy("team");
    setTeamNotice({ message: "", tone: "success" });
    try {
      const member = await api("/api/auth/company/users", {
        method: "POST",
        body: JSON.stringify(employee),
      });
      setTeam((current) => [member, ...current.filter((item) => item.email !== member.email)]);
      setEmployee({ name: "", email: "", password: "", role: "Viewer" });
      setTeamNotice({ message: `${member.name} can now sign in with the credentials you set.`, tone: "success" });
    } catch (error) {
      setTeamNotice({ message: error.message, tone: "error" });
    } finally {
      setBusy("");
    }
  }

  async function deactivateEmployee(member) {
    if (!window.confirm(`Deactivate ${member.name}'s LedgerOps access?`)) return;
    setBusy(`deactivate-${member.id}`);
    setTeamNotice({ message: "", tone: "success" });
    try {
      await api(`/api/auth/company/users/${member.id}`, { method: "DELETE" });
      setTeam((current) => current.filter((item) => item.id !== member.id));
      setTeamNotice({ message: `${member.name}'s access was deactivated and active sessions were revoked.`, tone: "success" });
    } catch (error) {
      setTeamNotice({ message: error.message, tone: "error" });
    } finally {
      setBusy("");
    }
  }

  async function requestVerification() {
    setBusy("verify-email");
    try {
      const result = await api("/api/auth/email-verification/request", { method: "POST" });
      setSecurityNotice({ message: result.verification_url ? `Verification link prepared: ${result.verification_url}` : result.message, tone: "success" });
    } catch (error) {
      setSecurityNotice({ message: error.message, tone: "error" });
    } finally {
      setBusy("");
    }
  }

  async function beginMfa() {
    setBusy("mfa-setup");
    try {
      const result = await api("/api/auth/mfa/setup", { method: "POST" });
      setMfaSetup(result);
      setSecurityNotice({ message: "Add the secret to your authenticator app, then enter its six-digit code.", tone: "success" });
    } catch (error) {
      setSecurityNotice({ message: error.message, tone: "error" });
    } finally {
      setBusy("");
    }
  }

  async function enableMfa() {
    setBusy("mfa-enable");
    try {
      await api("/api/auth/mfa/enable", { method: "POST", body: JSON.stringify({ code: mfaCode }) });
      setIdentity((current) => ({ ...current, mfa_enabled: true }));
      setMfaSetup(null);
      setMfaCode("");
      setSecurityNotice({ message: "Authenticator MFA enabled.", tone: "success" });
    } catch (error) {
      setSecurityNotice({ message: error.message, tone: "error" });
    } finally {
      setBusy("");
    }
  }

  async function disableMfa() {
    setBusy("mfa-disable");
    try {
      await api("/api/auth/mfa/disable", { method: "POST", body: JSON.stringify({ password: mfaPassword, code: mfaCode }) });
      setIdentity((current) => ({ ...current, mfa_enabled: false }));
      setMfaCode("");
      setMfaPassword("");
      setSecurityNotice({ message: "Authenticator MFA disabled.", tone: "success" });
    } catch (error) {
      setSecurityNotice({ message: error.message, tone: "error" });
    } finally {
      setBusy("");
    }
  }

  function signOut() {
    localStorage.clear();
    navigate("/login");
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Account settings</h2>
        <p className="mt-1 text-sm text-steel">Manage your identity, security, alerts, and finance workspace preferences.</p>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Profile">
          <form onSubmit={saveProfile} className="mt-5">
            <div className="mb-5 flex items-center gap-3">
              <div className="grid h-12 w-12 place-items-center rounded-md bg-emerald-50 text-emerald-600">
                <UserRound size={23} />
              </div>
              <div>
                <div className="font-medium">{profile.name || "Account owner"}</div>
                <div className="text-sm text-steel">{profile.role}</div>
              </div>
            </div>
            <label className="block text-sm font-medium">
              Full name
              <input value={profile.name} onChange={(event) => setProfile({ ...profile, name: event.target.value })} className="mt-1.5 w-full rounded-md border border-slate-300 px-3 py-2.5 outline-none focus:border-emerald-500" />
            </label>
            <label className="mt-4 block text-sm font-medium">
              Work email
              <input value={profile.email} disabled className="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2.5 text-steel" />
            </label>
            <button disabled={busy === "profile"} className="mt-5 rounded-md bg-ink px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">
              {busy === "profile" ? "Saving..." : "Save profile"}
            </button>
            <Notice tone={profileNotice.tone}>{profileNotice.message}</Notice>
          </form>
        </Card>

        <Card title="Security">
          <form onSubmit={updatePassword} className="mt-5">
            <div className="mb-4 flex items-start gap-3 rounded-md bg-slate-50 p-3">
              <ShieldCheck className="mt-0.5 text-emerald-600" size={20} />
              <div>
                <div className="text-sm font-medium">Password-protected account</div>
                <div className="text-xs text-steel">Update your password regularly and do not share access credentials.</div>
              </div>
            </div>
            <label className="block text-sm font-medium">
              <span className="flex items-center justify-between gap-3">
                <span>Current password</span>
                <Link to="/settings/recovery" className="text-xs font-medium text-emerald-700 hover:text-emerald-800">Forgot password?</Link>
              </span>
              <input type="password" required value={passwords.current} onChange={(event) => setPasswords({ ...passwords, current: event.target.value })} className="mt-1.5 w-full rounded-md border border-slate-300 px-3 py-2.5 outline-none focus:border-emerald-500" />
            </label>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="block text-sm font-medium">
                New password
                <input type="password" minLength={10} required value={passwords.next} onChange={(event) => setPasswords({ ...passwords, next: event.target.value })} className="mt-1.5 w-full rounded-md border border-slate-300 px-3 py-2.5 outline-none focus:border-emerald-500" />
              </label>
              <label className="block text-sm font-medium">
                Confirm password
                <input type="password" minLength={10} required value={passwords.confirm} onChange={(event) => setPasswords({ ...passwords, confirm: event.target.value })} className="mt-1.5 w-full rounded-md border border-slate-300 px-3 py-2.5 outline-none focus:border-emerald-500" />
              </label>
            </div>
            <button disabled={busy === "password"} className="mt-5 inline-flex items-center gap-2 rounded-md bg-ink px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">
              <KeyRound size={16} />
              {busy === "password" ? "Updating..." : "Update password"}
            </button>
            <Notice tone={passwordNotice.tone}>{passwordNotice.message}</Notice>
          </form>
          <div className="mt-5 space-y-3 border-t border-slate-200 pt-5">
            <div className="flex items-center justify-between gap-4 rounded-md border border-slate-200 p-3">
              <div className="flex items-center gap-3">
                <MailCheck size={19} className={identity.email_verified ? "text-mint" : "text-steel"} />
                <div>
                  <div className="text-sm font-medium">Email verification</div>
                  <div className="text-xs text-steel">{identity.email_verified ? "Verified" : "Required before live financial operations"}</div>
                </div>
              </div>
              {!identity.email_verified && <button type="button" onClick={requestVerification} disabled={busy === "verify-email"} className="rounded-md border border-slate-300 px-3 py-2 text-xs font-medium disabled:opacity-60">Send link</button>}
            </div>
            <div className="rounded-md border border-slate-200 p-3">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <Smartphone size={19} className={identity.mfa_enabled ? "text-mint" : "text-steel"} />
                  <div>
                    <div className="text-sm font-medium">Authenticator MFA</div>
                    <div className="text-xs text-steel">{identity.mfa_enabled ? "Enabled" : "Protect sign-in with a rotating six-digit code"}</div>
                  </div>
                </div>
                {!identity.mfa_enabled && !mfaSetup && <button type="button" onClick={beginMfa} disabled={busy === "mfa-setup"} className="rounded-md border border-slate-300 px-3 py-2 text-xs font-medium disabled:opacity-60">Set up</button>}
              </div>
              {mfaSetup && (
                <div className="mt-3 space-y-3 rounded-md bg-panel p-3">
                  <div className="text-xs text-steel">Authenticator secret</div>
                  <code className="block break-all rounded bg-white p-2 text-xs">{mfaSetup.secret}</code>
                  <input inputMode="numeric" maxLength={6} value={mfaCode} onChange={(event) => setMfaCode(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="Six-digit code" className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                  <button type="button" onClick={enableMfa} disabled={mfaCode.length !== 6 || busy === "mfa-enable"} className="rounded-md bg-ink px-3 py-2 text-xs font-medium text-white disabled:opacity-60">Enable MFA</button>
                </div>
              )}
              {identity.mfa_enabled && (
                <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_130px_auto]">
                  <input type="password" value={mfaPassword} onChange={(event) => setMfaPassword(event.target.value)} placeholder="Current password" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
                  <input inputMode="numeric" maxLength={6} value={mfaCode} onChange={(event) => setMfaCode(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="MFA code" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
                  <button type="button" onClick={disableMfa} disabled={!mfaPassword || mfaCode.length !== 6 || busy === "mfa-disable"} className="rounded-md border border-coral/40 px-3 py-2 text-xs font-medium text-coral disabled:opacity-60">Disable</button>
                </div>
              )}
            </div>
            <Notice tone={securityNotice.tone}>{securityNotice.message}</Notice>
          </div>
        </Card>

        <Card title="Notifications & preferences">
          <form onSubmit={savePreferences} className="mt-4">
            <div className="mb-3 flex items-center gap-2 text-sm text-steel">
              <Bell size={17} />
              Choose what LedgerOps sends to your attention queue.
            </div>
            <Toggle label="Payment activity alerts" helper="Get alerted when collections or outgoing transfers settle." checked={preferences.paymentAlerts} onChange={(value) => setPreferences({ ...preferences, paymentAlerts: value })} />
            <Toggle label="High-risk alerts" helper="Notify me when anomaly and compliance flags need review." checked={preferences.riskAlerts} onChange={(value) => setPreferences({ ...preferences, riskAlerts: value })} />
            <Toggle label="Weekly finance digest" helper="Receive a weekly summary of cash, collections, and exposure." checked={preferences.weeklyDigest} onChange={(value) => setPreferences({ ...preferences, weeklyDigest: value })} />
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-medium">
                Reporting currency
                <input
                  list="ledgerops-currencies"
                  value={preferences.currency}
                  maxLength={8}
                  onChange={(event) => setPreferences({ ...preferences, currency: event.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "") })}
                  className="mt-1.5 w-full rounded-md border border-slate-300 bg-white px-3 py-2.5"
                  placeholder="Enter ISO code, e.g. INR"
                />
                <datalist id="ledgerops-currencies">
                  {currencies.map((currency) => <option key={currency} value={currency}>{currencyName(currency)}</option>)}
                </datalist>
                <span className="mt-1 block text-xs font-normal text-steel">Supports the active ISO-4217 registry, precious-metal units, selected digital assets, and provider-specific codes. Actual money movement depends on the connected banking or payment partner.</span>
              </label>
              <label className="text-sm font-medium">
                Time zone
                <select value={preferences.timezone} onChange={(event) => setPreferences({ ...preferences, timezone: event.target.value })} className="mt-1.5 w-full rounded-md border border-slate-300 bg-white px-3 py-2.5">
                  <option value="Asia/Kolkata">India Standard Time</option>
                  <option value="UTC">UTC</option>
                  <option value="Europe/London">London</option>
                  <option value="America/New_York">New York</option>
                </select>
              </label>
              <label className="text-sm font-medium sm:col-span-2">
                One-time payment limit
                <div className="mt-1.5 grid grid-cols-[92px_1fr]">
                  <span className="rounded-l-md border border-r-0 border-slate-300 bg-slate-50 px-3 py-2.5 text-sm text-steel">{preferences.currency || "USD"}</span>
                  <input
                    type="number"
                    min="1"
                    step="1"
                    value={preferences.oneTimePaymentLimit}
                    onChange={(event) => setPreferences({ ...preferences, oneTimePaymentLimit: Number(event.target.value) || 1 })}
                    className="w-full rounded-r-md border border-slate-300 bg-white px-3 py-2.5 outline-none focus:border-emerald-500"
                    placeholder="5000"
                  />
                </div>
                <span className="mt-1 block text-xs font-normal text-steel">LedgerOps blocks single QuickLinks and outgoing payments above this amount for your account.</span>
              </label>
            </div>
            <button disabled={busy === "preferences"} className="mt-5 rounded-md bg-ink px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">{busy === "preferences" ? "Saving..." : "Save preferences"}</button>
            <Notice>{preferencesNotice}</Notice>
          </form>
        </Card>

        <Card title="Account access">
          <div className="mt-5 space-y-4">
            <div className="flex items-center justify-between rounded-md border border-slate-200 p-4">
              <div className="flex items-center gap-3">
                <Globe2 size={20} className="text-steel" />
                <div>
                  <div className="text-sm font-medium">Current session</div>
                  <div className="text-xs text-steel">Signed in as {profile.email || "your account"}</div>
                </div>
              </div>
              <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
                <CheckCircle2 size={14} />
                Active
              </span>
            </div>
            <div className="rounded-md border border-slate-200 p-4">
              <div className="text-sm font-medium">Role and permissions</div>
              <p className="mt-1 text-sm text-steel">{profile.role} access controls the payment, risk, and reporting actions available in this workspace.</p>
            </div>
            {canManageTeam && (
              <div className="rounded-md border border-slate-200 p-4">
                <div className="mb-4 flex items-start gap-3">
                  <Users size={20} className="mt-0.5 text-steel" />
                  <div>
                    <div className="text-sm font-medium">Company employee accounts</div>
                    <p className="mt-1 text-xs text-steel">Create individual logins for employees in {account.workspace_name || "this company workspace"}.</p>
                  </div>
                </div>
                <form onSubmit={createEmployee} className="grid gap-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="text-sm font-medium">
                      Employee name
                      <input required minLength={2} value={employee.name} onChange={(event) => setEmployee({ ...employee, name: event.target.value })} className="mt-1.5 w-full rounded-md border border-slate-300 px-3 py-2.5 outline-none focus:border-emerald-500" />
                    </label>
                    <label className="text-sm font-medium">
                      Work email
                      <input required type="email" value={employee.email} onChange={(event) => setEmployee({ ...employee, email: event.target.value })} className="mt-1.5 w-full rounded-md border border-slate-300 px-3 py-2.5 outline-none focus:border-emerald-500" />
                    </label>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="text-sm font-medium">
                      Temporary password
                      <input required minLength={10} type="password" value={employee.password} onChange={(event) => setEmployee({ ...employee, password: event.target.value })} className="mt-1.5 w-full rounded-md border border-slate-300 px-3 py-2.5 outline-none focus:border-emerald-500" />
                    </label>
                    <label className="text-sm font-medium">
                      Role
                      <select value={employee.role} onChange={(event) => setEmployee({ ...employee, role: event.target.value })} className="mt-1.5 w-full rounded-md border border-slate-300 bg-white px-3 py-2.5">
                        <option>Viewer</option>
                        <option>Finance Manager</option>
                      </select>
                    </label>
                  </div>
                  <button disabled={busy === "team"} className="inline-flex w-fit items-center gap-2 rounded-md bg-ink px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">
                    <UserPlus size={16} />
                    {busy === "team" ? "Creating..." : "Create employee login"}
                  </button>
                  <Notice tone={teamNotice.tone}>{teamNotice.message}</Notice>
                </form>
                <div className="mt-5 space-y-2">
                  {team.map((member) => (
                    <div key={member.id || member.email} className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2.5">
                      <div>
                        <div className="text-sm font-medium">{member.name}</div>
                        <div className="text-xs text-steel">{member.email}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-steel">{member.role}</span>
                        {member.email !== account.email && (
                          <button
                            type="button"
                            title={`Deactivate ${member.name}`}
                            onClick={() => deactivateEmployee(member)}
                            disabled={busy === `deactivate-${member.id}`}
                            className="grid h-8 w-8 place-items-center rounded-md border border-slate-200 text-steel hover:border-coral/40 hover:bg-coral/5 hover:text-coral disabled:opacity-50"
                          >
                            <Trash2 size={15} />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <button type="button" onClick={signOut} className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-4 py-2.5 text-sm font-medium hover:bg-slate-50">
              <LogOut size={16} />
              Sign out of account
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
}
