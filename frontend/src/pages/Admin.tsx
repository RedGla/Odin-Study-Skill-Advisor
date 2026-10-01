import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import { apiClient } from "../api/client";

import WorkspaceNav from "../components/WorkspaceNav";
import { Icon } from "../components/Brand";

interface UsageMetric {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  email_verified: boolean;
  created_at: string | null;
  messages_today: number;
  tokens_today: number;
  est_spend_today: number;
  messages_all_time: number;
  tokens_all_time: number;
  est_spend_all_time: number;
  last_usage_date: string | null;
}

interface ConversationSummary {
  id: string;
  user_email: string;
  title: string;
  message_count: number;
  created_at: string | null;
}

interface AdminMessage {
  id: string;
  sender: "user" | "assistant";
  content: string;
  status: string;
  prompt_tokens: number;
  completion_tokens: number;
  est_cost: number;
  created_at: string | null;
}
interface AdminConfig { daily_message_cap: number; daily_token_cap: number; rate_limit_requests: number; rate_limit_window_seconds: number; registration_enabled: boolean; chat_enabled: boolean; }
interface AdminEvent { id: string; created_at: string | null; event: string; status: string | null; user_id: string | null; user_email: string | null; conversation_id: string | null; prompt_tokens: number | null; completion_tokens: number | null; estimated_cost: number | null; reason: string | null; }

// ---------------------------------------------------------------------------
// Sorting helpers
// ---------------------------------------------------------------------------

type SortDirection = "asc" | "desc";

interface SortConfig<K extends string> {
  key: K;
  direction: SortDirection;
}

function toggleSort<K extends string>(
  current: SortConfig<K>,
  key: K,
): SortConfig<K> {
  if (current.key === key) {
    return { key, direction: current.direction === "asc" ? "desc" : "asc" };
  }
  return { key, direction: "asc" };
}

/**
 * Generic comparator that handles strings, numbers, and nullable date strings.
 * Null / empty values always sort last regardless of direction.
 */
function compare<T>(a: T, b: T, key: keyof T, direction: SortDirection): number {
  const av = a[key];
  const bv = b[key];

  // Nulls / empty strings → sort last
  const aNull = av == null || av === "";
  const bNull = bv == null || bv === "";
  if (aNull && bNull) return 0;
  if (aNull) return 1;
  if (bNull) return -1;

  let cmp: number;
  if (typeof av === "number" && typeof bv === "number") {
    cmp = av - bv;
  } else {
    cmp = String(av).localeCompare(String(bv), undefined, { sensitivity: "base" });
  }
  return direction === "asc" ? cmp : -cmp;
}

// ---------------------------------------------------------------------------
// SortableHeader — reusable clickable <th>
// ---------------------------------------------------------------------------

function SortIndicator({ active, direction }: { active: boolean; direction: SortDirection }) {
  return (
    <span
      className={`ml-1.5 inline-flex flex-col leading-none text-[10px] transition-opacity ${
        active ? "opacity-100" : "opacity-0 group-hover:opacity-40"
      }`}
    >
      <span className={active && direction === "asc" ? "text-blue-600" : "text-slate-400"}>▲</span>
      <span className={active && direction === "desc" ? "text-blue-600" : "text-slate-400"}>▼</span>
    </span>
  );
}

function SortableHeader<K extends string>({
  label,
  sortKey,
  currentSort,
  onSort,
  alignRight = false,
}: {
  label: string;
  sortKey: K;
  currentSort: SortConfig<K>;
  onSort: (key: K) => void;
  alignRight?: boolean;
}) {
  const active = currentSort.key === sortKey;
  return (
    <th
      className={`group cursor-pointer select-none px-6 py-4 font-semibold transition-colors hover:text-blue-600 ${
        alignRight ? "text-right" : ""
      } ${active ? "text-blue-600" : ""}`}
      aria-sort={active ? (currentSort.direction === "asc" ? "ascending" : "descending") : "none"}
    >
      <button type="button" onClick={() => onSort(sortKey)} className="inline-flex items-center gap-0.5">
        {label}
        <SortIndicator active={active} direction={currentSort.direction} />
      </button>
    </th>
  );
}

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

const numberFormatter = new Intl.NumberFormat();
const dateFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
});

function formatDate(value: string | null) {
  if (!value) return "No usage yet";
  return dateFormatter.format(new Date(value));
}

// ---------------------------------------------------------------------------
// Sort key types
// ---------------------------------------------------------------------------

type UsageSortKey = keyof Pick<
  UsageMetric,
  "email" | "role" | "messages_today" | "tokens_today" | "est_spend_today" | "last_usage_date"
>;

type ConversationSortKey = keyof Pick<
  ConversationSummary,
  "title" | "user_email" | "message_count" | "created_at"
>;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Admin() {
  const [metrics, setMetrics] = useState<UsageMetric[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedConversation, setSelectedConversation] = useState<ConversationSummary | null>(null);
  const [conversationMessages, setConversationMessages] = useState<AdminMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [config, setConfig] = useState<AdminConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [busyUser, setBusyUser] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [serviceStatus, setServiceStatus] = useState<{database: string; active_sessions: number; google_configured: boolean; email_configured: boolean; secure_cookies: boolean} | null>(null);
  const [configSaved, setConfigSaved] = useState(false);
  const [events, setEvents] = useState<AdminEvent[]>([]);

  // Sort state for each table
  const [usageSort, setUsageSort] = useState<SortConfig<UsageSortKey>>({
    key: "messages_today",
    direction: "desc",
  });
  const [convSort, setConvSort] = useState<SortConfig<ConversationSortKey>>({
    key: "created_at",
    direction: "desc",
  });

  const loadUsage = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [usageResponse, conversationsResponse, configResponse, eventsResponse, statusResponse] = await Promise.all([
        apiClient.get<UsageMetric[]>("/admin/usage"),
        apiClient.get<ConversationSummary[]>("/admin/conversations"),
        apiClient.get<AdminConfig>("/admin/config"),
        apiClient.get<AdminEvent[]>("/admin/events?limit=50"),
        apiClient.get("/admin/status"),
      ]);
      setServiceStatus(statusResponse.data);
      setMetrics(usageResponse.data);
      setConversations(conversationsResponse.data);
      setConfig(configResponse.data);
      setEvents(eventsResponse.data);
    } catch {
      setError("Could not load usage metrics.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const saveConfig = async () => {
    if (!config || saving) return;
    setSaving(true); setError(null); setConfigSaved(false);
    try {
      const { data } = await apiClient.put("/admin/config", config);
      setConfig(data); setConfigSaved(true);
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
      setError(typeof detail === "string" ? detail : "Could not save rules. Use positive whole numbers within the allowed limits.");
    } finally { setSaving(false); }
  };

  const manageUser = async (user: UsageMetric, action: "status" | "sessions") => {
    if (busyUser) return;
    if (!window.confirm(action === "sessions" ? `Sign out every session for ${user.email}?` : `${user.is_active ? "Suspend" : "Reactivate"} ${user.email}?`)) return;
    setBusyUser(user.id); setError(null);
    try {
      if (action === "sessions") await apiClient.post(`/admin/users/${user.id}/revoke-sessions`);
      else await apiClient.patch(`/admin/users/${user.id}`, { is_active: !user.is_active });
      await loadUsage();
    } catch { setError("The user update failed. Refresh and try again."); }
    finally { setBusyUser(null); }
  };

  const logout = async () => {
    try { await apiClient.post("/auth/logout"); window.location.assign("/login"); }
    catch { setError("Could not sign out. Please try again."); }
  };

  const openConversation = async (conversation: ConversationSummary) => {
    setSelectedConversation(conversation);
    setMessagesLoading(true);
    try {
      const response = await apiClient.get<AdminMessage[]>(`/admin/conversations/${conversation.id}/messages`);
      setConversationMessages(response.data);
    } catch {
      setConversationMessages([]);
      setError("Could not load conversation messages.");
    } finally {
      setMessagesLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadUsage();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadUsage]);

  // Sorted data (derived — no extra state needed)
  const sortedMetrics = useMemo(
    () =>
      [...metrics].filter(user => user.email.toLowerCase().includes(search.toLowerCase())).sort((a, b) => compare(a, b, usageSort.key, usageSort.direction)),
    [metrics, usageSort, search],
  );

  const sortedConversations = useMemo(
    () =>
      [...conversations].sort((a, b) => compare(a, b, convSort.key, convSort.direction)),
    [conversations, convSort],
  );

  return (
    <div className="admin-page"><WorkspaceNav admin /><main className="admin-main"><div className="page-topbar">Workspace <span>/</span> Operations</div>
      <div className="admin-content">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">
              Operations
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              Manage accounts, monitor usage, and control application rules.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/settings"
              className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-300 hover:text-blue-700"
            >
              <Icon name="settings" /> Account settings
            </Link>
            <button onClick={logout} className="rounded-lg border px-4 py-2 text-sm">Sign out</button>
            <button
              type="button"
              onClick={loadUsage}
              disabled={isLoading}
              className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-300 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isLoading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-5 flex items-center justify-between gap-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <span>{error}</span>
            <button type="button" onClick={loadUsage} className="font-semibold underline">
              Try again
            </button>
          </div>
        )}

        {serviceStatus && <section className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Service status">
          {[["Database", serviceStatus.database], ["Active sessions", serviceStatus.active_sessions], ["Google sign-in", serviceStatus.google_configured ? "Configured" : "Setup required"], ["Account emails", serviceStatus.email_configured ? "Configured" : "Setup required"]].map(([label, value]) => <div key={label} className="rounded-xl border bg-white p-4"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 font-semibold text-slate-900">{value}</p></div>)}
        </section>}
        {config && (
          <section className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="font-semibold text-slate-900">Application rules</h2>
            <p className="mt-1 text-sm text-slate-500">Rules apply to new requests immediately. Pausing chat keeps saved conversations readable.</p>
            <div className="mt-4 flex flex-wrap gap-5 text-sm">
              <label><input type="checkbox" checked={config.registration_enabled} onChange={event => {setConfig({...config, registration_enabled: event.target.checked}); setConfigSaved(false);}} /> Allow new registrations</label>
              <label><input type="checkbox" checked={config.chat_enabled} onChange={event => {setConfig({...config, chat_enabled: event.target.checked}); setConfigSaved(false);}} /> Allow new chat messages</label>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {([['daily_message_cap', 'Daily messages'], ['daily_token_cap', 'Daily tokens'], ['rate_limit_requests', 'Requests per window'], ['rate_limit_window_seconds', 'Window seconds']] as const).map(([key, label]) => (
                <label key={key} className="text-sm font-medium text-slate-700">{label}
                  <input type="number" min="1" value={config[key]} onChange={(event) => { setConfig({ ...config, [key]: Number(event.target.value) }); setConfigSaved(false); }} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
                </label>
              ))}
            </div>
            <button type="button" disabled={saving} onClick={() => void saveConfig()} className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700">{saving ? "Saving…" : configSaved ? "Saved" : "Save rules"}</button>
          </section>
        )}

        <section className="mt-8 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-6 py-4"><h2 className="font-semibold text-slate-900">Operational events</h2><p className="mt-1 text-sm text-slate-500">Recent blocked requests, cache activity, failures, and completed calls. Conversation content remains in the conversation viewer.</p></div>
          <div className="overflow-x-auto"><table className="min-w-full divide-y divide-slate-200 text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500"><tr><th className="px-6 py-3">Time</th><th className="px-6 py-3">Event</th><th className="px-6 py-3">User</th><th className="px-6 py-3">Status / reason</th><th className="px-6 py-3 text-right">Usage</th></tr></thead><tbody className="divide-y divide-slate-100">{events.map((item) => <tr key={item.id}><td className="whitespace-nowrap px-6 py-3 text-slate-500">{item.created_at ? new Date(item.created_at).toLocaleString() : "—"}</td><td className="px-6 py-3 font-medium text-slate-800">{item.event}</td><td className="px-6 py-3 text-slate-500">{item.user_email || item.user_id || "system"}</td><td className="px-6 py-3 text-slate-500">{item.status || "—"}{item.reason ? ` · ${item.reason}` : ""}</td><td className="px-6 py-3 text-right text-xs text-slate-500">{item.prompt_tokens ?? 0} + {item.completion_tokens ?? 0}{item.estimated_cost != null ? ` · $${item.estimated_cost.toFixed(4)}` : ""}</td></tr>)}{!events.length && <tr><td colSpan={5} className="px-6 py-8 text-center text-slate-500">No operational events found.</td></tr>}</tbody></table></div>
        </section>

        <section className="my-8 rounded-xl border bg-white p-6">
          <h2 className="font-semibold text-slate-900">Account management</h2>
          <label className="mt-4 block text-sm text-slate-600">Search accounts<input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by email" className="mt-1 w-full rounded-lg border px-3 py-2" /></label>
          <div className="mt-4 max-h-96 overflow-auto divide-y">{sortedMetrics.map(user => <div key={user.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
            <div><p className="font-medium text-slate-800">{user.email}</p><p className="text-xs text-slate-500">{user.role} · {user.is_active ? "Active" : "Suspended"} · {user.email_verified ? "Email verified" : "Verification pending"}</p></div>
            <div className="flex gap-3 text-sm"><button disabled={busyUser !== null} onClick={() => void manageUser(user, "sessions")} className="rounded-lg border px-3 py-2 disabled:opacity-50">Revoke sessions</button>{user.role !== "admin" && <button disabled={busyUser !== null} onClick={() => void manageUser(user, "status")} className="rounded-lg border px-3 py-2 disabled:opacity-50">{user.is_active ? "Suspend" : "Reactivate"}</button>}</div>
          </div>)}</div>
        </section>
        {/* ---- Usage metrics table ---- */}
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"><div className="border-b px-6 py-4"><h2 className="font-semibold">Usage by account</h2><p className="mt-1 text-sm text-slate-500">Daily activity and estimated spend across the workspace.</p></div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <SortableHeader label="User" sortKey="email" currentSort={usageSort} onSort={(k) => setUsageSort(toggleSort(usageSort, k))} />
                  <SortableHeader label="Role" sortKey="role" currentSort={usageSort} onSort={(k) => setUsageSort(toggleSort(usageSort, k))} />
                  <SortableHeader label="Messages today" sortKey="messages_today" currentSort={usageSort} onSort={(k) => setUsageSort(toggleSort(usageSort, k))} alignRight />
                  <SortableHeader label="Tokens today" sortKey="tokens_today" currentSort={usageSort} onSort={(k) => setUsageSort(toggleSort(usageSort, k))} alignRight />
                  <SortableHeader label="Spend today" sortKey="est_spend_today" currentSort={usageSort} onSort={(k) => setUsageSort(toggleSort(usageSort, k))} alignRight />
                  <th className="px-6 py-4 text-right font-semibold">All time</th>
                  <SortableHeader label="Latest usage" sortKey="last_usage_date" currentSort={usageSort} onSort={(k) => setUsageSort(toggleSort(usageSort, k))} />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading && (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                      <span className="inline-flex items-center gap-2">
                        <svg className="w-4 h-4 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                        </svg>
                        Loading usage metrics…
                      </span>
                    </td>
                  </tr>
                )}
                {!isLoading && sortedMetrics.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                      No users found.
                    </td>
                  </tr>
                )}
                {!isLoading && sortedMetrics.map((metric) => (
                  <tr key={metric.id} className="transition hover:bg-slate-50">
                    <td className="whitespace-nowrap px-6 py-4 font-medium text-slate-900">
                      {metric.email}
                    </td>
                    <td className="px-6 py-4 capitalize text-slate-500">{metric.role}</td>
                    <td className="px-6 py-4 text-right tabular-nums text-slate-700">
                      {numberFormatter.format(metric.messages_today)}
                    </td>
                    <td className="px-6 py-4 text-right tabular-nums text-slate-700">
                      {numberFormatter.format(metric.tokens_today)}
                    </td>
                    <td className="px-6 py-4 text-right tabular-nums text-slate-700">
                      ${metric.est_spend_today.toFixed(4)}
                    </td>
                    <td className="px-6 py-4 text-right text-xs text-slate-500">
                      {numberFormatter.format(metric.messages_all_time)} msgs · {numberFormatter.format(metric.tokens_all_time)} tokens<br />
                      ${metric.est_spend_all_time.toFixed(4)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-slate-500">
                      {formatDate(metric.last_usage_date)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* ---- Conversations table ---- */}
        <section className="mt-8 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-6 py-4">
            <h2 className="font-semibold text-slate-900">Recent conversations</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <SortableHeader label="Title" sortKey="title" currentSort={convSort} onSort={(k) => setConvSort(toggleSort(convSort, k))} />
                  <SortableHeader label="User" sortKey="user_email" currentSort={convSort} onSort={(k) => setConvSort(toggleSort(convSort, k))} />
                  <SortableHeader label="Messages" sortKey="message_count" currentSort={convSort} onSort={(k) => setConvSort(toggleSort(convSort, k))} alignRight />
                  <SortableHeader label="Created" sortKey="created_at" currentSort={convSort} onSort={(k) => setConvSort(toggleSort(convSort, k))} />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading && (
                  <tr>
                    <td colSpan={4} className="px-6 py-10 text-center text-slate-500">
                      <span className="inline-flex items-center gap-2">
                        <svg className="w-4 h-4 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                        </svg>
                        Loading conversations…
                      </span>
                    </td>
                  </tr>
                )}
                {!isLoading && sortedConversations.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 py-10 text-center text-slate-500">
                      No conversations found.
                    </td>
                  </tr>
                )}
                {!isLoading && sortedConversations.map((conversation) => (
                  <tr key={conversation.id} className="transition hover:bg-slate-50">
                    <td className="px-6 py-4 font-medium text-slate-900"><button type="button" onClick={() => void openConversation(conversation)} className="text-left hover:text-blue-700 hover:underline">{conversation.title}</button></td>
                    <td className="px-6 py-4 text-slate-500">{conversation.user_email}</td>
                    <td className="px-6 py-4 text-right tabular-nums text-slate-700">
                      {numberFormatter.format(conversation.message_count)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-slate-500">
                      {formatDate(conversation.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {selectedConversation && (
          <section className="mt-8 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div><h2 className="font-semibold text-slate-900">Conversation details</h2><p className="text-sm text-slate-500">{selectedConversation.title} · {selectedConversation.user_email}</p></div>
              <button type="button" onClick={() => setSelectedConversation(null)} className="text-sm font-semibold text-slate-500 hover:text-slate-900">Close</button>
            </div>
            {messagesLoading ? <p className="px-6 py-8 text-sm text-slate-500">Loading messages…</p> : (
              <div className="divide-y divide-slate-100">
                {conversationMessages.map((message) => (
                  <article key={message.id} className="px-6 py-5">
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500"><span className="font-semibold uppercase">{message.sender} · {message.status}</span><span>{message.created_at ? new Date(message.created_at).toLocaleString() : "No timestamp"}</span></div>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">{message.content || "(empty)"}</p>
                    <p className="mt-2 text-xs text-slate-500">Prompt: {message.prompt_tokens ?? 0} · Completion: {message.completion_tokens ?? 0} · Est. cost: ${(message.est_cost ?? 0).toFixed(4)}</p>
                  </article>
                ))}
                {!conversationMessages.length && <p className="px-6 py-8 text-sm text-slate-500">No messages found.</p>}
              </div>
            )}
          </section>
        )}
      </div>
    </main></div>
  );
}
