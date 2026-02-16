"use client";

import { useCallback, useReducer, useRef } from "react";
import { sendMessage as sendA2AMessage } from "@/lib/a2a-client";
import { parseA2AResponse } from "@/lib/json-extractor";
import type { ChatAction, ChatMessage, ChatState } from "@/lib/types";

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

const PLACEHOLDER_ID = "__agent_placeholder__";

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "ADD_USER_MESSAGE":
      return {
        ...state,
        isLoading: true,
        messages: [
          ...state.messages,
          {
            id: generateId(),
            role: "user",
            text: action.text,
            timestamp: Date.now(),
          },
        ],
      };

    case "ADD_AGENT_PLACEHOLDER":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: PLACEHOLDER_ID,
            role: "agent",
            text: "",
            timestamp: Date.now(),
            isLoading: true,
          },
        ],
      };

    case "RESOLVE_AGENT_MESSAGE":
      return {
        ...state,
        isLoading: false,
        contextId: action.contextId ?? state.contextId,
        messages: state.messages.map((m) =>
          m.id === PLACEHOLDER_ID
            ? {
                ...m,
                id: generateId(),
                text: action.text,
                card: action.card,
                isLoading: false,
              }
            : m
        ),
      };

    case "REJECT_AGENT_MESSAGE":
      return {
        ...state,
        isLoading: false,
        messages: state.messages.map((m) =>
          m.id === PLACEHOLDER_ID
            ? {
                ...m,
                id: generateId(),
                text: action.error,
                card: {
                  component_type: "error",
                  error: true,
                  message: action.error,
                },
                isLoading: false,
              }
            : m
        ),
      };

    default:
      return state;
  }
}

const initialState: ChatState = {
  messages: [],
  isLoading: false,
};

export function useChat() {
  const [state, dispatch] = useReducer(chatReducer, initialState);

  // Use a ref for contextId to avoid stale closures in sendMessage.
  // The ref is updated synchronously when RESOLVE_AGENT_MESSAGE fires,
  // so rapid sequential sends always read the latest value.
  const contextIdRef = useRef<string | undefined>(state.contextId);
  contextIdRef.current = state.contextId;

  const sendMessage = useCallback(async (text: string) => {
    dispatch({ type: "ADD_USER_MESSAGE", text });
    dispatch({ type: "ADD_AGENT_PLACEHOLDER" });

    try {
      const response = await sendA2AMessage(text, contextIdRef.current);
      const { text: agentText, card } = parseA2AResponse(response);
      const contextId = response.result?.contextId as string | undefined;
      dispatch({ type: "RESOLVE_AGENT_MESSAGE", text: agentText, card, contextId });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to reach agent";
      dispatch({ type: "REJECT_AGENT_MESSAGE", error: message });
    }
  }, []);

  return {
    messages: state.messages,
    isLoading: state.isLoading,
    sendMessage,
  };
}
