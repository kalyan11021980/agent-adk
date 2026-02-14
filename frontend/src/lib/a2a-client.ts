import type { A2AResponse } from "./types";

/**
 * Send a chat message to the A2A agent via the /api/chat proxy.
 */
export async function sendMessage(text: string): Promise<A2AResponse> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text }),
  });

  if (!res.ok) {
    throw new Error(`Agent request failed: ${res.status} ${res.statusText}`);
  }

  return res.json();
}
