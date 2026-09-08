import { useEffect, useRef } from "react";

import { ResponseBlocks } from "../visualizations/ResponseBlocks";
import type { ChatMessage } from "./types";
import { Welcome } from "./Welcome";

interface ChatTranscriptProps {
  activity?: string;
  error?: string;
  isLoadingHistory: boolean;
  isSending: boolean;
  messages: ChatMessage[];
  onPrompt: (prompt: string) => void;
}

export function ChatTranscript({
  activity,
  error,
  isLoadingHistory,
  isSending,
  messages,
  onPrompt,
}: ChatTranscriptProps) {
  const messagesContainer = useRef<HTMLDivElement>(null);
  const isWelcome = messages.length === 0;

  useEffect(() => {
    const transcript = messagesContainer.current;
    if (transcript) {
      transcript.scrollTo({ top: transcript.scrollHeight, behavior: "smooth" });
    }
  }, [messages, isSending]);

  return (
    <div className="messages" ref={messagesContainer}>
      {isLoadingHistory && <div className="history-loading">Loading conversation…</div>}
      {isWelcome && !isLoadingHistory && <Welcome onPrompt={onPrompt} />}
      {messages.map((message) => (
        <article className={`message ${message.role}`} key={message.id}>
          <div className="message-label">{message.role === "assistant" ? "CurlChat" : "You"}</div>
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
            <span />
            <span />
            <span />
          </div>
        </article>
      )}
      {error && (
        <div className="error-banner">
          <strong>Unable to complete the request.</strong> {error}
        </div>
      )}
    </div>
  );
}
