"""Parse translation quality scores from Judge responses."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re


@dataclass(frozen=True)
class ParsedScore:
    score: float
    parse_status: str
    matched_text: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def parse_score(response: str) -> ParsedScore:
    """Apply score-line precedence, then text fallback, with zero for unparsed responses."""
    allowed = {0.0, 0.5, 1.0}
    for line in response.split("\n"):
        match = re.match(r"^\s*(?:评分|score)\s*[:：=]?\s*([+-]?\d+(?:\.\d+)?)", line, re.I)
        if match:
            score = float(match.group(1))
            if score in allowed:
                return ParsedScore(score, "explicit_score_line", line)
            return ParsedScore(0.0, "nonstandard_fallback_0", line)
    text = response.strip()
    if re.fullmatch(r"(?:0(?:\.0+)?|0\.50*|1(?:\.0+)?)", text):
        return ParsedScore(float(text), "whole_response_fallback", text)
    # Legacy fallback is retained only for complete score tokens, never 0.1/10.
    for token, score in [("1", 1.0), ("0.5", 0.5), ("0", 0.0)]:
        if re.search(r"(?<![\d.])" + re.escape(token) + r"分", response):
            return ParsedScore(score, "whole_response_fallback", None)
    return ParsedScore(0.0, "nonstandard_fallback_0", None)
