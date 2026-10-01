import React, { useCallback, useState, useEffect, useRef } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../api/client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";

import { Icon, OdinMark } from "./Brand";

interface Message {
  role: "user" | "ai";
  content: string;
}

interface ApiMessage {
  sender?: string;
  role?: string;
  content: string;
}

interface Conversation {
  id: string;
  title: string;
  created_at: string;
}

export default function AppShell() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<
    string | null
  >(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isDark, setIsDark] = useState(() => (localStorage.getItem("odin-theme") || "light") === "dark");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [conversationSearch, setConversationSearch] = useState("");
  const [temporary, setTemporary] = useState(false);
  const initialized = useRef(false);
  const busy = useRef(false);
  const selection = useRef(0);

  // Custom Toast State
  const [toast, setToast] = useState<{
    message: string;
    type: "error" | "success";
  } | null>(null);
  const [deleteDialog, setDeleteDialog] = useState<{
    conversationId: string;
    title: string;
  } | null>(null);

  // Auto-scroll Reference
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const navigate = useNavigate();

  useEffect(() => {
    const syncTheme = () => setIsDark((localStorage.getItem("odin-theme") || "light") === "dark");
    syncTheme();
    window.addEventListener("odin-theme-change", syncTheme);
    return () => window.removeEventListener("odin-theme-change", syncTheme);
  }, []);



  useEffect(() => {
    document.documentElement.dataset.theme = isDark ? "dark" : "light";
    localStorage.setItem("odin-theme", isDark ? "dark" : "light");
  }, [isDark]);

  // Auto-scroll whenever messages or loading state changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
  }, [messages, isLoading]);

  // Auto-hide toast after 3 seconds
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const selectConversation = useCallback(async (id: string) => {
    if (busy.current) return;
    const requestId = ++selection.current;
    setSidebarOpen(false);
    setTemporary(false);
    setCurrentConversationId(null);
    setMessages([]);
    try {
      const response = await apiClient.get(`/conversations/${id}/messages`);
      if (requestId !== selection.current) return;
      setCurrentConversationId(id);
      const loadedMessages = response.data.map((msg: ApiMessage) => ({
        role:
          msg.role?.toLowerCase() === "user" ||
          msg.sender?.toLowerCase() === "user"
            ? "user"
            : "ai",
        content: msg.content,
      }));
      setMessages(
        loadedMessages.length > 0
          ? loadedMessages
          : [
              {
                role: "ai",
                content:
                  "Hello! Your advisor session is ready. How can I assist you today?",
              },
            ],
      );
    } catch {
      setToast({ message: "Failed to load messages.", type: "error" });
    }
  }, []);

  const createNewConversation = useCallback(async () => {
    if (isCreating || busy.current) return;
    setIsCreating(true);

    try {
      const response = await apiClient.post("/conversations", {
        title: "New Conversation",
      });
      const newConv = response.data;
      setConversations((prev) => [newConv, ...prev]);
      selectConversation(newConv.id);
    } catch {
      setToast({ message: "Could not create a new chat.", type: "error" });
    } finally {
      setIsCreating(false);
    }
  }, [isCreating, selectConversation]);

  const fetchConversations = useCallback(async () => {
    try {
      const response = await apiClient.get("/conversations");
      const convs = response.data;
      setConversations(convs);
      if (selection.current > 0) return;

      if (convs.length > 0 && !currentConversationId) {
        selectConversation(convs[0].id);
      } else if (convs.length === 0) {
        createNewConversation();
      }
    } catch {
      setToast({ message: "Failed to load chats.", type: "error" });
    }
  }, [createNewConversation, currentConversationId, selectConversation]);

  const handleRenameConversation = useCallback(
    async (conversationId: string) => {
      const target = conversations.find((conversation) => conversation.id === conversationId);
      const nextTitle = window.prompt(
        "Rename conversation",
        target?.title || "Untitled Chat",
      );

      if (nextTitle === null) return;

      const trimmedTitle = nextTitle.trim();
      if (!trimmedTitle) {
        setToast({ message: "Conversation name cannot be empty.", type: "error" });
        return;
      }

      try {
        const response = await apiClient.patch(`/conversations/${conversationId}`, {
          title: trimmedTitle,
        });

        const renamedConversation = response.data;
        setConversations((prev) =>
          prev.map((conversation) =>
            conversation.id === conversationId
              ? { ...conversation, title: renamedConversation.title }
              : conversation,
          ),
        );

        setToast({ message: "Conversation renamed.", type: "success" });
      } catch {
        setToast({ message: "Could not rename this conversation.", type: "error" });
      }
    },
    [conversations],
  );

  const handleDeleteConversation = useCallback(
    async (conversationId: string) => {
      const target = conversations.find((conversation) => conversation.id === conversationId);
      setDeleteDialog({
        conversationId,
        title: target?.title || "this conversation",
      });
    },
    [conversations],
  );

  const confirmDeleteConversation = useCallback(async () => {
    if (!deleteDialog) return;

    if (busy.current) return;
    const { conversationId } = deleteDialog;

    try {
      await apiClient.delete(`/conversations/${conversationId}`);

      const remainingConversations = conversations.filter(
        (conversation) => conversation.id !== conversationId,
      );
      setConversations(remainingConversations);

      if (currentConversationId === conversationId) {
        if (remainingConversations.length > 0) {
          const nextConversationId = remainingConversations[0].id;
          setCurrentConversationId(nextConversationId);
          await selectConversation(nextConversationId);
        } else {
          setCurrentConversationId(null);
          setMessages([]);
        }
      }

      setDeleteDialog(null);
      setToast({ message: "Conversation deleted.", type: "success" });
    } catch {
      setDeleteDialog(null);
      setToast({ message: "Could not delete this conversation.", type: "error" });
    }
  }, [conversations, currentConversationId, deleteDialog, selectConversation]);

  // Load conversations on mount
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (initialized.current) return;
      initialized.current = true;
      void fetchConversations();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchConversations]);

  const handleLogout = async () => {
    try {
      await apiClient.post("/auth/logout");
      navigate("/login");
    } catch {
      setToast({ message: "Logout failed.", type: "error" });
    }
  };

  const handleSendMessage = async () => {
    if (busy.current || !inputText.trim() || (!temporary && !currentConversationId)) return;
    busy.current = true;

    const userMessage = inputText;
    setInputText("");

    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await apiClient.post(
        temporary ? "/temporary-chat/messages" : `/conversations/${currentConversationId}/messages`,
        temporary ? { messages: [...messages.slice(-49).map(message => ({ role: message.role === "user" ? "user" : "assistant", content: message.content })), { role: "user", content: userMessage }] } : { content: userMessage },
      );

      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content: response.data.content || response.data.message,
        },
      ]);
    } catch (error) {
      if (temporary) {
        setMessages(previous => previous.slice(0, -1));
        setInputText(userMessage);
      }
      let message = "Network error. Failed to reach the advisor.";
      if (axios.isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (detail?.reason === "cap" || detail?.reason === "token_cap") {
          message = detail.message;
        } else if (detail?.reason === "rate") {
          message = detail.message;
        } else if (error.response?.status && error.response.status >= 500) {
          message = "The advisor service is temporarily unavailable.";
        }
      }
      setToast({
        message,
        type: "error",
      });
    } finally {
      busy.current = false;
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div onKeyDown={event => { if (event.key === "Escape") { setSidebarOpen(false); setDeleteDialog(null); } }} className={`odin-shell ${isDark ? "is-dark" : "is-light"} ${sidebarOpen ? "sidebar-open" : ""}`}>
      {/* Toast Notification Banner */}
      {toast && (
        <div
          className={`absolute top-4 right-8 px-5 py-3 rounded-xl shadow-lg transform transition-colors z-50 flex items-center gap-3 animate-fade-in ${
            toast.type === "error"
              ? "bg-red-900 text-white shadow-red-900/20"
              : "bg-slate-900 text-white"
          }`}
        >
          {toast.type === "error" && (
            <svg
              className="w-5 h-5 text-red-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          )}
          <span className="text-sm font-medium">{toast.message}</span>
        </div>
      )}

      {deleteDialog && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/45 backdrop-blur-[2px] px-4"
          onClick={() => setDeleteDialog(null)}
        >
          <div
            role="dialog" aria-modal="true" aria-label="Delete conversation" className="delete-dialog w-full max-w-md rounded-[28px] border border-white/10 bg-[#1d2a26]/95 p-6 shadow-[0_24px_70px_rgba(15,23,42,0.45)] text-white"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-5 flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-red-500/15 text-red-300 ring-1 ring-red-400/30">
                <svg
                  className="h-5 w-5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M3 6h18" />
                  <path d="M8 6V4h8v2" />
                  <path d="M19 6l-1 14H6L5 6" />
                  <path d="M10 11v6" />
                  <path d="M14 11v6" />
                </svg>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-300">
                  Delete conversation
                </p>
                <h3 className="mt-1 text-xl font-semibold text-white">
                  {deleteDialog.title}
                </h3>
              </div>
            </div>

            <p className="text-sm leading-6 text-slate-300">
              Delete "{deleteDialog.title}"? This action cannot be undone.
            </p>

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setDeleteDialog(null)}
                className="rounded-full border border-slate-500/70 bg-slate-100/5 px-6 py-2.5 text-sm font-medium text-slate-200 transition hover:border-slate-400 hover:bg-slate-100/10"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  void confirmDeleteConversation();
                }}
                className="rounded-full bg-gradient-to-r from-red-500 to-red-600 px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-red-900/30 transition hover:from-red-400 hover:to-red-500"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {sidebarOpen && <button className="sidebar-scrim" aria-label="Dismiss navigation" onClick={() => setSidebarOpen(false)} />}
      {/* Sidebar - Left Pane */}
      <aside className="w-72 flex-shrink-0 flex-col border-r border-slate-200/80 bg-white shadow-sm flex z-40">
        <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
          <h1 className="font-semibold text-slate-900 tracking-tight text-sm uppercase">
            <OdinMark /> <span>odin</span>
          </h1>
          <button
            onClick={createNewConversation}
            disabled={isCreating || isLoading}
            className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-600 text-white hover:bg-blue-500 transition-colors shadow-sm hover:shadow disabled:opacity-50"
            title="New conversation" aria-label="New conversation"
          >
            {isCreating ? (
              <svg
                className="w-4 h-4 animate-spin"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
            ) : (
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2.5"
                  d="M12 4v16m8-8H4"
                ></path>
              </svg>
            )}
          </button>
        </div>

        <button className="mobile-close" aria-label="Close navigation" onClick={() => setSidebarOpen(false)}><Icon name="close" /></button>
        <div className="sidebar-tools">
          <button type="button" onClick={() => navigate("/settings")} className="sidebar-tool">
            <Icon name="settings" /> Settings
          </button>
          <button type="button" disabled={isLoading || isCreating} className="sidebar-tool" onClick={() => {
            if (busy.current) return;
            ++selection.current;
            setSidebarOpen(false); setTemporary(true); setCurrentConversationId(null); setMessages([]); setInputText("");
          }}><Icon name="shield" /> Temporary chat</button>
          {temporary && <p className="px-3 py-2 text-xs text-slate-500" role="status">Temporary chat. Messages disappear when you leave or refresh. Odin does not save their content; the AI provider may retain data under its policy. Usage limits still apply.</p>}

        </div>

        <div className="conversation-search"><label htmlFor="conversation-search">Conversations</label><input id="conversation-search" type="search" placeholder="Find a conversation…" value={conversationSearch} onChange={event => setConversationSearch(event.target.value)} /></div>
        {/* Dynamic Conversation List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1.5 scrollbar-thin">
          {conversations.length === 0 && !isCreating && (
            <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
              <svg className="w-7 h-7 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              <p className="text-xs text-slate-400">No conversations yet.<br />Hit <strong>+</strong> to start one.</p>
            </div>
          )}
          {conversations.filter(conv => (conv.title || "Untitled Chat").toLowerCase().includes(conversationSearch.toLowerCase())).map((conv) => (
            <div
              key={conv.id}
              role="button" tabIndex={0} aria-label={`Open ${conv.title || "conversation"}`} aria-current={conv.id === currentConversationId ? "true" : undefined}
              onKeyDown={event => { if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); void selectConversation(conv.id); } }}
              onClick={() => selectConversation(conv.id)}
              className={`flex items-center justify-between w-full px-3 py-2.5 rounded-xl text-sm font-medium transition-colors cursor-pointer ${
                conv.id === currentConversationId
                  ? "bg-blue-50 text-blue-700 shadow-sm ring-1 ring-blue-500/20"
                  : "text-slate-600 hover:bg-slate-100/80 hover:text-slate-900"
              }`}
            >
              <Icon name="chat" /><span className="truncate flex-1 pr-2">
                {conv.title || "Untitled Chat"}
              </span>

              <div className="flex items-center gap-1 opacity-80">
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    void handleRenameConversation(conv.id);
                  }}
                  className="rounded-md p-1 text-slate-500 hover:bg-slate-200 hover:text-slate-900"
                  aria-label={`Rename ${conv.title || "conversation"}`}
                  title="Rename conversation"
                >
                  <svg
                    className="h-3.5 w-3.5"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M12 20h9" />
                    <path d="M16.5 3.5a2.12 2.12 0 1 1 3 3L7 19l-4 1 1-4 12.5-12.5Z" />
                  </svg>
                </button>

                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    void handleDeleteConversation(conv.id);
                  }}
                  className="rounded-md p-1 text-slate-500 hover:bg-red-100 hover:text-red-700"
                  aria-label={`Delete ${conv.title || "conversation"}`}
                  title="Delete conversation"
                >
                  <svg
                    className="h-3.5 w-3.5"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M3 6h18" />
                    <path d="M8 6V4h8v2" />
                    <path d="M19 6l-1 14H6L5 6" />
                    <path d="M10 11v6" />
                    <path d="M14 11v6" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Footer / Logout */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/30">
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
              />
            </svg>
            Log Out
          </button>
        </div>
      </aside>

      {/* Main Chat Window */}
      <main className="flex-1 flex flex-col min-w-0 bg-white relative">
        {/* Header */}
        <header className="h-16 border-b border-slate-100 flex items-center justify-between px-8 bg-white/80 backdrop-blur-md z-10 sticky top-0">
          <div className="flex items-center gap-3">
            <button className="mobile-menu" aria-label="Open navigation" aria-expanded={sidebarOpen} onClick={() => setSidebarOpen(!sidebarOpen)}><Icon name="menu" /></button>
            <h2 className="text-slate-800 font-semibold tracking-tight">
              {temporary ? "Temporary conversation" : conversations.find(conv => conv.id === currentConversationId)?.title || "Advisor"}
            </h2>
          </div>
          <span className="header-badge">{temporary ? "Not saved" : "Advisor workspace"}</span>
        </header>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-6 md:p-8 bg-gradient-to-b from-white to-slate-50/50">
          <div className="flex flex-col space-y-6 max-w-3xl mx-auto pb-4">
            {(messages.length === 0 || (messages.length === 1 && messages[0].content === "Hello! Your advisor session is ready. How can I assist you today?")) && <section className="chat-welcome"><OdinMark /><h1>What’s on your mind?</h1><p>A little clarity goes a long way.<br />Start a conversation with your advisor.</p><div className="prompt-options">{["Help me think through a decision", "Explain a complex topic", "Help me plan my next steps"].map(prompt => <button key={prompt} onClick={() => setInputText(prompt)}>{prompt}<Icon name="plus" /></button>)}</div></section>}
            {messages.filter(msg => msg.content !== "Hello! Your advisor session is ready. How can I assist you today?").map((msg, index) => (
              <div
                key={index}
                className={`flex items-start gap-4 animate-fade-in ${msg.role === "user" ? "flex-row-reverse space-x-reverse" : ""}`}
              >
                {/* Avatar */}
                <div
                  className={`h-9 w-9 rounded-2xl flex items-center justify-center font-bold text-xs flex-shrink-0 shadow-sm ${
                    msg.role === "user"
                      ? "bg-slate-900 text-white"
                      : "bg-blue-600 text-white shadow-blue-500/20"
                  }`}
                >
                  {msg.role === "user" ? "You" : <OdinMark />}
                </div>

                {/* Bubble */}
                <div
                  className={`rounded-2xl px-5 py-3.5 max-w-[80%] text-sm leading-relaxed shadow-sm overflow-x-auto ${
                    msg.role === "user"
                      ? "bg-slate-900 text-white rounded-tr-sm"
                      : "bg-white text-slate-800 border border-slate-200/70 rounded-tl-sm"
                  }`}
                >
                  {/* Markdown Renderer Applied Here */}
                  {msg.role === "ai" ? (
                    <div className="prose prose-sm prose-slate max-w-none text-slate-800">
                      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                        {String(msg.content || "")}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    msg.content
                  )}
                </div>
              </div>
            ))}

            {/* Loading Indicator */}
            {isLoading && (
              <div className="flex items-start gap-4">
                <div className="h-9 w-9 rounded-2xl bg-blue-600 text-white flex items-center justify-center font-bold text-xs flex-shrink-0 shadow-sm">
                  <OdinMark />
                </div>
                <div className="bg-white border border-slate-200/70 rounded-2xl rounded-tl-sm px-5 py-3.5 text-slate-400 text-sm shadow-sm flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-500 animate-bounce"></span>
                  <span className="w-2 h-2 rounded-full bg-blue-500 animate-bounce [animation-delay:0.2s]"></span>
                  <span className="w-2 h-2 rounded-full bg-blue-500 animate-bounce [animation-delay:0.4s]"></span>
                </div>
              </div>
            )}

            {/* Invisible div to attach the scroll listener to */}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Bar Area */}
        <div className="p-4 md:p-6 bg-white border-t border-slate-100">
          <div className="max-w-3xl mx-auto relative flex items-center">
            <textarea
              rows={2}
              aria-label="Message your advisor"
              maxLength={16000}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading || (!temporary && !currentConversationId)}
              placeholder="Ask your advisor anything..."
              className="w-full rounded-2xl border border-slate-200 bg-slate-50/50 pl-6 pr-14 py-4 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-4 focus:ring-blue-500/10 transition-colors shadow-inner disabled:opacity-50"
            />
            <button
              onClick={handleSendMessage}
              disabled={
                isLoading || !inputText.trim() || (!temporary && !currentConversationId)
              }
              className="absolute right-3 p-2.5 rounded-xl bg-blue-600 text-white hover:bg-blue-500 transition-colors shadow-sm hover:shadow disabled:opacity-40 disabled:bg-slate-300 disabled:shadow-none cursor-pointer"
              aria-label={isLoading ? "Sending…" : "Send message"}
            >
              {isLoading ? (
                <svg
                  className="w-4 h-4 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                </svg>
              ) : (
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2.5"
                    d="M14 5l7 7m0 0l-7 7m7-7H3"
                  ></path>
                </svg>
              )}
            </button>
          </div><p className="composer-help">Enter to send · Shift + Enter for a new line</p>
        </div>
      </main>
    </div>
  );
}
