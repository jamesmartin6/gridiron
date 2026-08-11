export function WinProbBar({ prob }: { prob: number }) {
  const pct = Math.round(prob * 1000) / 10;
  return (
    <div className="prob-cell">
      <div className="prob-bar">
        <div className="prob-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="prob-value">{pct.toFixed(1)}%</span>
    </div>
  );
}
