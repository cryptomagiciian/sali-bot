// src/config/superbowl.ts

export type Team = {
  name: string;
  city: string;
  abbreviation: string;
  conference?: "AFC" | "NFC";
};

export const SUPERBOWL = {
  label: "Super Bowl",
  roman: "XLIX",
  teams: {
    home: {
      name: "New England Patriots",
      city: "New England",
      abbreviation: "NE",
      conference: "AFC",
    } as Team,
    away: {
      name: "Seattle Seahawks",
      city: "Seattle",
      abbreviation: "SEA",
      conference: "NFC",
    } as Team,
  },
} as const;

export const SUPERBOWL_TEAM_NAMES = [
  SUPERBOWL.teams.home.name,
  SUPERBOWL.teams.away.name,
] as const;

export function isSuperbowlTeamName(teamName: string): boolean {
  const t = teamName.trim().toLowerCase();
  return SUPERBOWL_TEAM_NAMES.some((n) => n.toLowerCase() === t);
}
