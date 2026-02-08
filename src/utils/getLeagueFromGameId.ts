// src/utils/getLeagueFromGameId.ts
import gameIdToLeague from "../config/gameIdToLeague.json";

export function getLeagueFromGameId(gameId: string): string | null {
  return (gameIdToLeague as Record<string, string>)[gameId] ?? null;
}

export function isNFLGameId(gameId: string): boolean {
  return getLeagueFromGameId(gameId) === "NFL";
}
