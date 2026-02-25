"use client";

import { useEffect, useState } from "react";
import {
  DISLIKE_CHIPS,
  LIKE_CHIPS,
  type AnalysisStatus,
  type ChipTag,
  type ImageAnalysisData,
} from "../lib/types";

type Props = {
  activeSentiments: Set<"like" | "dislike">;
  imageAnalysis: ImageAnalysisData | null;
  analysisStatus: AnalysisStatus;
  initialTags?: string[];
  initialNote?: string;
  hasExistingSubmission?: boolean;
  onSubmit: (tags: string[], note?: string, chipDimensionMap?: Record<string, string[]>) => void;
};

// After this many ms of pending/running analysis, fall back to static chips
const ANALYSIS_FALLBACK_MS = 3000;

function normalizeTag(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export default function ChipTray({
  activeSentiments,
  imageAnalysis,
  analysisStatus,
  initialTags = [],
  initialNote,
  hasExistingSubmission = false,
  onSubmit,
}: Props) {
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set(initialTags));
  const [showOther, setShowOther] = useState(false);
  const [otherText, setOtherText] = useState(initialNote ?? "");
  const [fallbackTriggered, setFallbackTriggered] = useState(false);

  const isAnalysisPending = analysisStatus === "pending" || analysisStatus === "running";
  const isDynamicReady = analysisStatus === "done" && imageAnalysis !== null;

  // Start fallback timer when analysis is still pending after mount
  useEffect(() => {
    if (!isAnalysisPending) {
      setFallbackTriggered(false);
      return;
    }
    const t = setTimeout(() => setFallbackTriggered(true), ANALYSIS_FALLBACK_MS);
    return () => clearTimeout(t);
  }, [isAnalysisPending]);

  useEffect(() => {
    setSelectedTags(new Set(initialTags));
    setOtherText(initialNote ?? "");
    setShowOther(Boolean(initialNote));
  }, [initialTags, initialNote]);

  const showLoadingSkeleton = isAnalysisPending && !fallbackTriggered;

  // Determine which chips to show
  const likeChips: ChipTag[] = isDynamicReady
    ? imageAnalysis!.like_chips
    : LIKE_CHIPS;
  const dislikeChips: ChipTag[] = isDynamicReady
    ? imageAnalysis!.dislike_chips
    : DISLIKE_CHIPS;

  const chips: ChipTag[] = [
    ...(activeSentiments.has("like") ? likeChips : []),
    ...(activeSentiments.has("dislike") ? dislikeChips : []),
  ];
  const previouslySubmittedNormalizedTags = new Set(initialTags.map(normalizeTag));
  const normalizedCurrentTags = Array.from(selectedTags).sort();
  const normalizedInitialTags = [...initialTags].sort();
  const normalizedCurrentNote = otherText.trim();
  const normalizedInitialNote = (initialNote ?? "").trim();
  const isDuplicateSubmission =
    hasExistingSubmission &&
    normalizedCurrentNote === normalizedInitialNote &&
    normalizedCurrentTags.length === normalizedInitialTags.length &&
    normalizedCurrentTags.every((tag, idx) => tag === normalizedInitialTags[idx]);
  const duplicateReason =
    normalizedInitialTags.length > 0
      ? `${normalizedInitialTags.join(", ")} zaten gonderildi.`
      : "Bu feedback kombinasyonunu zaten gonderdiniz.";

  function toggleTag(id: string) {
    setSelectedTags((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function handleSubmit() {
    const tags = Array.from(selectedTags);

    // Build chip→dimension map for only the selected chips
    let chipDimensionMap: Record<string, string[]> | undefined;
    if (isDynamicReady && imageAnalysis) {
      chipDimensionMap = {};
      for (const tag of tags) {
        const dims = imageAnalysis.chip_dimension_map[tag];
        if (dims) chipDimensionMap[tag] = dims;
      }
    }

    onSubmit(tags, otherText.trim() || undefined, chipDimensionMap);
  }

  if (showLoadingSkeleton) {
    return (
      <div className="chip-tray">
        <p className="chip-tray-hint">Analyzing image...</p>
        <div className="chip-list chip-list--loading">
          {[1, 2, 3].map((i) => (
            <span key={i} className="chip chip--skeleton" />
          ))}
        </div>
      </div>
    );
  }

  if (chips.length === 0) return null;

  return (
    <div className="chip-tray">
      <p className="chip-tray-hint">What stood out? (optional)</p>
      <div className="chip-list">
        {chips.map((chip) => {
          const isSelected = selectedTags.has(chip.id);
          const isPreviouslySubmitted =
            hasExistingSubmission &&
            (
              previouslySubmittedNormalizedTags.has(normalizeTag(chip.id)) ||
              previouslySubmittedNormalizedTags.has(normalizeTag(chip.label))
            );

          return (
            <button
              key={chip.id}
              type="button"
              className={[
                "chip",
                isSelected ? "chip--selected" : "",
                isPreviouslySubmitted ? "chip--previously-submitted" : "",
                isPreviouslySubmitted ? "chip--locked" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => toggleTag(chip.id)}
              disabled={isPreviouslySubmitted}
              title={
                isPreviouslySubmitted
                  ? "Bu chip daha once gonderildi ve tekrar secilemez."
                  : undefined
              }
            >
              {chip.label}
            </button>
          );
        })}
        <button
          type="button"
          className={`chip${showOther ? " chip--selected" : ""}`}
          onClick={() => setShowOther((v) => !v)}
        >
          Other
        </button>
      </div>

      {showOther && (
        <input
          className="chip-other-input"
          type="text"
          placeholder="Describe what you liked or disliked..."
          value={otherText}
          onChange={(e) => setOtherText(e.target.value)}
          autoFocus
        />
      )}

      <button
        type="button"
        className={`chip-submit-btn${isDuplicateSubmission ? " chip-submit-btn--blocked" : ""}`}
        onClick={handleSubmit}
        disabled={isDuplicateSubmission}
        title={isDuplicateSubmission ? duplicateReason : undefined}
      >
        {isDuplicateSubmission
          ? "Already submitted"
          : (selectedTags.size > 0 || otherText ? "Submit feedback" : "Skip")}
      </button>
    </div>
  );
}
