"use client";

import { useState, useCallback, type KeyboardEvent } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }, [value, disabled, onSend]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-medical-border bg-white px-4 py-3">
      <div className="mx-auto flex max-w-3xl items-end gap-3">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about visits, symptoms, or lab results..."
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none rounded-xl border border-medical-border bg-medical-bg px-4 py-2.5 text-sm text-medical-text placeholder:text-medical-muted focus:border-teal-400 focus:outline-none focus:ring-2 focus:ring-teal-100 disabled:opacity-50"
        />
        <button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-teal-600 text-white transition-colors hover:bg-teal-700 disabled:opacity-40 disabled:cursor-not-allowed"
          aria-label="Send message"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="h-5 w-5"
          >
            <path d="M3.105 2.29a.75.75 0 0 0-.826.95l1.414 4.926A1.5 1.5 0 0 0 5.135 9.25h6.115a.75.75 0 0 1 0 1.5H5.135a1.5 1.5 0 0 0-1.442 1.084L2.28 16.76a.75.75 0 0 0 .826.95l15-4.5a.75.75 0 0 0 0-1.42l-15-4.5Z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
