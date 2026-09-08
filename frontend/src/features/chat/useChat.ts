import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  getConversationMessages,
  isRequestAborted,
  listConversations,
  streamMessage,
} from "../../lib/api";
import type { ArtifactBlock, Conversation, ResponseBlock } from "../../types/api";
import type { ChatMessage } from "./types";

export function useChat() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);
  const [activity, setActivity] = useState<string>();
  const [error, setError] = useState<string>();
  const [composerKey, setComposerKey] = useState(0);
  const viewVersion = useRef(0);
  const historyController = useRef<AbortController>();
  const streamController = useRef<AbortController>();

  const refreshConversations = useCallback(async () => {
    setIsLoadingConversations(true);
    try {
      setConversations(await listConversations());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load conversations.");
    } finally {
      setIsLoadingConversations(false);
    }
  }, []);

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  useEffect(
    () => () => {
      historyController.current?.abort();
      streamController.current?.abort();
    },
    [],
  );

  const invalidateCurrentView = useCallback(() => {
    viewVersion.current += 1;
    historyController.current?.abort();
    streamController.current?.abort();
  }, []);

  const newConversation = useCallback(() => {
    invalidateCurrentView();
    setActiveConversationId(undefined);
    setMessages([]);
    setError(undefined);
    setActivity(undefined);
    setIsSending(false);
    setIsLoadingHistory(false);
    setComposerKey((current) => current + 1);
  }, [invalidateCurrentView]);

  const selectConversation = useCallback(
    async (id: string) => {
      invalidateCurrentView();
      const version = viewVersion.current;
      const controller = new AbortController();
      historyController.current = controller;
      setActiveConversationId(id);
      setMessages([]);
      setError(undefined);
      setActivity(undefined);
      setIsSending(false);
      setIsLoadingHistory(true);
      try {
        const history = await getConversationMessages(id, controller.signal);
        if (version !== viewVersion.current) return;
        setMessages(
          history.map((message) => ({
            id: crypto.randomUUID(),
            role: message.role,
            content: message.role === "user" ? message.content : undefined,
            blocks: message.role === "assistant" ? message.blocks : undefined,
          })),
        );
      } catch (cause) {
        if (isRequestAborted(cause) || version !== viewVersion.current) return;
        const apiError =
          cause instanceof ApiError ? cause : new ApiError("Could not load this conversation.");
        setError(
          apiError.status === 404
            ? "This conversation is no longer available. Start a new one to continue."
            : apiError.message,
        );
      } finally {
        if (version === viewVersion.current) setIsLoadingHistory(false);
      }
    },
    [invalidateCurrentView],
  );

  const sendMessage = useCallback(
    async (message: string) => {
      const trimmed = message.trim();
      if (!trimmed || isSending) return;
      const version = viewVersion.current;
      const controller = new AbortController();
      streamController.current = controller;
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
        if (version !== viewVersion.current) return;
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
        await streamMessage(
          { message: trimmed, conversation_id: activeConversationId },
          (event) => {
            if (version !== viewVersion.current) return;
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
                  const markdown = blocks[markdownIndex];
                  if (markdown?.type === "markdown") {
                    blocks[markdownIndex] = {
                      type: "markdown",
                      payload: { content: `${markdown.payload.content}${event.payload.delta}` },
                    };
                  } else {
                    blocks.unshift({ type: "markdown", payload: { content: event.payload.delta } });
                  }
                  return { ...item, blocks };
                });
              });
            } else if (event.type === "artifact") {
              pendingArtifacts.push(event.payload);
            } else if (event.type === "complete") {
              pendingArtifacts.forEach(appendAssistantBlock);
            }
          },
          controller.signal,
        );
        if (version === viewVersion.current) await refreshConversations();
      } catch (cause) {
        if (isRequestAborted(cause) || version !== viewVersion.current) return;
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
        if (version === viewVersion.current) {
          setIsSending(false);
          setActivity(undefined);
        }
      }
    },
    [activeConversationId, isSending, refreshConversations],
  );

  return {
    activeConversationId,
    activity,
    composerKey,
    conversations,
    error,
    isLoadingConversations,
    isLoadingHistory,
    isSending,
    messages,
    newConversation,
    refreshConversations,
    selectConversation,
    sendMessage,
  };
}
