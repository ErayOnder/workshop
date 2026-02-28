"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createSession,
  finalizeSession,
  nextRound,
  openCandidateStream,
  submitFeedback,
  type AnalysisDoneEvent,
  type CandidateDoneEvent,
} from "./api";
import type {
  ActionFeedback,
  Candidate,
  CandidateLocalFeedback,
  FeedbackAction,
  FinalizeResult,
  JewelryCategory,
  ScreenPhase,
} from "./types";

const USER_ID_KEY = "workshop_user_id";

function getOrCreateUserId(): string {
  if (typeof window === "undefined") return "";
  let id = localStorage.getItem(USER_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}

const EMPTY_ACTION: ActionFeedback = { submitted: false, chips: [], chipDimMap: {} };

function emptyFeedback(): CandidateLocalFeedback {
  return { like: { ...EMPTY_ACTION }, dislike: { ...EMPTY_ACTION }, save: false };
}

export type SessionHook = {
  phase: ScreenPhase;
  userId: string;
  sessionId: string | null;
  roundNumber: number;
  candidates: Candidate[];
  selectedCandidateId: string | null;
  isLoading: boolean;
  error: string | null;
  savedCandidateId: string | null;
  feedbackByCandidate: Record<string, CandidateLocalFeedback>;
  finalizeResult: FinalizeResult | null;
  canGoNext: boolean;
  hasPendingFeedback: boolean;

  startSession: (file: File, category?: JewelryCategory) => Promise<void>;
  selectCandidate: (id: string) => void;
  submitFeedbackAction: (
    action: FeedbackAction,
    tags: string[],
    note?: string,
    chipDimensionMap?: Record<string, string[]>
  ) => Promise<void>;
  goNextRound: () => Promise<void>;
  doFinalize: (selectedId: string) => Promise<void>;
  resetToUpload: () => void;
};

export function useSession(): SessionHook {
  const [phase, setPhase] = useState<ScreenPhase>("upload");
  const [userId] = useState<string>(() => getOrCreateUserId());
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [roundNumber, setRoundNumber] = useState(0);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedCandidateId, setSavedCandidateId] = useState<string | null>(null);
  const [feedbackByCandidate, setFeedbackByCandidate] = useState<Record<string, CandidateLocalFeedback>>({});
  const [finalizeResult, setFinalizeResult] = useState<FinalizeResult | null>(null);
  const [pendingFeedbackCount, setPendingFeedbackCount] = useState(0);

  const eventSourceRef = useRef<EventSource | null>(null);
  const pendingFeedbackRequestsRef = useRef<Set<Promise<unknown>>>(new Set());

  const stopStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  // SSE stream with all event handlers including candidates_created
  const startStream = useCallback(
    (sid: string) => {
      stopStream();

      const patchCandidate = (id: string, patch: Partial<Candidate>) => {
        setCandidates((prev) =>
          prev.map((c) => (c.candidate_id === id ? { ...c, ...patch } : c))
        );
      };

      eventSourceRef.current = openCandidateStream(sid, {
        onCandidatesCreated: (e) => {
          setCandidates(e.candidates);
          setSelectedCandidateId(e.candidates[0]?.candidate_id ?? null);
          setRoundNumber(e.round_number);
        },
        onCandidateDone: (e: CandidateDoneEvent) => {
          patchCandidate(e.candidate_id, {
            generation_status: e.generation_status,
            image_url: e.image_url ?? undefined,
            error: e.error ?? undefined,
            analysis_status: e.analysis_status,
          });
        },
        onAnalysisDone: (e: AnalysisDoneEvent) => {
          patchCandidate(e.candidate_id, {
            analysis_status: e.analysis_status,
            image_analysis: e.image_analysis ?? undefined,
          });
        },
        onRoundComplete: (e) => {
          setRoundNumber(e.round_number);
          setIsLoading(false);
          eventSourceRef.current = null;
        },
        onPipelineError: (e) => {
          setError(`Generation failed: ${e.error}`);
          setIsLoading(false);
        },
      });
    },
    [stopStream]
  );

  useEffect(() => {
    return () => stopStream();
  }, [stopStream]);

  // ── Session creation (SSE-first) ─────────────────────────────────────── //

  const startSession = useCallback(
    async (file: File, category?: JewelryCategory) => {
      setIsLoading(true);
      setError(null);
      setCandidates([]);
      setSavedCandidateId(null);
      setFeedbackByCandidate({});
      setFinalizeResult(null);
      setPendingFeedbackCount(0);
      pendingFeedbackRequestsRef.current.clear();

      try {
        const result = await createSession(file, userId, category);
        setSessionId(result.session_id);
        setRoundNumber(result.round_number);
        setPhase("review");
        // Start SSE stream — candidates arrive via candidates_created event
        startStream(result.session_id);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to start session");
        setIsLoading(false);
      }
      // isLoading stays true until round_complete or pipeline_error via SSE
    },
    [userId, startStream]
  );

  const selectCandidate = useCallback((id: string) => {
    setSelectedCandidateId(id);
  }, []);

  // ── Next round (SSE-first) ───────────────────────────────────────────── //

  const advanceToNextRound = useCallback(
    async () => {
      if (!sessionId) return;

      // Clear old round state
      setCandidates([]);
      setSelectedCandidateId(null);
      setFeedbackByCandidate({});
      setPendingFeedbackCount(0);
      setError(null);

      // Start SSE stream BEFORE calling the API so we never miss
      // the candidates_created event from the background pipeline.
      startStream(sessionId);

      try {
        const result = await nextRound(sessionId, true);
        setRoundNumber(result.round_number);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to load next round";
        setError(message);
        setIsLoading(false);
      }
      // isLoading stays true until round_complete or pipeline_error via SSE
    },
    [sessionId, startStream]
  );

  // ── Feedback ─────────────────────────────────────────────────────────── //

  const submitFeedbackAction = useCallback(
    async (
      action: FeedbackAction,
      tags: string[],
      note?: string,
      chipDimensionMap?: Record<string, string[]>
    ) => {
      if (!sessionId || !selectedCandidateId) return;
      if (action === "save") setSavedCandidateId(selectedCandidateId);

      // Optimistic local update
      const prev = feedbackByCandidate[selectedCandidateId] ?? emptyFeedback();
      const updatedEntry: CandidateLocalFeedback =
        action === "like"
          ? { ...prev, like: { submitted: true, chips: tags, chipDimMap: chipDimensionMap ?? {}, note } }
          : action === "dislike"
            ? { ...prev, dislike: { submitted: true, chips: tags, chipDimMap: chipDimensionMap ?? {}, note } }
            : { ...prev, save: true };
      const updatedFeedback = { ...feedbackByCandidate, [selectedCandidateId]: updatedEntry };
      setFeedbackByCandidate(updatedFeedback);
      setError(null);

      // Move to next unactioned candidate
      const nextUnactioned = candidates.find((c) => {
        const fb = updatedFeedback[c.candidate_id];
        return !fb?.like.submitted && !fb?.dislike.submitted;
      });
      if (nextUnactioned) {
        setSelectedCandidateId(nextUnactioned.candidate_id);
      }

      setPendingFeedbackCount((n) => n + 1);
      const requestPromise = submitFeedback(
        sessionId,
        selectedCandidateId,
        action,
        tags,
        note,
        chipDimensionMap
      );
      pendingFeedbackRequestsRef.current.add(requestPromise);

      try {
        await requestPromise;
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to submit feedback");
      } finally {
        pendingFeedbackRequestsRef.current.delete(requestPromise);
        setPendingFeedbackCount((n) => Math.max(0, n - 1));
      }
    },
    [sessionId, selectedCandidateId, candidates, feedbackByCandidate]
  );

  // ── Go next round ───────────────────────────────────────────────────── //

  const goNextRound = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // Wait for any in-flight feedback writes before advancing.
      const inflight = Array.from(pendingFeedbackRequestsRef.current);
      if (inflight.length > 0) {
        await Promise.allSettled(inflight);
      }
      await advanceToNextRound();
    } catch {
      setIsLoading(false);
    }
    // isLoading stays true until round_complete or pipeline_error via SSE
  }, [advanceToNextRound]);

  const canGoNext = candidates.length > 0 && !isLoading;

  // ── Finalize ─────────────────────────────────────────────────────────── //

  const doFinalize = useCallback(
    async (selectedId: string) => {
      if (!sessionId) return;
      setIsLoading(true);
      setError(null);
      try {
        const result = await finalizeSession(sessionId, selectedId);
        setFinalizeResult(result);
        stopStream();
        setPhase("finalization");
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to finalize");
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, stopStream]
  );

  // ── Reset ────────────────────────────────────────────────────────────── //

  const resetToUpload = useCallback(() => {
    stopStream();
    setPhase("upload");
    setSessionId(null);
    setCandidates([]);
    setSelectedCandidateId(null);
    setSavedCandidateId(null);
    setFeedbackByCandidate({});
    setPendingFeedbackCount(0);
    pendingFeedbackRequestsRef.current.clear();
    setFinalizeResult(null);
    setError(null);
    setRoundNumber(0);
  }, [stopStream]);

  return {
    phase,
    userId,
    sessionId,
    roundNumber,
    candidates,
    selectedCandidateId,
    isLoading,
    error,
    savedCandidateId,
    feedbackByCandidate,
    finalizeResult,
    canGoNext,
    hasPendingFeedback: pendingFeedbackCount > 0,
    startSession,
    selectCandidate,
    submitFeedbackAction,
    goNextRound,
    doFinalize,
    resetToUpload,
  };
}
