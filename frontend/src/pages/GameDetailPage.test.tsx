import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import { TeamsProvider } from "../context/TeamsContext";
import type { GameDetail } from "../api/types";
import { GameDetailPage } from "./GameDetailPage";

vi.mock("../api/client");

const DETAIL: GameDetail = {
  game: {
    game_id: "2026_01_AAA_BBB",
    season: 2026,
    week: 1,
    home_team: "AAA",
    away_team: "BBB",
    home_score: null,
    away_score: null,
    game_date: "2026-09-10",
    prediction: null,
  },
  home_stats: {
    team_id: "AAA",
    season: 2025,
    points_for: 400,
    points_against: 300,
    epa_offense: 0.1,
    epa_defense: -0.05,
    turnover_margin: 5,
    yards_per_play: 5.8,
    win_pct: 0.7,
  },
  away_stats: {
    team_id: "BBB",
    season: 2025,
    points_for: 300,
    points_against: 350,
    epa_offense: -0.05,
    epa_defense: 0.02,
    turnover_margin: -3,
    yards_per_play: 5.1,
    win_pct: 0.4,
  },
  stats_season: 2025,
  feature_breakdown: {
    epa_offense_diff: 0.15,
    epa_defense_diff: -0.07,
    turnover_margin_diff: 8,
    win_pct_diff: 0.3,
    yards_per_play_diff: 0.7,
  },
  prediction: { model_version: "logreg_v1", home_win_prob: 0.68, predicted_at: "now" },
};

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={["/games/2026_01_AAA_BBB"]}>
      <TeamsProvider>
        <Routes>
          <Route path="/games/:gameId" element={<GameDetailPage />} />
        </Routes>
      </TeamsProvider>
    </MemoryRouter>
  );
}

describe("GameDetailPage", () => {
  beforeEach(() => {
    vi.mocked(client.getPrediction).mockResolvedValue(DETAIL);
    vi.mocked(client.getTeams).mockResolvedValue([]);
  });

  it("renders the win probability and feature breakdown", async () => {
    renderDetail();

    await waitFor(() => expect(screen.getByText("68.0%")).toBeInTheDocument());
    expect(screen.getByText("Why the model likes AAA")).toBeInTheDocument();
    expect(screen.getByText("30pp")).toBeInTheDocument();
  });

  it("renders season stats for both teams", async () => {
    renderDetail();

    await waitFor(() => expect(screen.getByText("2025 season stats")).toBeInTheDocument());
    expect(screen.getByText("70%")).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
  });
});
