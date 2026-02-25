"use client";

import { imageUrl } from "../lib/api";
import type { Candidate } from "../lib/types";

type Props = {
  candidate: Candidate | null;
};

export default function Podium({ candidate }: Props) {
  if (!candidate) {
    return <div className="podium podium--empty shimmer" />;
  }

  const isGenerating =
    candidate.generation_status === "pending" ||
    candidate.generation_status === "generating";
  const isDone = candidate.generation_status === "done" && candidate.image_url;
  const isError = candidate.generation_status === "error";

  return (
    <div className="podium">
      {isDone && (
        <img
          src={imageUrl(candidate.image_url!)}
          alt="Selected candidate"
          className="podium-img"
        />
      )}
      {isGenerating && <div className="shimmer podium-shimmer" />}
      {isError && (
        <div className="podium-error">
          <span>Generation failed</span>
        </div>
      )}
    </div>
  );
}
