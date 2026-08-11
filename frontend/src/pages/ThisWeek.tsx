import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getGames } from "../api/client";
import { WinProbBar } from "../components/WinProbBar";
import { useTeamName } from "../context/TeamsContext";
import { useApi } from "../hooks/useApi";
import type { Game } from "../api/types";

type SortKey = "matchup" | "prob" | "score";

function GameRow({ game }: { game: Game }) {
  const homeName = useTeamName(game.home_team);
  const awayName = useTeamName(game.away_team);
  const played = game.home_score !== null && game.away_score !== null;

  return (
    <tr>
      <td>
        <Link to={`/games/${game.game_id}`} className="matchup">
          <span>
            {homeName} <span style={{ color: "var(--text-dim)" }}>(home)</span>
          </span>
          <span className="away">vs {awayName}</span>
        </Link>
      </td>
      <td>
        {game.prediction ? (
          <WinProbBar prob={game.prediction.home_win_prob} />
        ) : (
          <span className="status">no prediction yet</span>
        )}
      </td>
      <td className="score">
        {played ? `${game.home_score} – ${game.away_score}` : "—"}
      </td>
      <td className="score">{game.game_date ?? "—"}</td>
    </tr>
  );
}

export function ThisWeek() {
  const [season, setSeason] = useState<number | undefined>(undefined);
  const [week, setWeek] = useState<number | undefined>(undefined);
  const [sortKey, setSortKey] = useState<SortKey>("prob");
  const [sortDir, setSortDir] = useState<1 | -1>(-1);

  const { data: games, loading, error } = useApi(() => getGames(season, week), [season, week]);

  const resolved = games?.[0];

  const sorted = useMemo(() => {
    if (!games) return [];
    const copy = [...games];
    copy.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "matchup") cmp = a.home_team.localeCompare(b.home_team);
      else if (sortKey === "prob")
        cmp = (a.prediction?.home_win_prob ?? -1) - (b.prediction?.home_win_prob ?? -1);
      else if (sortKey === "score")
        cmp = (a.home_score ?? -1) - (b.home_score ?? -1);
      return cmp * sortDir;
    });
    return copy;
  }, [games, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) setSortDir((d) => (d === 1 ? -1 : 1));
    else {
      setSortKey(key);
      setSortDir(-1);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>This Week</h2>
        <p>Home win probability from each team's prior-season stats.</p>
      </div>

      <div className="card">
        <div className="week-controls">
          <label>
            Season
            <input
              type="number"
              placeholder={resolved ? String(resolved.season) : "auto"}
              value={season ?? ""}
              onChange={(e) => setSeason(e.target.value ? Number(e.target.value) : undefined)}
            />
          </label>
          <label>
            Week
            <input
              type="number"
              placeholder={resolved ? String(resolved.week) : "auto"}
              value={week ?? ""}
              onChange={(e) => setWeek(e.target.value ? Number(e.target.value) : undefined)}
            />
          </label>
          {resolved && (
            <span className="badge">
              Season {resolved.season} · Week {resolved.week}
            </span>
          )}
        </div>

        {loading && <p className="status">Loading games…</p>}
        {error && <p className="status error">Couldn't load games: {error}</p>}
        {!loading && !error && sorted.length === 0 && (
          <p className="status">
            No games found. Try a different season/week, or run <code>/ingest</code> and{" "}
            <code>/predict</code> from the API.
          </p>
        )}

        {!loading && !error && sorted.length > 0 && (
          <table>
            <thead>
              <tr>
                <th className={sortKey === "matchup" ? "sorted" : ""} onClick={() => toggleSort("matchup")}>
                  Matchup
                </th>
                <th className={sortKey === "prob" ? "sorted" : ""} onClick={() => toggleSort("prob")}>
                  Home Win Prob
                </th>
                <th className={sortKey === "score" ? "sorted" : ""} onClick={() => toggleSort("score")}>
                  Score
                </th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((g) => (
                <GameRow key={g.game_id} game={g} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
