import type { ChatMessage as ChatMessageType } from "@/lib/types";
import { CardRenderer } from "@/components/cards/CardRenderer";
import { TypingIndicator } from "./TypingIndicator";
import { cn } from "@/lib/utils";
import Markdown from "react-markdown";

interface Props {
  message: ChatMessageType;
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={cn(
          "max-w-[85%] space-y-3",
          isUser ? "items-end" : "items-start"
        )}
      >
        {/* Text bubble */}
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            isUser
              ? "bg-teal-600 text-white rounded-br-md"
              : "bg-white border border-medical-border text-medical-text rounded-bl-md shadow-sm"
          )}
        >
          {message.isLoading ? (
            <TypingIndicator />
          ) : isUser ? (
            <p className="whitespace-pre-wrap">{message.text}</p>
          ) : (
            <div className="prose prose-sm max-w-none prose-headings:text-medical-text prose-headings:font-semibold prose-h3:text-base prose-h3:mt-4 prose-h3:mb-2 prose-p:my-1.5 prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5 prose-strong:text-teal-700 prose-hr:my-3 prose-hr:border-medical-border">
              <Markdown>{message.text}</Markdown>
            </div>
          )}
        </div>

        {/* Card (agent only) */}
        {!isUser && message.card && !message.isLoading && (
          <div className="mt-2 w-full">
            <CardRenderer card={message.card} />
          </div>
        )}
      </div>
    </div>
  );
}
