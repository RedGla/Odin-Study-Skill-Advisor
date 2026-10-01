import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { apiClient } from "../api/client";

import WorkspaceNav from "../components/WorkspaceNav";
import { OdinMark } from "../components/Brand";

type Theme = "dark" | "light";

function Icon({ name }: { name: "arrow" | "check" }) {
  const path = name === "arrow" ? <><path d="M19 12H5" /><path d="m12 19-7-7 7-7" /></> : <path d="m5 12 4 4L19 6" />;
  return <svg className="odin-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{path}</svg>;
}

export default function Settings() {
  const navigate = useNavigate();
  const [theme, setTheme] = useState<Theme>((localStorage.getItem("odin-theme") as Theme) || "light");
  const [role, setRole] = useState("user");
  const [googleLinked, setGoogleLinked] = useState(false);
  const [email, setEmail] = useState("your account");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("odin-theme", theme);
    window.dispatchEvent(new Event("odin-theme-change"));
  }, [theme]);

  useEffect(() => {
    apiClient
      .get("/auth/me")
      .then(({ data }) => { setEmail(data.email); setRole(data.role); setGoogleLinked(data.google_linked); })
      .catch(() => setError("Could not load account details."));
  }, []);

  const changePassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage("");
    setError("");
    setIsSubmitting(true);
    try {
      await apiClient.post("/auth/change-password", { current_password: currentPassword, new_password: newPassword });
      setCurrentPassword("");
      setNewPassword("");
      setMessage("Your password was updated. Other sessions have been signed out.");
    } catch (requestError) {
      setError(axios.isAxiosError(requestError) ? String(requestError.response?.data?.detail || "Could not update password.") : "Could not update password.");
    } finally {
      setIsSubmitting(false);
    }
  };

  async function linkGoogle() {
    setError("");
    try {
      const { data } = await apiClient.post("/auth/google/start?link=true");
      window.location.assign(data.url);
    } catch { setError("Could not start Google linking. Check that Google sign-in is configured."); }
  }

  return (
    <div className={`settings-page ${theme === "dark" ? "is-dark" : "is-light"}`}>
      <WorkspaceNav admin={role === "admin"} />
      <main className="settings-main"><div className="page-topbar">Workspace <span>/</span> Settings<button onClick={() => navigate(role === "admin" ? "/admin" : "/")}><Icon name="arrow" /> Back to workspace</button></div>
        <header className="settings-header"><div><h1>Settings</h1><p>Shape Odin around the way you think and work.</p></div></header>
        <div className="settings-content">
          <section className="settings-section"><div className="section-title"><h2>Appearance</h2><p>Choose the atmosphere for your advisor workspace.</p></div><div className="theme-options">
            <button className={`theme-option ${theme === "dark" ? "selected" : ""}`} aria-pressed={theme === "dark"} onClick={() => setTheme("dark")}><div className="theme-preview preview-dark"><OdinMark /><i /><i /><i /></div><div><strong>Dark mode</strong><span>Focused and easy on the eyes</span></div>{theme === "dark" && <b><Icon name="check" /></b>}</button>
            <button className={`theme-option ${theme === "light" ? "selected" : ""}`} aria-pressed={theme === "light"} onClick={() => setTheme("light")}><div className="theme-preview preview-light"><OdinMark /><i /><i /><i /></div><div><strong>Light mode</strong><span>Bright and open</span></div>{theme === "light" && <b><Icon name="check" /></b>}</button>
          </div></section>
          <section className="settings-section"><div className="section-title"><h2>Account & security</h2><p>Keep your account details protected.</p></div><div className="account-row"><div><span className="field-label">Email address</span><strong>{email}</strong></div><span className="account-role">{role}</span></div><p className="mt-4 text-sm">{googleLinked ? "Google account linked." : <button className="primary-button" onClick={linkGoogle}>Link Google account</button>}</p><form className="password-form" onSubmit={changePassword}><h3>Change password</h3><div className="form-grid"><label>Current password<input type="password" autoComplete="current-password" required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label><label>New password<input type="password" required minLength={15} maxLength={128} autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></label></div><div className="form-actions"><span className={error ? "form-error" : "form-success"}>{error || message}</span><button className="primary-button" type="submit" disabled={isSubmitting} style={isSubmitting ? {opacity: 0.65, cursor: 'not-allowed'} : {}}>{isSubmitting ? (<span style={{display:'inline-flex',alignItems:'center',gap:'6px'}}><svg style={{width:13,height:13}} className="animate-spin" fill="none" viewBox="0 0 24 24"><circle style={{opacity:.25}} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" /><path style={{opacity:.75}} fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>Updating…</span>) : 'Update password'}</button></div></form></section>
        </div>
      </main>
    </div>
  );
}
