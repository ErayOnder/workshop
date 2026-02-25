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
  onSubmit: (tags: string[], note?: string, chipDimensionMap?: Record<string, string[]>) => void;
};

// After this many ms of pending/running analysis, fall back to static chips
const ANALYSIS_FALLBACK_MS = 3000;

export default function ChipTray({
  activeSentiments,
  imageAnalysis,
  analysisStatus,
  onSubmit,
}: Props) {
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set());
  const [showOther, setShowOther] = useState(false);
  const [otherText, setOtherText] = useState("");
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
        {chips.map((chip) => (
          <button
            key={chip.id}
            type="button"
            className={`chip${selectedTags.has(chip.id) ? " chip--selected" : ""}`}
            onClick={() => toggleTag(chip.id)}
          >
            {chip.label}
          </button>
        ))}
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

      <button type="button" className="chip-submit-btn" onClick={handleSubmit}>
        {selectedTags.size > 0 || otherText ? "Submit feedback" : "Skip"}
      </button>
    </div>
  );
}
