"use client";

import { imageUrl } from "../lib/api";
import type { Candidate, CandidateLocalFeedback } from "../lib/types";

type Props = {
  candidates: Candidate[];
  selectedId: string | null;
  feedbackByCandidate: Record<string, CandidateLocalFeedback>;
  onSelect: (id: string) => void;
};

export default function CandidateRow({
  candidates,
  selectedId,
  feedbackByCandidate,
  onSelect,
}: Props) {
  return (
    <div className="candidate-row">
      {candidates.map((c, i) => {
        const isSelected = c.candidate_id === selectedId;
        const isGenerating =
          c.generation_status === "pending" || c.generation_status === "generating";
        const isError = c.generation_status === "error";
        const isDone = c.generation_status === "done" && c.image_url;

        const fb = feedbackByCandidate[c.candidate_id];
        const likeSubmitted = fb?.like.submitted ?? false;
        const dislikeSubmitted = fb?.dislike.submitted ?? false;
        const hasAnyFeedback = likeSubmitted || dislikeSubmitted;

        return (
          <button
            key={c.candidate_id}
            className={`candidate-thumb${isSelected ? " candidate-thumb--selected" : ""}`}
            onClick={() => onSelect(c.candidate_id)}
            type="button"
            aria-label={`Option ${i + 1}`}
          >
            {isDone && (
              <img
                src={imageUrl(c.image_url!)}
                alt={`Candidate ${i + 1}`}
                className="candidate-thumb-img"
              />
            )}
            {isGenerating && <div className="shimmer candidate-thumb-shimmer" />}
            {isError && (
              <div className="candidate-thumb-error">
                <span>Failed</span>
              </div>
            )}
            {hasAnyFeedback && (
              <div className="candidate-thumb-reviewed-stack">
                {likeSubmitted && (
                  <div className="candidate-thumb-reviewed" title="Like submitted">
                    ✓
                  </div>
                )}
                {dislikeSubmitted && (
                  <div className="candidate-thumb-reviewed" title="Dislike submitted">
                    ✓
                  </div>
                )}
              </div>
            )}
            {isSelected && <div className="candidate-thumb-ring" />}
          </button>
        );
      })}
    </div>
  );
}
