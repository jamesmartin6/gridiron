import { Route, BrowserRouter, Routes } from "react-router-dom";
import { Nav } from "./components/Nav";
import { TeamsProvider } from "./context/TeamsContext";
import { BacktestPage } from "./pages/BacktestPage";
import { GameDetailPage } from "./pages/GameDetailPage";
import { ThisWeek } from "./pages/ThisWeek";

export default function App() {
  return (
    <BrowserRouter>
      <TeamsProvider>
        <div className="app-shell">
          <Nav />
          <Routes>
            <Route path="/" element={<ThisWeek />} />
            <Route path="/games/:gameId" element={<GameDetailPage />} />
            <Route path="/backtest" element={<BacktestPage />} />
          </Routes>
          <p className="footer-note">
            Predictions use each team's prior-season stats only — not a betting product.
          </p>
        </div>
      </TeamsProvider>
    </BrowserRouter>
  );
}
