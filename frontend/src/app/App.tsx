import { useCallback, useEffect, useRef, useState } from "react";

import { MessageComposer } from "../features/chat/MessageComposer";
import { ChatTranscript } from "../features/chat/ChatTranscript";
import { useChat } from "../features/chat/useChat";
import { ConversationSidebar } from "../features/conversations/ConversationSidebar";
import { preloadPlotly } from "../features/visualizations/plotly";

type IdleWindow = Window & {
  cancelIdleCallback?: (id: number) => void;
  requestIdleCallback?: (callback: () => void) => number;
};

export function App() {
  const chat = useChat();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const activeTitle = chat.conversations.find(
    (conversation) => conversation.id === chat.activeConversationId,
  )?.title;

  useEffect(() => {
    const browserWindow = window as IdleWindow;
    if (browserWindow.requestIdleCallback) {
      const callbackId = browserWindow.requestIdleCallback(preloadPlotly);
      return () => browserWindow.cancelIdleCallback?.(callbackId);
    }

    const timeoutId = window.setTimeout(preloadPlotly, 1_500);
    return () => window.clearTimeout(timeoutId);
  }, []);

  const closeSidebar = useCallback(() => {
    setIsSidebarOpen(false);
    if (isSidebarOpen) menuButton.current?.focus();
  }, [isSidebarOpen]);

  useEffect(() => {
    if (!isSidebarOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeSidebar();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [closeSidebar, isSidebarOpen]);

  return (
    <main className="app-shell">
      <button
        aria-label="Close conversations"
        className={isSidebarOpen ? "sidebar-backdrop sidebar-backdrop-open" : "sidebar-backdrop"}
        onClick={closeSidebar}
        tabIndex={isSidebarOpen ? 0 : -1}
      />
      <ConversationSidebar
        activeConversationId={chat.activeConversationId}
        conversations={chat.conversations}
        isLoading={chat.isLoadingConversations}
        isOpen={isSidebarOpen}
        onClose={closeSidebar}
        onNewConversation={() => {
          chat.newConversation();
          closeSidebar();
        }}
        onRefresh={() => void chat.refreshConversations()}
        onSelectConversation={(id) => {
          void chat.selectConversation(id);
          closeSidebar();
        }}
      />

      <section className="chat-panel">
        <header className="chat-header">
          <div>
            <p>CONVERSATIONAL ANALYTICS</p>
            <h1>{activeTitle ?? "New conversation"}</h1>
          </div>
          <div className="header-actions">
            <span className="status-dot">Archive connected</span>
            <button
              aria-controls="conversation-sidebar"
              aria-expanded={isSidebarOpen}
              aria-label="Open conversations"
              className="mobile-menu"
              onClick={() => setIsSidebarOpen(true)}
              ref={menuButton}
            >
              ☰
            </button>
          </div>
        </header>
        <ChatTranscript
          activity={chat.activity}
          error={chat.error}
          isLoadingHistory={chat.isLoadingHistory}
          isSending={chat.isSending}
          messages={chat.messages}
          onPrompt={(prompt) => void chat.sendMessage(prompt)}
        />
        <MessageComposer
          key={chat.composerKey}
          disabled={chat.isSending || chat.isLoadingHistory}
          onSend={(message) => void chat.sendMessage(message)}
        />
        <p className="composer-note">
          CurlChat uses the Curling Canada statistics archive. Results may include historical source
          records.
        </p>
      </section>
    </main>
  );
}
