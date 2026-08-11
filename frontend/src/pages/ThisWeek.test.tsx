import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import { TeamsProvider } from "../context/TeamsContext";
import type { Game } from "../api/types";
import { ThisWeek } from "./ThisWeek";

vi.mock("../api/client");

const GAMES: Game[] = [
  {
    game_id: "2026_01_AAA_BBB",
    season: 2026,
    week: 1,
    home_team: "AAA",
    away_team: "BBB",
    home_score: null,
    away_score: null,
    game_date: "2026-09-10",
    prediction: { model_version: "logreg_v1", home_win_prob: 0.7, predicted_at: "now" },
  },
  {
    game_id: "2026_01_CCC_DDD",
    season: 2026,
    week: 1,
    home_team: "CCC",
    away_team: "DDD",
    home_score: null,
    away_score: null,
    game_date: "2026-09-10",
    prediction: { model_version: "logreg_v1", home_win_prob: 0.3, predicted_at: "now" },
  },
];

function renderThisWeek() {
  return render(
    <MemoryRouter>
      <TeamsProvider>
        <ThisWeek />
      </TeamsProvider>
    </MemoryRouter>
  );
}

describe("ThisWeek", () => {
  beforeEach(() => {
    vi.mocked(client.getGames).mockResolvedValue(GAMES);
    vi.mocked(client.getTeams).mockResolvedValue([]);
  });

  it("renders one row per game with win probabilities", async () => {
    renderThisWeek();

    await waitFor(() => expect(screen.getAllByText(/%$/)).toHaveLength(2));
    expect(screen.getByText("70.0%")).toBeInTheDocument();
    expect(screen.getByText("30.0%")).toBeInTheDocument();
  });

  it("sorts by win probability descending by default", async () => {
    renderThisWeek();
    await waitFor(() => expect(screen.getAllByRole("row")).toHaveLength(3)); // header + 2 rows

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("AAA");
    expect(rows[1]).toHaveTextContent("CCC");
  });

  it("shows an empty state when there are no games", async () => {
    vi.mocked(client.getGames).mockResolvedValue([]);
    renderThisWeek();

    await waitFor(() => expect(screen.getByText(/No games found/)).toBeInTheDocument());
  });

  it("shows an error state when the request fails", async () => {
    vi.mocked(client.getGames).mockRejectedValue(new Error("network down"));
    renderThisWeek();

    await waitFor(() => expect(screen.getByText(/Couldn't load games/)).toBeInTheDocument());
  });
});
