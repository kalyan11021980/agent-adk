import { NextRequest, NextResponse } from "next/server";

const AGENT_URL = process.env.A2A_AGENT_URL || "http://localhost:8001";

/**
 * Unwrap the REST response envelope.
 *
 * The REST transport wraps the result in either {"task": {...}} or
 * {"message": {...}}. This function returns the inner object.
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

/**
 * POST /api/chat — Send a message to the A2A agent.
 *
 * Returns the task immediately (with taskId + initial state) so the
 * client can start polling. Does NOT hold the connection open.
 */
export async function POST(request: NextRequest) {
  try {
    const { message, contextId } = await request.json();

    if (!message || typeof message !== "string") {
      return NextResponse.json(
        { error: "Missing or invalid 'message' field" },
        { status: 400 }
      );
    }

    const messageId = `msg-${Date.now()}`;

    const a2aMessage: Record<string, unknown> = {
      role: "ROLE_USER",
      content: [{ text: message }],
      messageId,
    };
    if (contextId) {
      a2aMessage.contextId = contextId;
    }

    const sendRes = await fetch(`${AGENT_URL}/v1/message:send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: a2aMessage }),
    });

    if (!sendRes.ok) {
      const errorText = await sendRes.text();
      console.error("[chat proxy] message:send error:", sendRes.status, errorText);
      return NextResponse.json(
        { error: `Agent error: ${sendRes.status} — ${errorText}` },
        { status: 502 }
      );
    }

    const sendData = await sendRes.json();
    const task = unwrapResponse(sendData);

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
