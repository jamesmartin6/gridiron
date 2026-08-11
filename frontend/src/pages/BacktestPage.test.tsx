import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { BacktestResult } from "../api/types";
import { BacktestPage } from "./BacktestPage";

vi.mock("../api/client");

const RESULTS: BacktestResult[] = [
  {
    id: 1,
    model_version: "logreg_bt_2023",
    test_season: 2023,
    accuracy: 0.6,
    log_loss: 0.65,
    brier_score: 0.22,
    baseline_accuracy: 0.5,
    n_games: 272,
    run_at: "now",
  },
  {
    id: 2,
    model_version: "logreg_bt_2024",
    test_season: 2024,
    accuracy: 0.58,
    log_loss: 0.67,
    brier_score: 0.24,
    baseline_accuracy: 0.53,
    n_games: 272,
    run_at: "now",
  },
];

describe("BacktestPage", () => {
  beforeEach(() => {
    vi.mocked(client.getBacktestResults).mockResolvedValue(RESULTS);
  });

  it("renders summary tiles with averaged metrics", async () => {
    render(<BacktestPage />);

    await waitFor(() => expect(screen.getByText("59.0%")).toBeInTheDocument()); // avg accuracy
    expect(screen.getByText("51.5%")).toBeInTheDocument(); // avg baseline
  });

  it("renders one table row per backtest result", async () => {
    render(<BacktestPage />);

    await waitFor(() => expect(screen.getByText("logreg_bt_2023")).toBeInTheDocument());
    expect(screen.getByText("logreg_bt_2024")).toBeInTheDocument();
  });

  it("shows an empty state with no results", async () => {
    vi.mocked(client.getBacktestResults).mockResolvedValue([]);
    render(<BacktestPage />);

    await waitFor(() => expect(screen.getByText(/No backtest results yet/)).toBeInTheDocument());
  });
});
