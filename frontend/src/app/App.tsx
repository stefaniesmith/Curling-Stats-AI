import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import logoUrl from "../../../assets/CurlChatLogo.png";
import { ApiError, getConversationMessages, listConversations, streamMessage } from "../lib/api";
import { ResponseBlocks } from "../features/visualizations/ResponseBlocks";
import type { ArtifactBlock, Conversation, ResponseBlock } from "../types/api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content?: string;
  blocks?: ResponseBlock[];
}

const prompts = [
  "Show Brad Jacobs' stats at the 2026 Brier.",
  "Compare Rachel Homan and Jennifer Jones from 2018-2024.",
  "Who had the highest draw percentage at the 2023 Hearts?",
];

export function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);
  const [activity, setActivity] = useState<string>();
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

  useEffect(() => {
    void refreshConversations();
  }, []);
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
    setActivity(undefined);
    setIsLoadingHistory(false);
  };

  const selectConversation = async (id: string) => {
    setActiveConversationId(id);
    setMessages([]);
    setError(undefined);
    setActivity(undefined);
    setIsLoadingHistory(true);
    try {
      const history = await getConversationMessages(id);
      setMessages(
        history.map((message) => ({
          id: crypto.randomUUID(),
          role: message.role,
          content: message.role === "user" ? message.content : undefined,
          blocks: message.role === "assistant" ? message.blocks : undefined,
        })),
      );
    } catch (cause) {
      const apiError =
        cause instanceof ApiError ? cause : new ApiError("Could not load this conversation.");
      setError(
        apiError.status === 404
          ? "This conversation is no longer available. Start a new one to continue."
          : apiError.message,
      );
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const submit = async (event?: FormEvent, message = draft) => {
    event?.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || isSending) return;
    setDraft("");
    setError(undefined);
    setActivity("Resolving context");
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: trimmed },
    ]);
    setIsSending(true);
    const assistantMessageId = crypto.randomUUID();
    const pendingArtifacts: ArtifactBlock[] = [];
    const appendAssistantBlock = (block: ResponseBlock) => {
      setMessages((current) => {
        const assistantIndex = current.findIndex((item) => item.id === assistantMessageId);
        if (assistantIndex === -1) {
          return [...current, { id: assistantMessageId, role: "assistant", blocks: [block] }];
        }
        return current.map((item, index) =>
          index === assistantIndex ? { ...item, blocks: [...(item.blocks ?? []), block] } : item,
        );
      });
    };
    try {
      await streamMessage({ message: trimmed, conversation_id: activeConversationId }, (event) => {
        if (event.type === "message_start") {
          setActiveConversationId(event.payload.conversation_id);
        } else if (event.type === "status") {
          setActivity(event.payload.label);
        } else if (event.type === "markdown_delta") {
          setMessages((current) => {
            const assistantIndex = current.findIndex((item) => item.id === assistantMessageId);
            if (assistantIndex === -1) {
              return [
                ...current,
                {
                  id: assistantMessageId,
                  role: "assistant",
                  blocks: [{ type: "markdown", payload: { content: event.payload.delta } }],
                },
              ];
            }
            return current.map((item, index) => {
              if (index !== assistantIndex) return item;
              const blocks = [...(item.blocks ?? [])];
              const markdownIndex = blocks.findIndex((block) => block.type === "markdown");
              if (markdownIndex >= 0) {
                const markdown = blocks[markdownIndex];
                if (markdown?.type === "markdown") {
                  blocks[markdownIndex] = {
                    type: "markdown",
                    payload: { content: `${markdown.payload.content}${event.payload.delta}` },
                  };
                }
              } else
                blocks.unshift({ type: "markdown", payload: { content: event.payload.delta } });
              return { ...item, blocks };
            });
          });
        } else if (event.type === "artifact") {
          pendingArtifacts.push(event.payload);
        } else if (event.type === "complete") {
          pendingArtifacts.forEach(appendAssistantBlock);
        }
      });
      await refreshConversations();
    } catch (cause) {
      const apiError =
        cause instanceof ApiError
          ? cause
          : new ApiError("CurlChat could not answer that question.");
      setError(
        apiError.status === 404
          ? "This conversation is no longer available. Start a new one to continue."
          : apiError.message,
      );
    } finally {
      setIsSending(false);
      setActivity(undefined);
    }
  };

  const activeTitle = conversations.find(
    (conversation) => conversation.id === activeConversationId,
  )?.title;
  const isWelcome = messages.length === 0;

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <img src={logoUrl} alt="CurlChat" className="sidebar-logo" />
          <span>CurlChat</span>
        </div>
        <button className="new-chat" onClick={newConversation}>
          <span>＋</span> New conversation
        </button>
        <div className="conversation-heading">
          <span>Recent conversations</span>
          <button aria-label="Refresh conversations" onClick={() => void refreshConversations()}>
            ↻
          </button>
        </div>
        <nav className="conversation-list" aria-label="Recent conversations">
          {isLoadingConversations ? (
            <p className="sidebar-status">Loading conversations…</p>
          ) : conversations.length ? (
            conversations.map((conversation) => (
              <button
                className={
                  conversation.id === activeConversationId ? "conversation active" : "conversation"
                }
                key={conversation.id}
                onClick={() => void selectConversation(conversation.id)}
              >
                <span>{conversation.title}</span>
                <small>
                  {new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(
                    new Date(conversation.updated_at),
                  )}
                </small>
              </button>
            ))
          ) : (
            <p className="sidebar-status">Your conversations will appear here.</p>
          )}
        </nav>
        <div className="sidebar-foot">
          Curling Canada stats archive
          <br />
          AI-assisted analysis
        </div>
      </aside>

      <section className="chat-panel">
        <header className="chat-header">
          <div>
            <p>CONVERSATIONAL ANALYTICS</p>
            <h1>{activeTitle ?? "New conversation"}</h1>
          </div>
          <span className="status-dot">Archive connected</span>
        </header>
        <div className="messages" ref={messagesContainer}>
          {isLoadingHistory && <div className="history-loading">Loading conversation…</div>}
          {isWelcome && !isLoadingHistory && (
            <Welcome onPrompt={(prompt) => void submit(undefined, prompt)} />
          )}
          {messages.map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <div className="message-label">
                {message.role === "assistant" ? "CurlChat" : "You"}
              </div>
              {(message.content || message.blocks) && (
                <div className="message-card">
                  {message.content && <p>{message.content}</p>}
                  {message.blocks && <ResponseBlocks blocks={message.blocks} />}
                </div>
              )}
            </article>
          ))}
          {isSending && (
            <article className="message assistant thinking">
              <div className="message-label">CurlChat</div>
              <div className="message-card">
                <p className="thinking-status" aria-live="polite">
                  {activity ?? "Working…"}
                </p>
                <span></span>
                <span></span>
                <span></span>
              </div>
            </article>
          )}
          {error && (
            <div className="error-banner">
              <strong>Unable to complete the request.</strong> {error}
            </div>
          )}
        </div>
        <form className="composer" onSubmit={submit}>
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask about a player, event, season, or statistic…"
            rows={1}
            disabled={isSending || isLoadingHistory}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void submit();
              }
            }}
          />
          <button
            type="submit"
            disabled={isSending || isLoadingHistory || !draft.trim()}
            aria-label="Send message"
          >
            ↑
          </button>
        </form>
        <p className="composer-note">
          CurlChat uses the Curling Canada statistics archive. Results may include historical source
          records.
        </p>
      </section>
    </main>
  );
}

function Welcome({ onPrompt }: { onPrompt: (prompt: string) => void }) {
  return (
    <section className="welcome">
      <img src={logoUrl} alt="CurlChat — Curling stats. AI insights." className="welcome-logo" />
      <p>
        Explore historical player performance with natural language, interactive charts, and
        source-grounded statistics.
      </p>
      <div className="prompt-grid">
        {prompts.map((prompt) => (
          <button key={prompt} onClick={() => onPrompt(prompt)}>
            {prompt}
            <span>→</span>
          </button>
        ))}
      </div>
    </section>
  );
}
