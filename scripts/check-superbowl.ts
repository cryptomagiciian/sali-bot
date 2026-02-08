import { formatSuperbowlMatchup } from "../src/utils/formatMatchup";
import { formatSuperbowlEventLabel } from "../src/utils/formatSuperbowl";

// Standard UI: event label + matchup (use this pattern everywhere)
const header = `${formatSuperbowlEventLabel()}: ${formatSuperbowlMatchup()}`;
console.log(header);
console.log(formatSuperbowlEventLabel());
console.log(formatSuperbowlMatchup());
console.log(formatSuperbowlMatchup({ useAbbreviations: true }));
