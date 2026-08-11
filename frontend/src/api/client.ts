import type { BacktestResult, Game, GameDetail, SeasonStats, Team } from "./types";

const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  const res = await fetch(url.toString());
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText);
  }
  return (await res.json()) as T;
}

export function getTeams(): Promise<Team[]> {
  return request<Team[]>("/teams");
}

export function getTeamStats(teamId: string, season: number): Promise<SeasonStats> {
  return request<SeasonStats>(`/teams/${teamId}/stats`, { season });
}

export function getGames(season?: number, week?: number): Promise<Game[]> {
  return request<Game[]>("/games", { season, week });
}

export function getPrediction(gameId: string): Promise<GameDetail> {
  return request<GameDetail>(`/predictions/${gameId}`);
}

export function getBacktestResults(): Promise<BacktestResult[]> {
  return request<BacktestResult[]>("/backtest");
}

export { ApiError };
