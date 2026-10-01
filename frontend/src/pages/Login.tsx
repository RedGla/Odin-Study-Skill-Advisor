import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../api/client";

import { OdinMark, Icon } from "../components/Brand";

type Mode = "login" | "register" | "forgot" | "resend" | "reset" | "verify";

export default function Login() {
  const [link] = useState(() => new URLSearchParams(window.location.hash.slice(1)));
  const [mode, setMode] = useState<Mode>(() => link.get("action") === "reset" ? "reset" : link.get("action") === "verify" ? "verify" : "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState(new URLSearchParams(window.location.search).has("google_error") ? "Google sign-in failed or was cancelled. If you already have a password account, sign in and link Google in Settings." : "");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const navigate = useNavigate();
  const newPassword = mode === "register" || mode === "reset";
  const needsEmail = !["reset", "verify"].includes(mode);
  const needsPassword = ["login", "register", "reset"].includes(mode);
  const labels: Record<Mode, string> = { login: "Sign in", register: "Create account", forgot: "Reset password", resend: "Resend verification", reset: "Save new password", verify: "Verify email" };

  useEffect(() => {
    window.history.replaceState(null, "", "/login");
    apiClient.get("/auth/options").then(({ data }) => setGoogleEnabled(data.google_enabled)).catch(() => {});
  }, []);

  function switchMode(next: Mode) {
    setMode(next); setError(""); setNotice(""); setPassword(""); setConfirmPassword("");
  }

  function reportError(err: unknown) {
    const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
    setError(typeof detail === "string" ? detail : Array.isArray(detail) ? "Check your email address and password. Addresses with dots, such as ellise.cruz@gmail.com, are supported." : "Unable to reach the service. Please try again.");
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (loading) return;
    setError(""); setNotice("");
    if (newPassword && password !== confirmPassword) { setError("Passwords do not match."); return; }
    setLoading(true);
    try {
      const normalizedEmail = email.trim().toLowerCase();
      if (mode === "login") {
        const { data } = await apiClient.post("/auth/login", { email: normalizedEmail, password });
        try { await apiClient.get("/auth/me"); }
        catch { setError("Your browser did not retain the sign-in cookie. Check your browser cookie settings or contact the administrator."); return; }
        navigate(data.role === "admin" ? "/admin" : "/", { replace: true });
      } else {
        const endpoint = { register: "register", forgot: "forgot-password", resend: "resend-verification", reset: "reset-password", verify: "verify-email" }[mode];
        const body = mode === "verify" ? { token: link.get("token") } : mode === "reset" ? { token: link.get("token"), password } : { email: normalizedEmail, ...(mode === "register" ? { password } : {}) };
        const { data } = await apiClient.post(`/auth/${endpoint}`, body);
        setNotice(data.message);
        setPassword(""); setConfirmPassword("");
        if (mode === "verify" || mode === "reset") setMode("login");
      }
    } catch (err) { reportError(err); }
    finally { setLoading(false); }
  }

  async function googleLogin() {
    setLoading(true); setError("");
    try {
      const { data } = await apiClient.post("/auth/google/start");
      window.location.assign(data.url);
    } catch (err) { reportError(err); setLoading(false); }
  }

  const inputClass = "mt-2 w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500";
  return (
    <main className="login-page">
      <aside className="login-story">
        <div className="brand-lockup"><OdinMark /><span>odin<span className="brand-caption">Advisor console</span></span></div>
        <div className="login-story-content"><span className="story-rule" /><h2>A clearer space<br />to think.</h2><p>Ask questions. Explore ideas.<br />Pick up where you left off.</p><div className="story-details"><span><Icon name="chat" /> Saved conversations</span><span><Icon name="shield" /> Account controls</span><span><Icon name="settings" /> Your workspace, your way</span></div></div>
        <p className="story-footer">Clarity starts with a conversation.</p>
      </aside><div className="login-form-region">
      <section className="login-form">
        <div className="login-mobile-brand brand-lockup"><OdinMark /><span>odin</span></div>
        <h1 className="text-3xl font-bold text-slate-900">{mode === "login" ? "Welcome back." : labels[mode]}</h1>
        <p className="mt-2 mb-6 text-sm text-slate-500">{mode === "register" ? "Use your email address. We’ll send a link to verify it." : mode === "verify" ? "Confirm your email to finish setting up your account." : "Sign in to your Odin workspace."}</p>
        {error && <p role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {notice && <p role="status" className="mb-4 rounded-lg bg-green-50 p-3 text-sm text-green-800">{notice}</p>}
        <form onSubmit={handleSubmit} className="space-y-4">
          {needsEmail && <label className="block text-sm font-medium text-slate-700">Email address<input type="email" name="email" autoComplete="email" autoCapitalize="none" spellCheck={false} required maxLength={254} value={email} onChange={e => setEmail(e.target.value)} onBlur={() => setEmail(email.trim())} className={inputClass} placeholder="you@example.com" /></label>}
          {needsPassword && <label className="block text-sm font-medium text-slate-700">{newPassword ? "New password" : "Password"}<input type="password" name="password" required minLength={newPassword ? 15 : undefined} maxLength={128} autoComplete={newPassword ? "new-password" : "current-password"} value={password} onChange={e => setPassword(e.target.value)} className={inputClass} />{newPassword && <span className="mt-1 block text-xs text-slate-500">15–128 characters. A long, unique passphrase works well.</span>}</label>}
          {newPassword && <label className="block text-sm font-medium text-slate-700">Confirm password<input type="password" name="confirmPassword" required minLength={15} maxLength={128} autoComplete="new-password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} className={inputClass} /></label>}
          <button disabled={loading} className="primary-button w-full rounded-lg bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700 disabled:opacity-50">{loading ? "Please wait…" : labels[mode]}</button>
        </form>
        {(mode === "login" || mode === "register") && <><div className="my-4 text-center text-xs text-slate-400">or</div><button type="button" onClick={googleLogin} disabled={loading || !googleEnabled} className="w-full rounded-lg border border-slate-300 px-4 py-3 font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"><svg className="odin-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M21 12.2c0-.7-.1-1.4-.2-2.2H12v4h5.1a4.4 4.4 0 0 1-1.9 2.8 6 6 0 1 1 0-9.6l3-3A10 10 0 1 0 22 12Z" /></svg>Continue with Google</button>{!googleEnabled && <p className="mt-2 text-center text-xs text-slate-500">Google sign-in is awaiting administrator setup.</p>}</>}
        <nav aria-label="Account help" className="mt-6 flex flex-wrap justify-center gap-3 text-sm text-blue-700">
          {mode !== "login" && <button disabled={loading} onClick={() => switchMode("login")}>Back to sign in</button>}
          {mode === "login" && <><button disabled={loading} onClick={() => switchMode("register")}>Create account</button><button disabled={loading} onClick={() => switchMode("forgot")}>Forgot password?</button><button disabled={loading} onClick={() => switchMode("resend")}>Resend verification</button></>}
        </nav>
      </section><p className="login-bottom">Odin · Advisor console</p></div>
    </main>
  );
}
