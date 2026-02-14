import { KNOWN_COMPONENT_TYPES, normalizeComponentType } from "./constants";
import type { A2AResponse, HealthCard, CardError } from "./types";

/* eslint-disable @typescript-eslint/no-explicit-any */

/**
 * Parse an A2A response and extract the display text + optional card.
 *
 * Extraction priority (first match wins for card):
 * 1. DataPart with ADK `function_response` metadata → card from tool result
 * 2. DataPart with known `component_type` directly
 * 3. JSON code block embedded in TextPart content
 * 4. Outermost `{...}` JSON in TextPart content
 *
 * Handles both Pydantic (parts/kind) and protobuf/REST (content/text)
 * serialization formats, as well as the `{root: ...}` wrapper pattern.
 */
export function parseA2AResponse(response: A2AResponse): {
  text: string;
  card?: HealthCard;
} {
  if (response.error) {
    const errCard: CardError = {
      component_type: "error",
      error: true,
      message: response.error.message,
    };
    return { text: response.error.message, card: errCard };
  }

  if (!response.result) {
    return { text: "No response from agent." };
  }

  const result = response.result as any;

  // Collect all parts from every possible location in the response
  const allParts = collectParts(result);

  // Deduplicate parts by content fingerprint
  const seen = new Set<string>();
  const uniqueParts: any[] = [];
  for (const part of allParts) {
    const key = partFingerprint(part);
    if (!seen.has(key)) {
      seen.add(key);
      uniqueParts.push(part);
    }
  }

  // Extract text and card from parts
  const texts: string[] = [];
  let card: HealthCard | undefined;

  for (const part of uniqueParts) {
    // 1. Try function_response DataPart (highest priority — direct tool result)
    if (!card) {
      const fnResult = extractFunctionResponseCard(part);
      if (fnResult) card = fnResult;
    }

    // 2. Try plain DataPart with component_type
    if (!card) {
      const partData = getPartData(part);
      if (partData && isKnownCard(partData)) {
        card = normalizeCard(partData);
      }
    }

    // Collect text parts for display
    const partText = getPartText(part);
    if (partText) texts.push(partText);

    // 3. Try extracting card JSON from text content (fallback)
    if (!card && partText) {
      card = extractJsonFromText(partText);
    }
  }

  // If we found a card, strip the JSON code block from display text
  let text = texts.join("\n");
  if (card) {
    text = stripCodeBlocks(text).trim();
  }

  // Handle tool error status — convert to ErrorCard
  if (card && (card as any).status === "error") {
    const errMsg = (card as any).error_message ?? "An error occurred.";
    card = {
      component_type: "error",
      error: true,
      message: errMsg,
    } as CardError;
    if (!text) text = errMsg;
  }

  return { text: text || (card ? "" : "Agent responded."), card };
}

/* ── Part collection ───────────────────────────────────────────────────── */

/** Collect parts from all possible locations in a Task or Message result. */
function collectParts(result: any): any[] {
  const parts: any[] = [];

  // 1. Artifacts (most reliable location for final response data)
  if (Array.isArray(result.artifacts)) {
    for (const artifact of result.artifacts) {
      if (Array.isArray(artifact.parts)) parts.push(...artifact.parts);
      if (Array.isArray(artifact.content)) parts.push(...artifact.content);
    }
  }

  // 2. Status message — Pydantic uses "parts", protobuf uses "content"
  const statusMsg = result.status?.message;
  if (statusMsg) {
    if (Array.isArray(statusMsg.parts)) parts.push(...statusMsg.parts);
    if (Array.isArray(statusMsg.content)) parts.push(...statusMsg.content);
    if (typeof statusMsg === "string") parts.push({ text: statusMsg });
  }

  // 3. History — only agent messages
  if (Array.isArray(result.history)) {
    for (const msg of result.history) {
      const isAgent = msg.role === "agent" || msg.role === "ROLE_AGENT";
      if (isAgent) {
        if (Array.isArray(msg.parts)) parts.push(...msg.parts);
        if (Array.isArray(msg.content)) parts.push(...msg.content);
      }
    }
  }

  // 4. Direct parts/content (Message shape)
  if (Array.isArray(result.parts)) parts.push(...result.parts);
  if (Array.isArray(result.content)) parts.push(...result.content);

  return parts;
}

/* ── Part accessors (handle multiple serialization formats) ────────────── */

function getPartText(part: any): string | undefined {
  if (!part || typeof part !== "object") return undefined;
  const p = part.root ?? part;

  // Skip non-text parts (function_call/response DataParts)
  if (isFunctionPart(p)) return undefined;

  // Pydantic: {kind: "text", text: "..."}
  if (p.kind === "text" && typeof p.text === "string") return p.text;
  // REST/protobuf: {text: "..."} (direct string)
  if (typeof p.text === "string") return p.text;
  // REST/protobuf nested: {text: {text: "..."}}
  if (p.text && typeof p.text === "object" && typeof p.text.text === "string")
    return p.text.text;

  return undefined;
}

function getPartData(part: any): Record<string, unknown> | undefined {
  if (!part || typeof part !== "object") return undefined;
  const p = part.root ?? part;

  // Pydantic DataPart: {kind: "data", data: {...}}
  if (p.kind === "data" && p.data && typeof p.data === "object") return p.data;
  // REST DataPart: {data: {...}} without text/file fields
  if (p.data && typeof p.data === "object" && !p.text && !p.file) return p.data;
  // Nested: {data: {data: {...}}}
  if (p.data?.data && typeof p.data.data === "object") return p.data.data;

  return undefined;
}

/**
 * Extract card data from an ADK function_response DataPart.
 *
 * REST transport serializes tool results as:
 *   { data: { data: { name: "tool_name", response: {...tool_dict...} } },
 *     metadata: { "adk_type": "function_response" } }
 *
 * The actual card dict (with component_type) is in `data.data.response`.
 */
function extractFunctionResponseCard(part: any): HealthCard | undefined {
  if (!part || typeof part !== "object") return undefined;
  const p = part.root ?? part;

  if (!isAdkFunctionResponse(p)) return undefined;

  // Walk through all nesting levels to find `response` containing a card.
  // REST transport double-nests: data.data.response
  // Pydantic may use: data.response
  const candidates = [
    p.data?.data?.response, // REST/protobuf: { data: { data: { response: {...} } } }
    p.data?.response,       // Pydantic: { data: { response: {...} } }
    p.data?.data,           // Flat variant: { data: { data: {...card...} } }
    p.data,                 // Direct: { data: {...card...} }
  ];

  for (const candidate of candidates) {
    if (candidate && typeof candidate === "object" && isKnownCard(candidate)) {
      return normalizeCard(candidate as Record<string, unknown>);
    }
  }

  return undefined;
}

/** Get the ADK type from part metadata (handles all known key variants). */
function getAdkType(p: any): string | undefined {
  const meta = p.metadata;
  if (!meta || typeof meta !== "object") return undefined;
  // REST uses "adk_type", Pydantic uses "adk:type", fallback to "type"
  return meta["adk_type"] ?? meta["adk:type"] ?? meta["type"];
}

/** Check if a part is an ADK function_response DataPart. */
function isAdkFunctionResponse(p: any): boolean {
  return getAdkType(p) === "function_response";
}

/** Check if a part is an ADK function_call or function_response DataPart. */
function isFunctionPart(p: any): boolean {
  const adkType = getAdkType(p);
  return (
    adkType === "function_call" ||
    adkType === "function_response" ||
    adkType === "executable_code" ||
    adkType === "code_execution_result"
  );
}

/* ── Helpers ────────────────────────────────────────────────────────────── */

/** Stable fingerprint for deduplication. */
function partFingerprint(part: any): string {
  const text = getPartText(part);
  if (text) return `text:${text}`;
  return JSON.stringify(part);
}

function isKnownCard(data: Record<string, unknown>): boolean {
  return (
    typeof data.component_type === "string" &&
    (KNOWN_COMPONENT_TYPES as readonly string[]).includes(data.component_type)
  );
}

/** Normalize component_type to the canonical _card form. */
function normalizeCard(data: Record<string, unknown>): HealthCard {
  const normalized = { ...data };
  if (typeof normalized.component_type === "string") {
    normalized.component_type = normalizeComponentType(
      normalized.component_type as string
    );
  }
  return normalized as unknown as HealthCard;
}

function extractJsonFromText(text: string): HealthCard | undefined {
  // Try markdown code blocks first
  const codeBlockRe = /```(?:json)?\s*([\s\S]*?)```/g;
  let match: RegExpExecArray | null;
  while ((match = codeBlockRe.exec(text)) !== null) {
    const card = tryParseCard(match[1].trim());
    if (card) return card;
  }

  // Fall back to outermost { ... }
  const braceStart = text.indexOf("{");
  const braceEnd = text.lastIndexOf("}");
  if (braceStart !== -1 && braceEnd > braceStart) {
    const card = tryParseCard(text.slice(braceStart, braceEnd + 1));
    if (card) return card;
  }

  return undefined;
}

function tryParseCard(raw: string): HealthCard | undefined {
  try {
    const obj = JSON.parse(raw);
    if (!obj || typeof obj !== "object") return undefined;

    // Direct match — card at top level
    if (isKnownCard(obj)) {
      return normalizeCard(obj);
    }

    // LLM sometimes wraps the card in {"tool_name_response": {...card...}}
    // e.g. {"get_visit_summary_response": {...}}
    const values = Object.values(obj);
    if (values.length === 1) {
      const inner = values[0];
      if (inner && typeof inner === "object" && isKnownCard(inner as Record<string, unknown>)) {
        return normalizeCard(inner as Record<string, unknown>);
      }
    }
  } catch {
    // not valid JSON
  }
  return undefined;
}

/** Remove markdown code blocks from text so we don't show raw JSON. */
function stripCodeBlocks(text: string): string {
  return text.replace(/```(?:json)?\s*[\s\S]*?```/g, "").trim();
}
