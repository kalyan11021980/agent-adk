"use client";

import { useChat } from "@/hooks/use-chat";
import { MedicalDisclaimer } from "@/components/ui/MedicalDisclaimer";
import { ChatMessageList } from "./ChatMessageList";
import { ChatInput } from "./ChatInput";

export function ChatContainer() {
  const { messages, isLoading, sendMessage } = useChat();

  return (
    <div className="flex h-screen flex-col bg-medical-bg">
      {/* Header */}
      <header className="border-b border-medical-border bg-white px-4 py-3 shadow-sm">
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          <span className="text-2xl">&#129658;</span>
          <div>
            <h1 className="text-lg font-semibold text-medical-text">
              Health AI
            </h1>
            <p className="text-xs text-medical-muted">
              AI-powered health assistant
            </p>
          </div>
        </div>
      </header>

      {/* Disclaimer */}
      <div className="mx-auto w-full max-w-3xl px-4 pt-3">
        <MedicalDisclaimer />
      </div>

      {/* Messages */}
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col overflow-hidden">
        <ChatMessageList messages={messages} />
      </div>

      {/* Input */}
      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}
