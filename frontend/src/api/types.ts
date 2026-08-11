export interface Team {
  team_id: string;
  name: string;
}

export interface SeasonStats {
  team_id: string;
  season: number;
  points_for: number | null;
  points_against: number | null;
  epa_offense: number | null;
  epa_defense: number | null;
  turnover_margin: number | null;
  yards_per_play: number | null;
  win_pct: number | null;
}

export interface Prediction {
  model_version: string;
  home_win_prob: number;
  predicted_at: string;
}

export interface Game {
  game_id: string;
  season: number;
  week: number;
  home_team: string;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  game_date: string | null;
  prediction: Prediction | null;
}

export interface FeatureBreakdown {
  epa_offense_diff: number | null;
  epa_defense_diff: number | null;
  turnover_margin_diff: number | null;
  win_pct_diff: number | null;
  yards_per_play_diff: number | null;
}

export interface GameDetail {
  game: Game;
  home_stats: SeasonStats | null;
  away_stats: SeasonStats | null;
  stats_season: number;
  feature_breakdown: FeatureBreakdown | null;
  prediction: Prediction | null;
}

export interface BacktestResult {
  id: number;
  model_version: string;
  test_season: number;
  accuracy: number | null;
  log_loss: number | null;
  brier_score: number | null;
  baseline_accuracy: number | null;
  n_games: number | null;
  run_at: string;
}
