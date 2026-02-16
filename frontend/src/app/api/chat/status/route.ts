import { NextRequest, NextResponse } from "next/server";

const AGENT_URL = process.env.A2A_AGENT_URL || "http://localhost:8001";

/**
 * Unwrap the REST response envelope.
 */
function unwrapResponse(data: Record<string, unknown>): Record<string, unknown> {
  if (data.task && typeof data.task === "object") {
    return data.task as Record<string, unknown>;
  }
  return data;
}

/**
 * GET /api/chat/status?taskId=xxx — Thin proxy for polling task status.
 *
 * Each call is a single GET to the backend, responds immediately.
 * Client-side polling with exponential backoff calls this endpoint.
 */
export async function GET(request: NextRequest) {
  const taskId = request.nextUrl.searchParams.get("taskId");

  if (!taskId) {
    return NextResponse.json(
      { error: "Missing 'taskId' query parameter" },
      { status: 400 }
    );
  }

  try {
    const pollRes = await fetch(`${AGENT_URL}/v1/tasks/${taskId}`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!pollRes.ok) {
      const errorText = await pollRes.text();
      return NextResponse.json(
        { error: `Backend error: ${pollRes.status}` },
        { status: pollRes.status }
      );
    }

    const pollData = await pollRes.json();
    const task = unwrapResponse(pollData);

    return NextResponse.json({ result: task });
  } catch (err) {
    const errMsg = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json(
      { error: { code: -32603, message: `Proxy error: ${errMsg}` } },
      { status: 500 }
    );
  }
}
