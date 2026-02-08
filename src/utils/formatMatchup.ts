// src/utils/formatMatchup.ts
import { SUPERBOWL } from "../config/superbowl";

type Options = {
  useAbbreviations?: boolean;
  separator?: string;
};

export function formatSuperbowlMatchup(opts: Options = {}) {
  const { useAbbreviations = false, separator = " vs " } = opts;

  const left = useAbbreviations
    ? SUPERBOWL.teams.home.abbreviation
    : SUPERBOWL.teams.home.name;

  const right = useAbbreviations
    ? SUPERBOWL.teams.away.abbreviation
    : SUPERBOWL.teams.away.name;

  return `${left}${separator}${right}`;
}
