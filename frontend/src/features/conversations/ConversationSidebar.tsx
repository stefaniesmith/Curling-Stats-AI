import logoUrl from "../../../../assets/CurlChatLogo.png";
import { useEffect, useRef } from "react";
import type { Conversation } from "../../types/api";

interface ConversationSidebarProps {
  activeConversationId?: string;
  conversations: Conversation[];
  isLoading: boolean;
  isOpen: boolean;
  onClose: () => void;
  onNewConversation: () => void;
  onRefresh: () => void;
  onSelectConversation: (id: string) => void;
}

const dateFormatter = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });

export function ConversationSidebar({
  activeConversationId,
  conversations,
  isLoading,
  isOpen,
  onClose,
  onNewConversation,
  onRefresh,
  onSelectConversation,
}: ConversationSidebarProps) {
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (isOpen) closeButton.current?.focus();
  }, [isOpen]);

  return (
    <aside
      aria-label="Conversation navigation"
      className={isOpen ? "sidebar sidebar-open" : "sidebar"}
      id="conversation-sidebar"
    >
      <div className="brand-row">
        <img src={logoUrl} alt="CurlChat" className="sidebar-logo" />
        <span>CurlChat</span>
        <button
          aria-label="Close conversations"
          className="sidebar-close"
          onClick={onClose}
          ref={closeButton}
        >
          ×
        </button>
      </div>
      <button className="new-chat" onClick={onNewConversation}>
        <span>＋</span> New conversation
      </button>
      <div className="conversation-heading">
        <span>Recent conversations</span>
        <button aria-label="Refresh conversations" onClick={onRefresh}>
          ↻
        </button>
      </div>
      <nav className="conversation-list" aria-label="Recent conversations">
        {isLoading ? (
          <p className="sidebar-status">Loading conversations…</p>
        ) : conversations.length ? (
          conversations.map((conversation) => (
            <button
              className={
                conversation.id === activeConversationId ? "conversation active" : "conversation"
              }
              key={conversation.id}
              onClick={() => onSelectConversation(conversation.id)}
            >
              <span>{conversation.title}</span>
              <small>{dateFormatter.format(new Date(conversation.updated_at))}</small>
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
  );
}
