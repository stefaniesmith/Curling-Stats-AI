import { MessageComposer } from "../features/chat/MessageComposer";
import { ChatTranscript } from "../features/chat/ChatTranscript";
import { useChat } from "../features/chat/useChat";
import { ConversationSidebar } from "../features/conversations/ConversationSidebar";

export function App() {
  const chat = useChat();
  const activeTitle = chat.conversations.find(
    (conversation) => conversation.id === chat.activeConversationId,
  )?.title;

  return (
    <main className="app-shell">
      <ConversationSidebar
        activeConversationId={chat.activeConversationId}
        conversations={chat.conversations}
        isLoading={chat.isLoadingConversations}
        onNewConversation={chat.newConversation}
        onRefresh={() => void chat.refreshConversations()}
        onSelectConversation={(id) => void chat.selectConversation(id)}
      />

      <section className="chat-panel">
        <header className="chat-header">
          <div>
            <p>CONVERSATIONAL ANALYTICS</p>
            <h1>{activeTitle ?? "New conversation"}</h1>
          </div>
          <span className="status-dot">Archive connected</span>
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
