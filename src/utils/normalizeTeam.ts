// src/utils/normalizeTeam.ts

export function normalizeTeamName(name: string) {
  return name.replace(/\s+/g, " ").trim();
}

export function sameTeamName(a: string, b: string) {
  return normalizeTeamName(a).toLowerCase() === normalizeTeamName(b).toLowerCase();
}
