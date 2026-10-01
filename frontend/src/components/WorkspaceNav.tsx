import { NavLink } from "react-router-dom";
import { Icon, OdinMark } from "./Brand";

export default function WorkspaceNav({ admin = false }: { admin?: boolean }) {
  return <aside className="workspace-nav">
    <NavLink to={admin ? "/admin" : "/"} className="brand-lockup" aria-label="Odin workspace"><OdinMark /><span>odin<span className="brand-caption">Advisor console</span></span></NavLink>
    <nav aria-label="Workspace navigation">
      <NavLink to={admin ? "/admin" : "/"} aria-label={admin ? "Operations" : "Advisor"} end><Icon name={admin ? "shield" : "chat"} /><span>{admin ? "Operations" : "Advisor"}</span></NavLink>
      <NavLink to="/settings" aria-label="Settings"><Icon name="settings" /><span>Settings</span></NavLink>
    </nav>
    <div className="nav-foot"><span className="brand-dot" /><span>Odin workspace</span></div>
  </aside>;
}
