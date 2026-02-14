"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage as ChatMessageType } from "@/lib/types";
import { ChatMessage } from "./ChatMessage";

interface Props {
  messages: ChatMessageType[];
}

export function ChatMessageList({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-center">
        <div className="space-y-2">
          <p className="text-2xl">&#129658;</p>
          <p className="text-base font-medium text-medical-text">
            Health AI Assistant
          </p>
          <p className="text-sm text-medical-muted">
            Ask about visit summaries, symptoms, or lab results.
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2 text-xs">
            <span className="rounded-full bg-teal-50 border border-teal-200 px-3 py-1 text-teal-700">
              &quot;Show visit summary for P001&quot;
            </span>
            <span className="rounded-full bg-teal-50 border border-teal-200 px-3 py-1 text-teal-700">
              &quot;I have a headache and fever&quot;
            </span>
            <span className="rounded-full bg-teal-50 border border-teal-200 px-3 py-1 text-teal-700">
              &quot;Show my lab results&quot;
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
      {messages.map((msg) => (
        <ChatMessage key={msg.id} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
