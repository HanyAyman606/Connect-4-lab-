from __future__ import annotations

#Monotonically map any raw heuristic score into the open interval (-1, 1).
def _normalize(raw_score: float, scale: float) -> float:
    return raw_score / (scale + abs(raw_score))
