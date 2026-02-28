import type { Candidate, FeedbackAction, FinalizeResult, JewelryCategory } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Session creation ───────────────────────────────────────────────────── //

export type CreateSessionResult = {
  session_id: string;
  user_id: string;
  round_number: number;
};

export async function createSession(
  file: File,
  userId: string,
  category?: JewelryCategory
): Promise<CreateSessionResult> {
  const form = new FormData();
  form.append("image", file);
  form.append("user_id", userId);
  if (category) form.append("category", category);

  const res = await fetch(`${API_URL}/v1/sessions`, { method: "POST", body: form });
  return handleResponse<CreateSessionResult>(res);
}

// ── SSE event types ────────────────────────────────────────────────────── //

export type CandidatesCreatedEvent = {
  session_id: string;
  round_number: number;
  candidates: Candidate[];
};

export type CandidateDoneEvent = {
  candidate_id: string;
  generation_status: "done" | "error";
  image_url: string | null;
  error: string | null;
  analysis_status: "pending" | "running" | "done" | "failed";
};

export type AnalysisDoneEvent = {
  candidate_id: string;
  analysis_status: "done" | "failed";
  image_analysis: Candidate["image_analysis"] | null;
};

export type RoundCompleteEvent = {
  session_id: string;
  round_number: number;
};

export type PipelineErrorEvent = {
  session_id: string;
  round_number: number;
  error: string;
};

// ── SSE stream ─────────────────────────────────────────────────────────── //

export function openCandidateStream(
  sessionId: string,
  handlers: {
    onCandidatesCreated?: (e: CandidatesCreatedEvent) => void;
    onCandidateDone: (e: CandidateDoneEvent) => void;
    onAnalysisDone: (e: AnalysisDoneEvent) => void;
    onRoundComplete: (e: RoundCompleteEvent) => void;
    onPipelineError?: (e: PipelineErrorEvent) => void;
    onError?: (err: Event) => void;
  }
): EventSource {
  const es = new EventSource(`${API_URL}/v1/sessions/${sessionId}/events`);

  if (handlers.onCandidatesCreated) {
    es.addEventListener("candidates_created", (e: MessageEvent) => {
      handlers.onCandidatesCreated!(JSON.parse(e.data) as CandidatesCreatedEvent);
    });
  }

  es.addEventListener("candidate_done", (e: MessageEvent) => {
    handlers.onCandidateDone(JSON.parse(e.data) as CandidateDoneEvent);
  });

  es.addEventListener("analysis_done", (e: MessageEvent) => {
    handlers.onAnalysisDone(JSON.parse(e.data) as AnalysisDoneEvent);
  });

  es.addEventListener("round_complete", (e: MessageEvent) => {
    handlers.onRoundComplete(JSON.parse(e.data) as RoundCompleteEvent);
    es.close();
  });

  if (handlers.onPipelineError) {
    es.addEventListener("pipeline_error", (e: MessageEvent) => {
      handlers.onPipelineError!(JSON.parse(e.data) as PipelineErrorEvent);
      es.close();
    });
  }

  if (handlers.onError) {
    es.onerror = handlers.onError;
  }

  return es;
}

// ── Feedback ───────────────────────────────────────────────────────────── //

export async function submitFeedback(
  sessionId: string,
  candidateId: string,
  action: FeedbackAction,
  reasonTags: string[],
  textNote?: string,
  chipDimensionMap?: Record<string, string[]>
): Promise<{ feedback_accepted: boolean; reward: number }> {
  const res = await fetch(`${API_URL}/v1/sessions/${sessionId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      candidate_id: candidateId,
      action,
      reason_tags: reasonTags,
      text_note: textNote ?? null,
      chip_dimension_map: chipDimensionMap ?? {},
    }),
  });
  return handleResponse(res);
}

// ── Next round ─────────────────────────────────────────────────────────── //

export async function nextRound(
  sessionId: string,
  force = false
): Promise<{ advanced: boolean; round_number: number }> {
  const res = await fetch(`${API_URL}/v1/sessions/${sessionId}/next-round`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ force }),
  });
  return handleResponse(res);
}

// ── Finalize ───────────────────────────────────────────────────────────── //

export async function finalizeSession(
  sessionId: string,
  selectedCandidateId: string
): Promise<FinalizeResult> {
  const res = await fetch(`${API_URL}/v1/sessions/${sessionId}/finalize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selected_candidate_id: selectedCandidateId }),
  });
  return handleResponse<FinalizeResult>(res);
}

// ── Helpers ────────────────────────────────────────────────────────────── //

export function imageUrl(relativeUrl: string): string {
  return `${API_URL}${relativeUrl}`;
}
