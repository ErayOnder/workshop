"use client";

import { imageUrl } from "../lib/api";
import type { FinalizeResult } from "../lib/types";

type Props = {
  result: FinalizeResult;
  onReset: () => void;
};

function DownloadButton({ url, label }: { url: string; label: string }) {
  return (
    <a
      href={imageUrl(url)}
      download
      target="_blank"
      rel="noopener noreferrer"
      className="download-btn"
    >
      {label}
    </a>
  );
}

export default function FinalizationView({ result, onReset }: Props) {
  return (
    <div className="finalization-view">
      <h2 className="finalization-title">Your shot is ready</h2>

      <div className="finalization-hero">
        <img
          src={imageUrl(result.hero_image_url)}
          alt="Selected hero image"
          className="finalization-hero-img"
        />
        <DownloadButton url={result.hero_image_url} label="Download original" />
      </div>

      <h3 className="finalization-subtitle">Export variants</h3>
      <div className="export-variants">
        <div className="export-variant">
          <div className="export-variant-label">Feed (1:1)</div>
          <img
            src={imageUrl(result.export_variants.feed_1x1)}
            alt="Feed 1:1 export"
            className="export-variant-img export-variant-img--square"
          />
          <DownloadButton url={result.export_variants.feed_1x1} label="Download" />
        </div>

        <div className="export-variant">
          <div className="export-variant-label">Story (9:16)</div>
          <img
            src={imageUrl(result.export_variants.story_9x16)}
            alt="Story 9:16 export"
            className="export-variant-img export-variant-img--story"
          />
          <DownloadButton url={result.export_variants.story_9x16} label="Download" />
        </div>
      </div>

      <button type="button" className="reset-btn" onClick={onReset}>
        Start new session
      </button>
    </div>
  );
}
