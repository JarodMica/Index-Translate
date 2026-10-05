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


MARKDOWN_EMPHASIS_RE = re.compile(r"[*_`]+")
# Judge models wrap the score line in Markdown emphasis and label it inconsistently;
# accept the common Chinese variants next to the original 评分/score spelling.
SCORE_LABEL = r"(?:最终)?(?:评分|得分|总分|score)"
SCORE_LINE_RE = re.compile(
    rf"^\s*{SCORE_LABEL}\s*[:：=]?\s*([+-]?\d+(?:\.\d+)?)", re.I
)
WHOLE_RESPONSE_RE = re.compile(r"(?:0(?:\.0+)?|0\.50*|1(?:\.0+)?)")


def strip_markdown_emphasis(text: str) -> str:
    """Drop Markdown emphasis/backtick markers so `**评分：1**` still parses.

    Only formatting characters are removed; digits and wording survive, so the
    original line can still be reported verbatim as the matched text.
    """
    return MARKDOWN_EMPHASIS_RE.sub("", text)


def parse_score(response: str) -> ParsedScore:
    """Apply score-line precedence, then text fallback, with zero for unparsed responses.

    Off-grid values (for example 0.7) keep their existing meaning: the response is
    surfaced as `nonstandard_fallback_0` and counted as 0.0, never rounded onto the grid.
    """
    allowed = {0.0, 0.5, 1.0}
    for line in response.split("\n"):
        match = SCORE_LINE_RE.match(strip_markdown_emphasis(line))
        if match:
            score = float(match.group(1))
            if score in allowed:
                return ParsedScore(score, "explicit_score_line", line)
            return ParsedScore(0.0, "nonstandard_fallback_0", line)
    text = response.strip()
    normalized_text = strip_markdown_emphasis(text)
    if WHOLE_RESPONSE_RE.fullmatch(normalized_text):
        return ParsedScore(float(normalized_text), "whole_response_fallback", text)
    # Legacy fallback is retained only for complete score tokens, never 0.1/10.
    for token, score in [("1", 1.0), ("0.5", 0.5), ("0", 0.0)]:
        if re.search(r"(?<![\d.])" + re.escape(token) + r"分", response):
            return ParsedScore(score, "whole_response_fallback", None)
    return ParsedScore(0.0, "nonstandard_fallback_0", None)
