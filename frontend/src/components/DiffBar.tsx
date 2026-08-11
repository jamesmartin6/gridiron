export function DiffBar({
  label,
  value,
  clamp,
  format,
}: {
  label: string;
  value: number | null;
  clamp: number;
  format: (v: number) => string;
}) {
  if (value === null) {
    return (
      <div className="diff-row">
        <span className="diff-label">{label}</span>
        <div className="diff-track" />
        <span className="diff-value">—</span>
      </div>
    );
  }

  const magnitude = Math.min(Math.abs(value) / clamp, 1) * 50;
  const positive = value >= 0;

  return (
    <div className="diff-row">
      <span className="diff-label">{label}</span>
      <div className="diff-track">
        <div className="mid" />
        <div
          className={`diff-fill ${positive ? "positive" : "negative"}`}
          style={{ width: `${magnitude}%` }}
        />
      </div>
      <span className="diff-value">{format(value)}</span>
    </div>
  );
}
