type Props = {
  roundNumber: number;
  totalCandidates: number;
  selectedIndex: number;
};

export default function ProgressIndicator({
  roundNumber,
  totalCandidates,
  selectedIndex,
}: Props) {
  return (
    <div className="progress-indicator">
      <span className="progress-round">Round {roundNumber}</span>
      <span className="progress-sep">·</span>
      <span className="progress-option">
        Option {selectedIndex + 1}/{totalCandidates}
      </span>
    </div>
  );
}
