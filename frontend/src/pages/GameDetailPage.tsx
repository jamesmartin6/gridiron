import { Link, useParams } from "react-router-dom";
import { getPrediction } from "../api/client";
import { DiffBar } from "../components/DiffBar";
import { useTeamName } from "../context/TeamsContext";
import { useApi } from "../hooks/useApi";

const DIFF_SPECS: {
  key: "epa_offense_diff" | "epa_defense_diff" | "turnover_margin_diff" | "win_pct_diff" | "yards_per_play_diff";
  label: string;
  clamp: number;
  format: (v: number) => string;
}[] = [
  { key: "epa_offense_diff", label: "Offense EPA/play", clamp: 0.3, format: (v) => v.toFixed(3) },
  { key: "epa_defense_diff", label: "Defense EPA/play allowed", clamp: 0.3, format: (v) => v.toFixed(3) },
  { key: "win_pct_diff", label: "Win %", clamp: 1, format: (v) => `${(v * 100).toFixed(0)}pp` },
  { key: "turnover_margin_diff", label: "Turnover margin", clamp: 15, format: (v) => v.toFixed(0) },
  { key: "yards_per_play_diff", label: "Yards / play", clamp: 2, format: (v) => v.toFixed(2) },
];

export function GameDetailPage() {
  const { gameId } = useParams<{ gameId: string }>();
  const { data, loading, error } = useApi(() => getPrediction(gameId!), [gameId]);

  const homeName = useTeamName(data?.game.home_team ?? "");
  const awayName = useTeamName(data?.game.away_team ?? "");

  if (loading) return <p className="status">Loading…</p>;
  if (error) return <p className="status error">Couldn't load this game: {error}</p>;
  if (!data) return null;

  const { game, feature_breakdown, prediction, home_stats, away_stats, stats_season } = data;
  const played = game.home_score !== null && game.away_score !== null;
  const homeWon = played && game.home_score! > game.away_score!;

  return (
    <div>
      <Link to="/" className="back-link">
        ← Back to this week
      </Link>

      <div className="card">
        <div className="detail-header">
          <div className="detail-team">
            <div className="abbr">{game.home_team}</div>
            <div className="name">{homeName}</div>
            {played && (
              <div className="score" style={{ color: homeWon ? "var(--good)" : undefined }}>
                {game.home_score}
              </div>
            )}
          </div>
          <div className="detail-vs">
            Week {game.week} · {game.season}
            <br />
            HOME
          </div>
          <div className="detail-team">
            <div className="abbr">{game.away_team}</div>
            <div className="name">{awayName}</div>
            {played && (
              <div className="score" style={{ color: played && !homeWon ? "var(--good)" : undefined }}>
                {game.away_score}
              </div>
            )}
          </div>
        </div>

        {prediction ? (
          <div className="win-prob-banner">
            <div className="big">{(prediction.home_win_prob * 100).toFixed(1)}%</div>
            <div className="label">
              probability {homeName} ({game.home_team}) wins, per model{" "}
              <code>{prediction.model_version}</code>
            </div>
          </div>
        ) : (
          <p className="status">No prediction available for this game yet.</p>
        )}
      </div>

      {feature_breakdown ? (
        <div className="card">
          <div className="page-header">
            <h2 style={{ fontSize: 16 }}>Why the model likes {game.home_team}</h2>
            <p>
              {game.home_team} minus {game.away_team}, using each team's {stats_season} season
              stats. Green favors {game.home_team}, red favors {game.away_team}.
            </p>
          </div>
          {DIFF_SPECS.map((spec) => (
            <DiffBar
              key={spec.key}
              label={spec.label}
              value={feature_breakdown[spec.key]}
              clamp={spec.clamp}
              format={spec.format}
            />
          ))}
        </div>
      ) : (
        <div className="card">
          <p className="status">
            No {stats_season} season stats for one or both teams — feature breakdown unavailable.
          </p>
        </div>
      )}

      {(home_stats || away_stats) && (
        <div className="card">
          <div className="page-header">
            <h2 style={{ fontSize: 16 }}>{stats_season} season stats</h2>
          </div>
          <table className="stats-table">
            <thead>
              <tr>
                <th></th>
                <th>{game.home_team}</th>
                <th>{game.away_team}</th>
              </tr>
            </thead>
            <tbody>
              <StatRow label="Win %" home={home_stats?.win_pct} away={away_stats?.win_pct} fmt={(v) => `${(v * 100).toFixed(0)}%`} />
              <StatRow label="Points for" home={home_stats?.points_for} away={away_stats?.points_for} />
              <StatRow label="Points against" home={home_stats?.points_against} away={away_stats?.points_against} />
              <StatRow label="Offense EPA/play" home={home_stats?.epa_offense} away={away_stats?.epa_offense} fmt={(v) => v.toFixed(3)} />
              <StatRow label="Defense EPA/play allowed" home={home_stats?.epa_defense} away={away_stats?.epa_defense} fmt={(v) => v.toFixed(3)} />
              <StatRow label="Turnover margin" home={home_stats?.turnover_margin} away={away_stats?.turnover_margin} />
              <StatRow label="Yards / play" home={home_stats?.yards_per_play} away={away_stats?.yards_per_play} fmt={(v) => v.toFixed(2)} />
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatRow({
  label,
  home,
  away,
  fmt = (v: number) => String(v),
}: {
  label: string;
  home?: number | null;
  away?: number | null;
  fmt?: (v: number) => string;
}) {
  return (
    <tr>
      <td className="diff-label">{label}</td>
      <td>{home != null ? fmt(home) : "—"}</td>
      <td>{away != null ? fmt(away) : "—"}</td>
    </tr>
  );
}
