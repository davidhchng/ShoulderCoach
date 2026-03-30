export interface DecisionMeta {
  abbr: string;  // short label shown on card instead of emoji
  color: string;
}

export const DECISION_META: Record<string, DecisionMeta> = {
  foul_up_3:    { abbr: "F+3", color: "text-orange-400" },
  timeout:      { abbr: "TO",  color: "text-yellow-400" },
  hack_a_player:{ abbr: "HAP", color: "text-red-400"    },
  two_for_one:  { abbr: "2:1", color: "text-blue-400"   },
  zone_vs_man:  { abbr: "DEF", color: "text-green-400"  },
  pull_starters:{ abbr: "GBG", color: "text-purple-400" },
  press:        { abbr: "PRS", color: "text-teal-400"   },
  three_vs_two: { abbr: "3v2", color: "text-pink-400"   },
};

export function getDecisionMeta(type: string): DecisionMeta {
  return DECISION_META[type] ?? { abbr: "?", color: "text-orange-400" };
}
