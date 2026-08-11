import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getTeams } from "../api/client";

const TeamsContext = createContext<Record<string, string>>({});

export function TeamsProvider({ children }: { children: ReactNode }) {
  const [names, setNames] = useState<Record<string, string>>({});

  useEffect(() => {
    getTeams()
      .then((teams) => {
        const map: Record<string, string> = {};
        for (const t of teams) map[t.team_id] = t.name;
        setNames(map);
      })
      .catch(() => {
        // Non-critical: pages fall back to showing the raw team code.
      });
  }, []);

  return <TeamsContext.Provider value={names}>{children}</TeamsContext.Provider>;
}

export function useTeamName(teamId: string): string {
  const names = useContext(TeamsContext);
  return names[teamId] ?? teamId;
}
