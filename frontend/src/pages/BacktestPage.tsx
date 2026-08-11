import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getBacktestResults } from "../api/client";
import { useApi } from "../hooks/useApi";
import type { BacktestResult } from "../api/types";

const SERIES_COLORS = ["#4f7cff", "#34d399", "#f59e0b", "#f87171"];

function modelType(version: string): string {
  return version.split("_bt_")[0] ?? version;
}

function buildChartData(results: BacktestResult[]) {
  const seasons = [...new Set(results.map((r) => r.test_season))].sort();
  const types = [...new Set(results.map((r) => modelType(r.model_version)))].sort();

  const rows = seasons.map((season) => {
    const seasonResults = results.filter((r) => r.test_season === season);
    const row: Record<string, number | string> = { season: String(season) };
    row.baseline = Number(seasonResults[0]?.baseline_accuracy ?? 0) * 100;
    for (const t of types) {
      const r = seasonResults.find((x) => modelType(x.model_version) === t);
      if (r && r.accuracy !== null) row[t] = Number(r.accuracy) * 100;
    }
    return row;
  });

  return { rows, types };
}

export function BacktestPage() {
  const { data: results, loading, error } = useApi(() => getBacktestResults(), []);

  const { rows, types } = useMemo(() => buildChartData(results ?? []), [results]);

  const overall = useMemo(() => {
    if (!results || results.length === 0) return null;
    const avg = (f: (r: BacktestResult) => number | null) => {
      const values = results.map(f).filter((v): v is number => v !== null);
      return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
    };
    return {
      accuracy: avg((r) => r.accuracy),
      logLoss: avg((r) => r.log_loss),
      brier: avg((r) => r.brier_score),
      baseline: avg((r) => r.baseline_accuracy),
    };
  }, [results]);

  return (
    <div>
      <div className="page-header">
        <h2>Model Accuracy</h2>
        <p>
          Walk-forward backtest: each test season is predicted using a model trained only on
          strictly earlier seasons, with each game featurized from the prior season's stats —
          the same setup used for live predictions.
        </p>
      </div>

      {loading && <p className="status">Loading backtest results…</p>}
      {error && <p className="status error">Couldn't load backtest results: {error}</p>}

      {overall && (
        <div className="metric-grid">
          <MetricTile label="Avg. accuracy" value={`${(overall.accuracy! * 100).toFixed(1)}%`} />
          <MetricTile label="Avg. home-favorite baseline" value={`${(overall.baseline! * 100).toFixed(1)}%`} />
          <MetricTile label="Avg. log loss" value={overall.logLoss!.toFixed(3)} />
          <MetricTile label="Avg. Brier score" value={overall.brier!.toFixed(3)} />
        </div>
      )}

      {rows.length > 0 && (
        <div className="card">
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={rows} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#232c47" />
              <XAxis dataKey="season" stroke="#9aa5c4" fontSize={12} />
              <YAxis stroke="#9aa5c4" fontSize={12} unit="%" domain={[0, 100]} />
              <Tooltip
                contentStyle={{ background: "#131a2e", border: "1px solid #232c47", borderRadius: 8 }}
                formatter={(value) => `${Number(value).toFixed(1)}%`}
              />
              <Legend />
              <Bar dataKey="baseline" name="Home-favorite baseline" fill="#3a4368" radius={[4, 4, 0, 0]} />
              {types.map((t, i) => (
                <Bar
                  key={t}
                  dataKey={t}
                  name={t}
                  fill={SERIES_COLORS[i % SERIES_COLORS.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {results && results.length > 0 && (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th>Test season</th>
                <th>Accuracy</th>
                <th>Baseline</th>
                <th>Log loss</th>
                <th>Brier score</th>
                <th># games</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.id}>
                  <td>{r.model_version}</td>
                  <td>{r.test_season}</td>
                  <td>{r.accuracy !== null ? `${(r.accuracy * 100).toFixed(1)}%` : "—"}</td>
                  <td>{r.baseline_accuracy !== null ? `${(r.baseline_accuracy * 100).toFixed(1)}%` : "—"}</td>
                  <td>{r.log_loss?.toFixed(3) ?? "—"}</td>
                  <td>{r.brier_score?.toFixed(3) ?? "—"}</td>
                  <td>{r.n_games ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && (!results || results.length === 0) && (
        <p className="status">
          No backtest results yet. Run <code>python -m ml.backtest --seasons 2023 2024 2025</code>{" "}
          from the backend.
        </p>
      )}
    </div>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-tile">
      <div className="value">{value}</div>
      <div className="label">{label}</div>
    </div>
  );
}
