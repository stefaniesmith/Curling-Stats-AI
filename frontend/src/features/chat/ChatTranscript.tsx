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
  const latestResponse = useRef<HTMLElement>(null);
  const wasSending = useRef(false);
  const previousMessageCount = useRef(messages.length);
  const isWelcome = messages.length === 0;
  const latestUserIndex = messages.reduce(
    (lastUserIndex, message, index) => (message.role === "user" ? index : lastUserIndex),
    -1,
  );
  const latestResponseId = messages
    .slice(latestUserIndex + 1)
    .find((message) => message.role === "assistant")?.id;

  useEffect(() => {
    const transcript = messagesContainer.current;
    const requestStarted = isSending && !wasSending.current;
    const requestCompleted = !isSending && wasSending.current;

    if (transcript && requestStarted) {
      transcript.scrollTo({ top: transcript.scrollHeight, behavior: "smooth" });
    } else if (transcript && requestCompleted && latestResponse.current) {
      const transcriptBounds = transcript.getBoundingClientRect();
      const responseBounds = latestResponse.current.getBoundingClientRect();
      transcript.scrollTo({
        top: Math.max(0, transcript.scrollTop + responseBounds.top - transcriptBounds.top - 12),
        behavior: "smooth",
      });
    } else if (transcript && !isSending && messages.length !== previousMessageCount.current) {
      // Conversation history should still open at its most recent message.
      transcript.scrollTo({ top: transcript.scrollHeight, behavior: "auto" });
    }

    wasSending.current = isSending;
    previousMessageCount.current = messages.length;
  }, [isSending, messages.length]);

  return (
    <div className="messages" ref={messagesContainer}>
      {isLoadingHistory && <div className="history-loading">Loading conversation…</div>}
      {isWelcome && !isLoadingHistory && <Welcome onPrompt={onPrompt} />}
      {messages.map((message) => (
        <article
          className={`message ${message.role}`}
          key={message.id}
          ref={message.id === latestResponseId ? latestResponse : undefined}
        >
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
