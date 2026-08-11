import { NavLink } from "react-router-dom";

export function Nav() {
  return (
    <div className="top-nav">
      <div className="brand">
        <span className="mark">🏈</span>
        <h1>Gridiron</h1>
        <span className="tag">NFL win probability, from last season's stats</span>
      </div>
      <nav className="nav-links">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
          This Week
        </NavLink>
        <NavLink to="/backtest" className={({ isActive }) => (isActive ? "active" : "")}>
          Model Accuracy
        </NavLink>
      </nav>
    </div>
  );
}
