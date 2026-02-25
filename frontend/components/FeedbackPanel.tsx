"use client";

import { useEffect, useState } from "react";
import ChipTray from "./ChipTray";
import type { Candidate, CandidateLocalFeedback, FeedbackAction } from "../lib/types";

type Props = {
  selectedCandidateId: string | null;
  selectedCandidate: Candidate | null;
  candidateFeedback: CandidateLocalFeedback | null;
  canGoNext: boolean;
  onFeedback: (
    action: FeedbackAction,
    tags: string[],
    note?: string,
    chipDimensionMap?: Record<string, string[]>
  ) => void;
  onNext: () => void;
  onDone: () => void;
};

export default function FeedbackPanel({
  selectedCandidateId,
  selectedCandidate,
  candidateFeedback,
  canGoNext,
  onFeedback,
  onNext,
  onDone,
}: Props) {
  const [pendingAction, setPendingAction] = useState<"like" | "dislike" | null>(null);
  const [showChips, setShowChips] = useState(false);

  // Close chip tray when the selected candidate changes
  useEffect(() => {
    setShowChips(false);
    setPendingAction(null);
  }, [selectedCandidateId]);

  const likeSubmitted = candidateFeedback?.like.submitted ?? false;
  const dislikeSubmitted = candidateFeedback?.dislike.submitted ?? false;
  const saveDone = candidateFeedback?.save ?? false;

  function handleAction(action: FeedbackAction) {
    if (action === "save") {
      onFeedback("save", []);
      return;
    }
    setPendingAction(action);
    setShowChips(true);
  }

  function handleChipSubmit(
    tags: string[],
    note?: string,
    chipDimensionMap?: Record<string, string[]>
  ) {
    if (pendingAction) {
      onFeedback(pendingAction, tags, note, chipDimensionMap);
    }
    setShowChips(false);
    setPendingAction(null);
  }

  const disabled = !selectedCandidateId;

  // ChipTray only shows chips for the current pending action
  const activeSentiments = new Set<"like" | "dislike">(pendingAction ? [pendingAction] : []);

  return (
    <div className="feedback-panel">
      <div className="feedback-actions">
        <button
          type="button"
          className={`feedback-btn feedback-btn--dislike${dislikeSubmitted ? " feedback-btn--submitted" : ""}`}
          onClick={() => handleAction("dislike")}
          disabled={disabled}
          aria-label="Dislike"
        >
          <span className="feedback-icon">✕</span>
          {dislikeSubmitted ? "Disliked" : "Dislike"}
        </button>

        <button
          type="button"
          className={`feedback-btn feedback-btn--like${likeSubmitted ? " feedback-btn--submitted" : ""}`}
          onClick={() => handleAction("like")}
          disabled={disabled}
          aria-label="Like"
        >
          <span className="feedback-icon">♥</span>
          {likeSubmitted ? "Liked" : "Like"}
        </button>
      </div>

      <button
        type="button"
        className={`feedback-btn feedback-btn--save${saveDone ? " feedback-btn--saved" : ""}`}
        onClick={() => handleAction("save")}
        disabled={disabled}
        aria-label="Save"
      >
        {saveDone ? "Saved" : "Save"}
      </button>

      {showChips && (
        <ChipTray
          activeSentiments={activeSentiments}
          imageAnalysis={selectedCandidate?.image_analysis ?? null}
          analysisStatus={selectedCandidate?.analysis_status ?? "pending"}
          onSubmit={handleChipSubmit}
        />
      )}

      <div className="round-nav-actions">
        <button type="button" className="done-btn" onClick={onDone}>
          Done exploring
        </button>
        <button type="button" className="next-btn" onClick={onNext} disabled={!canGoNext}>
          Next
        </button>
      </div>
    </div>
  );
}
