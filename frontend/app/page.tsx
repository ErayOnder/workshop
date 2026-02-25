"use client";

import { useState } from "react";
import { useSession } from "@/lib/useSession";
import type { JewelryCategory } from "@/lib/types";
import UploadZone from "@/components/UploadZone";
import GenerateButton from "@/components/GenerateButton";
import CategorySelector from "@/components/CategorySelector";
import ProgressIndicator from "@/components/ProgressIndicator";
import CandidateRow from "@/components/CandidateRow";
import Podium from "@/components/Podium";
import FeedbackPanel from "@/components/FeedbackPanel";
import FinalizationView from "@/components/FinalizationView";

export default function Home() {
  const session = useSession();
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState<JewelryCategory | null>(null);

  // Derive selected candidate object
  const selectedCandidate =
    session.candidates.find((c) => c.candidate_id === session.selectedCandidateId) ?? null;

  const selectedIndex = session.selectedCandidateId
    ? session.candidates.findIndex((c) => c.candidate_id === session.selectedCandidateId)
    : 0;

  async function handleGenerate() {
    if (!file) return;
    await session.startSession(file, category ?? undefined);
  }

  async function handleDone() {
    if (!session.selectedCandidateId) return;
    // Prefer savedCandidateId if set, otherwise use current selection
    const toFinalize = session.savedCandidateId ?? session.selectedCandidateId;
    await session.doFinalize(toFinalize);
  }

  async function handleNext() {
    await session.goNextRound();
  }

  // ── Upload screen ──────────────────────────────────────────────────────── //
  if (session.phase === "upload") {
    return (
      <main className="page">
        <header className="header">
          <div className="header__logo">
            <span className="header__gem">◈</span>
            <h1 className="header__title">workshop</h1>
          </div>
          <p className="header__sub">jewelry style generator</p>
        </header>

        <div className="controls">
          <UploadZone file={file} onChange={setFile} disabled={session.isLoading} />
          <CategorySelector value={category} onChange={setCategory} />
          <GenerateButton
            ready={!!file}
            loading={session.isLoading}
            onClick={handleGenerate}
          />
          {session.error && <p className="error-msg">{session.error}</p>}
        </div>
      </main>
    );
  }

  // ── Finalization screen ────────────────────────────────────────────────── //
  if (session.phase === "finalization" && session.finalizeResult) {
    return (
      <main className="page">
        <header className="header">
          <div className="header__logo">
            <span className="header__gem">◈</span>
            <h1 className="header__title">workshop</h1>
          </div>
        </header>
        <FinalizationView result={session.finalizeResult} onReset={session.resetToUpload} />
      </main>
    );
  }

  // ── Review loop screen ─────────────────────────────────────────────────── //
  return (
    <main className="page page--review">
      <header className="header header--compact">
        <div className="header__logo">
          <span className="header__gem">◈</span>
          <h1 className="header__title">workshop</h1>
        </div>
        <ProgressIndicator
          roundNumber={session.roundNumber}
          totalCandidates={session.candidates.length}
          selectedIndex={selectedIndex}
        />
      </header>

      <div className="review-layout">
        <CandidateRow
          candidates={session.candidates}
          selectedId={session.selectedCandidateId}
          feedbackByCandidate={session.feedbackByCandidate}
          onSelect={session.selectCandidate}
        />

        <Podium candidate={selectedCandidate} />

        <FeedbackPanel
          selectedCandidateId={session.selectedCandidateId}
          selectedCandidate={selectedCandidate}
          candidateFeedback={
            session.selectedCandidateId
              ? (session.feedbackByCandidate[session.selectedCandidateId] ?? null)
              : null
          }
          canGoNext={session.canGoNext}
          onFeedback={session.submitFeedbackAction}
          onNext={handleNext}
          onDone={handleDone}
        />

        {session.error && <p className="error-msg">{session.error}</p>}
      </div>
    </main>
  );
}
