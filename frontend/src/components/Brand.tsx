export function OdinMark({ className = "" }: { className?: string }) {
  return <svg className={`odin-mark ${className}`} viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M23 7a12 12 0 1 0 4.3 7" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round"/><path d="m16 16 11-11M21 5h6v6" stroke="var(--accent)" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}

export type IconName = "chat" | "settings" | "shield" | "arrow" | "menu" | "close" | "plus" | "logout";
export function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  const paths: Record<IconName, string> = {
    chat: "M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9H13a8.5 8.5 0 0 1 8 8v.5Z",
    settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1 1-3Z",
    shield: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Zm-4 9 3 3 5-6",
    arrow: "M19 12H5m7 7-7-7 7-7", menu: "M4 6h16M4 12h16M4 18h16", close: "m6 6 12 12M6 18 18 6",
    plus: "M12 5v14M5 12h14", logout: "M9 4H4v16h5m5-13 5 5-5 5M8 12h11",
  };
  return <svg className={`odin-icon ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}
