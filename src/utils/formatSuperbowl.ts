// src/utils/formatSuperbowl.ts
import { SUPERBOWL } from "../config/superbowl";

export function formatSuperbowlEventLabel() {
  // Use this for event label/title (e.g. formatSuperbowlEventLabel() output)
  return `${SUPERBOWL.label} ${SUPERBOWL.roman}`;
}

export function formatSuperbowlTeamsLine() {
  // Away vs home team names; for standard matchup use formatMatchup.ts
  return `${SUPERBOWL.teams.away.name} vs ${SUPERBOWL.teams.home.name}`;
}
