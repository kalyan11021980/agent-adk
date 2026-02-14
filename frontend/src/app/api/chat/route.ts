import { NextRequest, NextResponse } from "next/server";

const AGENT_URL = process.env.A2A_AGENT_URL || "http://localhost:8001";
const POLL_INTERVAL_MS = 500;
const MAX_POLL_ATTEMPTS = 60; // 30 seconds max

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

/**
 * Unwrap the REST response envelope.
 *
 * The REST transport (MessageToDict on a SendMessageResponse) wraps
 * the result in either {"task": {...}} or {"message": {...}}.
 * This function returns the inner object.
 */
function unwrapResponse(data: Record<string, unknown>): Record<string, unknown> {
  if (data.task && typeof data.task === "object") {
    return data.task as Record<string, unknown>;
  }
  if (data.message && typeof data.message === "object") {
    return data.message as Record<string, unknown>;
  }
  return data;
}

export async function POST(request: NextRequest) {
  try {
    const { message } = await request.json();

    if (!message || typeof message !== "string") {
      return NextResponse.json(
        { error: "Missing or invalid 'message' field" },
        { status: 400 }
      );
    }

    const messageId = `msg-${Date.now()}`;

    // 1. Send message via HTTP/REST transport → POST /v1/message:send
    const sendRes = await fetch(`${AGENT_URL}/v1/message:send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: {
          role: "ROLE_USER",
          content: [{ text: message }],
          messageId,
        },
      }),
    });

    if (!sendRes.ok) {
      const errorText = await sendRes.text();
      console.error("[chat proxy] message:send error:", sendRes.status, errorText);
      return NextResponse.json(
        { error: `Agent error: ${sendRes.status} — ${errorText}` },
        { status: 502 }
      );
    }

    // Unwrap: REST returns {"task": {...}} or {"message": {...}}
    const sendData = await sendRes.json();
    let task = unwrapResponse(sendData);
    const taskId = task.id as string | undefined;
    const taskState = task.status
      ? (task.status as Record<string, unknown>).state as string
      : undefined;

    console.log(
      `[chat proxy] POST /v1/message:send → task ${taskId} state=${taskState}`
    );

    // 2. If not terminal, poll GET /v1/tasks/{id} until complete
    if (taskId && taskState && !TERMINAL_STATES.has(taskState)) {
      for (let i = 0; i < MAX_POLL_ATTEMPTS; i++) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));

        const pollRes = await fetch(`${AGENT_URL}/v1/tasks/${taskId}`, {
          method: "GET",
          headers: { Accept: "application/json" },
        });

        if (!pollRes.ok) {
          const errorText = await pollRes.text();
          console.error("[chat proxy] poll error:", pollRes.status, errorText);
          break;
        }

        // GET /v1/tasks/{id} also returns {"task": {...}} envelope
        const pollData = await pollRes.json();
        task = unwrapResponse(pollData);
        const state = task.status
          ? (task.status as Record<string, unknown>).state as string
          : undefined;

        console.log(
          `[chat proxy] poll ${i + 1}: task ${taskId} state=${state}`
        );

        if (state && TERMINAL_STATES.has(state)) break;
      }
    }

    console.log(
      "[chat proxy] final task:",
      JSON.stringify(task, null, 2)
    );

    // 3. Return unwrapped task for frontend parser
    return NextResponse.json({ result: task });
  } catch (err) {
    const errMsg = err instanceof Error ? err.message : "Unknown error";
    console.error("[chat proxy] exception:", errMsg);
    return NextResponse.json(
      { error: { code: -32603, message: `Proxy error: ${errMsg}` } },
      { status: 500 }
    );
  }
}
