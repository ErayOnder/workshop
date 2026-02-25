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
  SessionState,
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

  const eventSourceRef = useRef<EventSource | null>(null);

  const stopStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const startStream = useCallback(
    (sid: string) => {
      stopStream();

      const patchCandidate = (id: string, patch: Partial<Candidate>) => {
        setCandidates((prev) =>
          prev.map((c) => (c.candidate_id === id ? { ...c, ...patch } : c))
        );
      };

      eventSourceRef.current = openCandidateStream(sid, {
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
          eventSourceRef.current = null;
        },
      });
    },
    [stopStream]
  );

  useEffect(() => {
    return () => stopStream();
  }, [stopStream]);

  const startSession = useCallback(
    async (file: File, category?: JewelryCategory) => {
      setIsLoading(true);
      setError(null);
      try {
        const session: SessionState = await createSession(file, userId, category);
        setSessionId(session.session_id);
        setRoundNumber(session.round_number);
        setCandidates(session.candidates);
        setSelectedCandidateId(session.candidates[0]?.candidate_id ?? null);
        setSavedCandidateId(null);
        setFeedbackByCandidate({});
        setFinalizeResult(null);
        setPhase("review");
        startStream(session.session_id);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to start session");
      } finally {
        setIsLoading(false);
      }
    },
    [userId, startStream]
  );

  const selectCandidate = useCallback((id: string) => {
    setSelectedCandidateId(id);
  }, []);

  const advanceToNextRound = useCallback(
    async (force: boolean) => {
      if (!sessionId) return;
      try {
        const result = await nextRound(sessionId, force);
        const next = result.next_candidates;
        setCandidates(next);
        setRoundNumber(result.round_number);
        setSelectedCandidateId(next[0]?.candidate_id ?? null);
        setFeedbackByCandidate({});
        setError(null);
        startStream(sessionId);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to load next round";
        if (!force && message.toLowerCase().includes("feedback incomplete")) return;
        setError(message);
      }
    },
    [sessionId, startStream]
  );

  const submitFeedbackAction = useCallback(
    async (
      action: FeedbackAction,
      tags: string[],
      note?: string,
      chipDimensionMap?: Record<string, string[]>
    ) => {
      if (!sessionId || !selectedCandidateId) return;
      if (action === "save") setSavedCandidateId(selectedCandidateId);

      try {
        await submitFeedback(
          sessionId,
          selectedCandidateId,
          action,
          tags,
          note,
          chipDimensionMap
        );

        // Build updated feedback map locally (don't wait for re-render)
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

        // Auto-advance once all candidates have at least one like or dislike
        const allActioned =
          candidates.length > 0 &&
          candidates.every((c) => {
            const fb = updatedFeedback[c.candidate_id];
            return fb?.like.submitted || fb?.dislike.submitted;
          });

        if (allActioned) {
          await advanceToNextRound(false);
          return;
        }

        // Move to next unactioned candidate
        const nextUnactioned = candidates.find((c) => {
          const fb = updatedFeedback[c.candidate_id];
          return !fb?.like.submitted && !fb?.dislike.submitted;
        });
        if (nextUnactioned) {
          setSelectedCandidateId(nextUnactioned.candidate_id);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to submit feedback");
      }
    },
    [sessionId, selectedCandidateId, feedbackByCandidate, candidates, advanceToNextRound]
  );

  const goNextRound = useCallback(async () => {
    await advanceToNextRound(true);
  }, [advanceToNextRound]);

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

  const resetToUpload = useCallback(() => {
    stopStream();
    setPhase("upload");
    setSessionId(null);
    setCandidates([]);
    setSelectedCandidateId(null);
    setSavedCandidateId(null);
    setFeedbackByCandidate({});
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
    startSession,
    selectCandidate,
    submitFeedbackAction,
    goNextRound,
    doFinalize,
    resetToUpload,
  };
}
