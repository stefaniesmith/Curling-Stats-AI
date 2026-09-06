import { FormEvent, useEffect, useRef, useState } from "react";

import logoUrl from "../../../CurlChatLogo.png";
import { ApiError, listConversations, sendMessage } from "../lib/api";
import { ResponseBlocks } from "../features/visualizations/ResponseBlocks";
import type { Conversation, ResponseBlock } from "../types/api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content?: string;
  blocks?: ResponseBlock[];
}

const prompts = [
  "Show Brad Jacobs' Brier stats.",
  "Compare Rachel Homan and Jennifer Jones from 2018 to 2024.",
  "Who had the highest draw percentage at the 2023 Hearts?",
];

export function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);
  const [error, setError] = useState<string>();
  const messagesContainer = useRef<HTMLDivElement>(null);

  const refreshConversations = async () => {
    setIsLoadingConversations(true);
    try {
      setConversations(await listConversations());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load conversations.");
    } finally {
      setIsLoadingConversations(false);
    }
  };

  useEffect(() => { void refreshConversations(); }, []);
  useEffect(() => {
    const transcript = messagesContainer.current;
    if (transcript) {
      transcript.scrollTo({ top: transcript.scrollHeight, behavior: "smooth" });
    }
  }, [messages, isSending]);

  const newConversation = () => {
    setActiveConversationId(undefined);
    setMessages([]);
    setDraft("");
    setError(undefined);
  };

  const selectConversation = (id: string) => {
    setActiveConversationId(id);
    setMessages([]);
    setError(undefined);
  };

  const submit = async (event?: FormEvent, message = draft) => {
    event?.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || isSending) return;
    setDraft("");
    setError(undefined);
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: trimmed }]);
    setIsSending(true);
    try {
      const response = await sendMessage({ message: trimmed, conversation_id: activeConversationId });
      setActiveConversationId(response.conversation_id);
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", blocks: response.blocks }]);
      await refreshConversations();
    } catch (cause) {
      const apiError = cause instanceof ApiError ? cause : new ApiError("CurlChat could not answer that question.");
      setError(apiError.status === 404 ? "This conversation is no longer available. Start a new one to continue." : apiError.message);
    } finally {
      setIsSending(false);
    }
  };

  const activeTitle = conversations.find((conversation) => conversation.id === activeConversationId)?.title;
  const isWelcome = messages.length === 0;

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <img src={logoUrl} alt="CurlChat" className="sidebar-logo" />
          <span>CurlChat</span>
        </div>
        <button className="new-chat" onClick={newConversation}><span>＋</span> New conversation</button>
        <div className="conversation-heading"><span>Recent conversations</span><button aria-label="Refresh conversations" onClick={() => void refreshConversations()}>↻</button></div>
        <nav className="conversation-list" aria-label="Recent conversations">
          {isLoadingConversations ? <p className="sidebar-status">Loading conversations…</p> : conversations.length ? conversations.map((conversation) => (
            <button className={conversation.id === activeConversationId ? "conversation active" : "conversation"} key={conversation.id} onClick={() => selectConversation(conversation.id)}>
              <span>{conversation.title}</span><small>{new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(conversation.updated_at))}</small>
            </button>
          )) : <p className="sidebar-status">Your conversations will appear here.</p>}
        </nav>
        <div className="sidebar-foot">Curling Canada stats archive<br />AI-assisted analysis</div>
      </aside>

      <section className="chat-panel">
        <header className="chat-header"><div><p>CONVERSATIONAL ANALYTICS</p><h1>{activeTitle ?? "New conversation"}</h1></div><span className="status-dot">Archive connected</span></header>
        <div className="messages" ref={messagesContainer}>
          {isWelcome && <Welcome onPrompt={(prompt) => void submit(undefined, prompt)} />}
          {messages.map((message) => <article className={`message ${message.role}`} key={message.id}>
            <div className="message-label">{message.role === "assistant" ? "CurlChat" : "You"}</div>
            {message.content && <p>{message.content}</p>}
            {message.blocks && <ResponseBlocks blocks={message.blocks} />}
          </article>)}
          {isSending && <article className="message assistant thinking"><div className="message-label">CurlChat</div><span></span><span></span><span></span></article>}
          {error && <div className="error-banner"><strong>Unable to complete the request.</strong> {error}</div>}
        </div>
        <form className="composer" onSubmit={submit}>
          <textarea value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ask about a player, event, season, or statistic…" rows={1} disabled={isSending} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submit(); } }} />
          <button type="submit" disabled={isSending || !draft.trim()} aria-label="Send message">↑</button>
        </form>
        <p className="composer-note">CurlChat uses the Curling Canada statistics archive. Results may include historical source records.</p>
      </section>
    </main>
  );
}

function Welcome({ onPrompt }: { onPrompt: (prompt: string) => void }) {
  return <section className="welcome">
    <img src={logoUrl} alt="CurlChat — Curling stats. AI insights." className="welcome-logo" />
    <p>Explore historical player performance with natural language, interactive charts, and source-grounded statistics.</p>
    <div className="prompt-grid">{prompts.map((prompt) => <button key={prompt} onClick={() => onPrompt(prompt)}>{prompt}<span>→</span></button>)}</div>
  </section>;
}
