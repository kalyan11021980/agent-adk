import type { A2AResponse } from "./types";

/** Terminal task states — handles both Pydantic and protobuf enum formats. */
const TERMINAL_STATES = new Set([
  "completed",
  "failed",
  "canceled",
  "rejected",
  "TASK_STATE_COMPLETED",
  "TASK_STATE_FAILED",
  "TASK_STATE_CANCELED",
  "TASK_STATE_REJECTED",
]);

/** Exponential backoff config */
const INITIAL_DELAY_MS = 1000;
const MAX_DELAY_MS = 8000;
const MAX_POLL_DURATION_MS = 120_000; // 2 minute hard cap

/**
 * Send a chat message to the A2A agent via the /api/chat proxy.
 *
 * 1. POST /api/chat — fires the message, returns immediately with taskId
 * 2. Poll GET /api/chat/status?taskId=xxx with exponential backoff
 *    until task reaches a terminal state.
 *
 * Each individual request is fast (<1s), safe for Apigee's 10s timeout.
 */
export async function sendMessage(text: string, contextId?: string): Promise<A2AResponse> {
  // 1. Send the message
  const sendRes = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text, contextId }),
  });

  if (!sendRes.ok) {
    throw new Error(`Agent request failed: ${sendRes.status} ${sendRes.statusText}`);
  }

  const sendData: A2AResponse = await sendRes.json();
  const taskId = sendData.result?.id;
  const initialState = sendData.result?.status?.state;

  // If already terminal (unlikely but possible), return immediately
  if (!taskId || (initialState && TERMINAL_STATES.has(initialState))) {
    return sendData;
  }

  // 2. Poll with exponential backoff
  let delay = INITIAL_DELAY_MS;
  const startTime = Date.now();

  while (Date.now() - startTime < MAX_POLL_DURATION_MS) {
    await new Promise((r) => setTimeout(r, delay));

    const pollRes = await fetch(`/api/chat/status?taskId=${taskId}`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!pollRes.ok) {
      throw new Error(`Poll failed: ${pollRes.status} ${pollRes.statusText}`);
    }

    const pollData: A2AResponse = await pollRes.json();
    const state = pollData.result?.status?.state;

    if (state && TERMINAL_STATES.has(state)) {
      return pollData;
    }

    // Exponential backoff: 1s → 2s → 4s → 8s (capped)
    delay = Math.min(delay * 2, MAX_DELAY_MS);
  }

  // Timed out — return last known state
  return sendData;
}
