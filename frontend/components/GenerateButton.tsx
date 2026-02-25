"use client";

import { Sparkles } from "lucide-react";

interface Props {
  ready: boolean;
  loading: boolean;
  onClick: () => void;
}

export default function GenerateButton({ ready, loading, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      disabled={!ready || loading}
      className="gen-btn"
    >
      {loading ? (
        <>
          <span className="gen-btn__spinner" />
          <span>Generating…</span>
        </>
      ) : (
        <>
          <Sparkles size={15} strokeWidth={1.8} />
          <span>Generate</span>
        </>
      )}
    </button>
  );
}
