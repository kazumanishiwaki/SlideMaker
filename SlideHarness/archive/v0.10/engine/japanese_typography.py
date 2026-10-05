from __future__ import annotations

"""Deterministic Japanese/Latin typography helpers for slide layout and QA.

The module deliberately does not rewrite semantic copy.  It estimates the physical
footprint of text, selects a safe display font size, and diagnoses line-break
patterns after render.  Any semantic rewrite remains an upstream decision.
"""

from dataclasses import dataclass
from typing import Any, Iterable
import math
import re
import unicodedata

# Basic kinsoku rules.  The sets are intentionally conservative: false positives
# are less damaging than silently accepting obviously broken Japanese line starts.
PROHIBITED_LINE_START = set(
    "、。，．・：；？！ー〜～…‥)]｝〕〉》」』】〙〗〟’”»％%℃°々ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ"
)
PROHIBITED_LINE_END = set("([｛〔〈《「『【〘〖〝‘“«￥¥＄$#")
OPEN_BRACKETS = set("（([｛〔〈《「『【〘〖〝‘“«")
CLOSE_BRACKETS = set("）)]｝〕〉》」』】〙〗〟’”»")
PARTICLES = ("を", "が", "に", "へ", "で", "と", "の", "は", "も", "や", "か", "へ")
UNITS = (
    "円", "%", "％", "人", "名", "件", "個", "回", "台", "枚", "年", "月", "日", "時", "分", "秒",
    "GB", "MB", "KB", "TB", "px", "pt", "cm", "mm", "km", "kg", "g", "mL", "L", "倍", "社", "店舗",
)
LATIN_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+_:/-]*$")
CJK_RE = re.compile(r"[\u3000-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or "")).replace("\u00a0", " ")


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", normalize_text(text))


def is_cjk(char: str) -> bool:
    return bool(char and CJK_RE.match(char))


def glyph_units(char: str) -> float:
    """Return a rough em-width used only for deterministic fit estimation."""
    if not char:
        return 0.0
    if char in "\n\r":
        return 0.0
    if char.isspace():
        return 0.28
    if is_cjk(char):
        return 1.0
    category = unicodedata.category(char)
    if category.startswith("P"):
        return 0.45
    if char.isdigit():
        return 0.58
    if "A" <= char <= "Z":
        return 0.64
    if "a" <= char <= "z":
        return 0.52
    return 0.72


def text_units(text: str) -> float:
    return sum(glyph_units(ch) for ch in normalize_text(text))


def _tokens_for_wrap(text: str) -> list[str]:
    """Split text into Latin words and single Japanese glyphs without losing punctuation."""
    text = normalize_text(text)
    tokens: list[str] = []
    latin: list[str] = []

    def flush() -> None:
        if latin:
            tokens.append("".join(latin))
            latin.clear()

    for ch in text:
        if ch in "\r\n":
            flush(); tokens.append("\n")
        elif ch.isspace():
            flush(); tokens.append(" ")
        elif ord(ch) < 128 and (ch.isalnum() or ch in ".+_:/-%"):
            latin.append(ch)
        else:
            flush(); tokens.append(ch)
    flush()
    return tokens




def rebalance_japanese_lines(lines: list[str]) -> list[str]:
    """Move a short trailing noun fragment when the next line begins with a particle.

    This is intentionally conservative and only affects display wrapping. It never
    changes semantic text. Example::

        テンプレートの個性を、内容 / に合わせて継承する
        -> テンプレートの個性を、 / 内容に合わせて継承する
    """
    out = list(lines)
    for index in range(1, len(out)):
        previous = out[index - 1].rstrip()
        current = out[index].lstrip()
        if not previous or not current:
            continue
        if not any(current.startswith(particle) and len(current) > len(particle) for particle in PARTICLES):
            continue
        # Move the trailing CJK phrase from the preceding line. Limit long runs so
        # the first line does not collapse and the second line stays readable.
        match = re.search(r"([\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]{2,8})$", previous)
        if not match:
            continue
        run = match.group(1)
        carry = run if len(run) <= 4 else run[-3:]
        new_previous = previous[:-len(carry)].rstrip()
        new_current = carry + current
        if len(compact_text(new_previous)) < 4:
            continue
        # Avoid replacing one severe imbalance with another.
        old_gap = abs(text_units(previous) - text_units(current))
        new_gap = abs(text_units(new_previous) - text_units(new_current))
        if new_gap <= old_gap + 1.5:
            out[index - 1] = new_previous
            out[index] = new_current
    return out

def estimate_lines(text: str, width_in: float, font_pt: float) -> list[str]:
    """Estimate PowerPoint wrapping while respecting basic Japanese kinsoku."""
    width_pt = max(1.0, float(width_in) * 72.0)
    # Most UI fonts occupy roughly 0.98em for CJK.  A small safety factor avoids
    # overestimating capacity and reducing actual-render overflow.
    capacity = max(1.0, width_pt / max(1.0, float(font_pt) * 1.10))
    tokens = _tokens_for_wrap(text)
    lines: list[str] = []
    current = ""
    used = 0.0

    def commit() -> None:
        nonlocal current, used
        if current or not lines:
            lines.append(current.rstrip())
        current = ""; used = 0.0

    for token in tokens:
        if token == "\n":
            commit(); continue
        if token == " " and not current:
            continue
        weight = text_units(token)
        if current and used + weight > capacity:
            # A prohibited line-start glyph remains with the previous line when
            # possible.  Conversely, avoid ending the previous line with an opener.
            if token and token[0] in PROHIBITED_LINE_START and current:
                current += token
                used += weight
                commit()
                continue
            if current[-1] in PROHIBITED_LINE_END and len(current) >= 2:
                carry = current[-1]
                current = current[:-1]
                lines.append(current.rstrip())
                current = carry + token
                used = text_units(current)
                continue
            commit()
        current += token
        used += weight
    if current or not lines:
        commit()
    return rebalance_japanese_lines(lines)




def _balanced_title_lines(
    text: str,
    *,
    width_in: float,
    font_pt: float,
    max_lines: int,
) -> list[str] | None:
    """Return a conservative display-only title split when greedy wrap over-fragments.

    ``fit_font_size`` chooses the physical font size using the full semantic box.
    ``prepare_display_text`` then applies a render safety margin.  Near a wrapping
    boundary that safety margin can turn a valid two-line title into three lines,
    often leaving a one-character orphan.  This helper searches token boundaries
    for a balanced two-line split while allowing only a small estimator tolerance.

    The helper is intentionally limited to two-line title roles. It does not change
    semantic text, split Latin tokens, or permit prohibited/particle line starts.
    Actual-render QA remains authoritative for physical overflow.
    """
    if int(max_lines) != 2 or "\n" in str(text):
        return None
    tokens = [token for token in _tokens_for_wrap(text) if token != "\n"]
    if len(tokens) < 2:
        return None
    capacity = max(1.0, float(width_in) * 72.0 / max(1.0, float(font_pt) * 1.10))
    # The estimator is deliberately conservative. A modest tolerance allows a
    # split that fits the real box selected by ``fit_font_size`` without accepting
    # a materially overfull line.
    tolerated = capacity * 1.18
    best: tuple[float, list[str]] | None = None
    for index in range(1, len(tokens)):
        left = "".join(tokens[:index]).rstrip()
        right = "".join(tokens[index:]).lstrip()
        if not left or not right:
            continue
        left_compact = compact_text(left)
        right_compact = compact_text(right)
        if not left_compact or not right_compact:
            continue
        if right_compact[0] in PROHIBITED_LINE_START or left_compact[-1] in PROHIBITED_LINE_END:
            continue
        if any(right_compact.startswith(particle) and len(right_compact) > len(particle) for particle in PARTICLES):
            continue
        left_units = text_units(left)
        right_units = text_units(right)
        if max(left_units, right_units) > tolerated:
            continue
        # Strongly penalise overflow, then favour balanced visual widths.  A tiny
        # punctuation bonus keeps natural clause boundaries when scores are close.
        overflow = max(0.0, left_units - capacity) + max(0.0, right_units - capacity)
        imbalance = abs(left_units - right_units)
        punctuation_bonus = -0.20 if left_compact[-1] in "、。，．：；？！" else 0.0
        short_penalty = 6.0 if min(len(left_compact), len(right_compact)) <= 3 else 0.0
        score = overflow * 8.0 + imbalance + punctuation_bonus + short_penalty
        candidate = [left, right]
        if best is None or score < best[0]:
            best = (score, candidate)
    return best[1] if best is not None else None

def render_safety_factor(role: str) -> float:
    """Return the deterministic width safety used by fitting and display wrap."""
    return {
        "title": .87,
        "item_title": .88,
        "subtitle": .90,
        "item_body": .88,
        "body": .90,
        "caption": .92,
    }.get(role, .91)


def prepare_display_text(
    text: str,
    *,
    width_in: float,
    font_pt: float,
    role: str,
    max_lines: int,
) -> str:
    """Insert deterministic display-only line breaks with a render safety margin.

    PowerPoint/LibreOffice use the actual installed font and may wrap slightly
    earlier than our platform-neutral estimator.  The original semantic string is
    never changed; only the render string receives explicit breaks. Existing
    author paragraph breaks remain paragraph boundaries.
    """
    original = str(text or "")
    if not original.strip():
        return original
    safety = render_safety_factor(role)
    rendered: list[str] = []
    changed = False
    paragraphs = original.split("\n")
    for paragraph in paragraphs:
        if not paragraph:
            rendered.append("")
            continue
        lines = estimate_lines(paragraph, max(.2, width_in * safety), font_pt)
        rendered.extend(lines)
        changed = changed or len(lines) > 1
    # Never manufacture overflow. If conservative wrapping needs more lines than
    # the fitted box permits, keep PowerPoint's natural wrap and let actual-render
    # QA decide whether a layout or copy change is required.
    visible_lines = sum(1 for line in rendered if line or len(rendered) == 1)
    if changed and visible_lines <= max(1, int(max_lines)):
        if role in {"title", "item_title"} and len(rendered) >= 2:
            compact_lines = [compact_text(line) for line in rendered if compact_text(line)]
            widths = [max(.01, text_units(line)) for line in rendered if compact_text(line)]
            last = compact_lines[-1] if compact_lines else ""
            ratio = widths[-1] / max(widths) if widths else 1.0
            particle_start = any(
                last.startswith(particle) and len(last) > len(particle)
                for particle in PARTICLES
            )
            if len(last) <= 3 or ratio < .34 or particle_start:
                balanced = _balanced_title_lines(
                    original, width_in=max(.2, width_in),
                    font_pt=font_pt, max_lines=max_lines,
                )
                if balanced is not None:
                    return "\n".join(balanced)
        return "\n".join(rendered)
    if role in {"title", "item_title"} and visible_lines > max(1, int(max_lines)):
        balanced = _balanced_title_lines(
            original, width_in=max(.2, width_in),
            font_pt=font_pt, max_lines=max_lines,
        )
        if balanced is not None:
            return "\n".join(balanced)
    return original


def line_capacity(box_height_in: float, font_pt: float, *, line_height: float = 1.26) -> int:
    line_in = max(0.01, float(font_pt) / 72.0 * float(line_height))
    return max(1, int(math.floor(max(0.01, float(box_height_in)) / line_in)))


ROLE_RULES: dict[str, dict[str, float | int]] = {
    # Presentation-first defaults. If copy cannot fit at these sizes the engine
    # must change copy or layout rather than silently producing tiny text.
    "title": {"min_pt": 28.0, "max_lines": 2, "line_height": 1.13},
    "subtitle": {"min_pt": 16.0, "max_lines": 3, "line_height": 1.22},
    "item_title": {"min_pt": 18.0, "max_lines": 2, "line_height": 1.18},
    "item_body": {"min_pt": 14.0, "max_lines": 9, "line_height": 1.28},
    "body": {"min_pt": 15.0, "max_lines": 11, "line_height": 1.28},
    "number": {"min_pt": 12.0, "max_lines": 1, "line_height": 1.0},
    "kpi_value": {"min_pt": 28.0, "max_lines": 1, "line_height": 1.0},
    "caption": {"min_pt": 10.0, "max_lines": 3, "line_height": 1.2},
}


@dataclass(frozen=True)
class FitResult:
    font_pt: float
    estimated_lines: list[str]
    line_count: int
    max_lines: int
    fits: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "font_pt": round(self.font_pt, 2),
            "estimated_lines": self.estimated_lines,
            "line_count": self.line_count,
            "max_lines": self.max_lines,
            "fits": self.fits,
        }


def fit_font_size(
    text: str,
    *,
    width_in: float,
    height_in: float,
    preferred_pt: float,
    role: str,
    min_pt: float | None = None,
    max_lines: int | None = None,
) -> FitResult:
    rule = ROLE_RULES.get(role, ROLE_RULES["body"])
    lower = float(min_pt if min_pt is not None else rule["min_pt"])
    upper = max(lower, float(preferred_pt))
    line_height = float(rule["line_height"])
    role_max = int(max_lines if max_lines is not None else rule["max_lines"])

    def inspect(size: float) -> tuple[list[str], int, bool]:
        lines = estimate_lines(text, width_in, size)
        physical_max = line_capacity(height_in, size, line_height=line_height)
        allowed = max(1, min(role_max, physical_max))
        balanced = True
        # When the author supplied explicit line breaks, preserve that semantic choice.
        # Otherwise avoid accepting a font size that leaves a one-to-three character
        # orphan on the last line merely because it is technically inside the box.
        if len(lines) >= 2 and "\n" not in str(text):
            widths = [max(0.01, text_units(line)) for line in lines]
            ratio = widths[-1] / max(widths)
            compact_last = compact_text(lines[-1])
            threshold = 0.34 if role in {"title", "item_title", "kpi_value"} else 0.24
            if len(compact_last) <= 3 or ratio < threshold:
                balanced = False
        return lines, allowed, len(lines) <= allowed and balanced

    lines, allowed, ok = inspect(upper)
    if ok:
        return FitResult(upper, lines, len(lines), allowed, True)

    # Binary search is deterministic and avoids repeated one-point shrink loops.
    lo, hi = lower, upper
    best: tuple[float, list[str], int] | None = None
    for _ in range(18):
        mid = (lo + hi) / 2.0
        mid_lines, mid_allowed, mid_ok = inspect(mid)
        if mid_ok:
            best = (mid, mid_lines, mid_allowed)
            lo = mid
        else:
            hi = mid
    if best is not None:
        size, lines, allowed = best
        return FitResult(round(size, 2), lines, len(lines), allowed, True)
    lines, allowed, ok = inspect(lower)
    return FitResult(lower, lines, len(lines), allowed, ok)


def _line_text(line: Any) -> str:
    if isinstance(line, str):
        return line.strip()
    if isinstance(line, Iterable):
        return " ".join(str(getattr(item, "get", lambda *_: "")("text", "")) for item in line).strip()
    return str(line or "").strip()


def diagnose_rendered_lines(lines: list[Any], render_text: str, role: str | None = None) -> list[tuple[str, str, dict[str, Any]]]:
    """Return QA issues using rendered line/token order from PDF bbox extraction."""
    issues: list[tuple[str, str, dict[str, Any]]] = []
    if not lines:
        return issues
    texts = [_line_text(line) for line in lines]
    normalized = [compact_text(text) for text in texts]
    if role == "title" and len(lines) > 2:
        issues.append(("TITLE_MAX_LINES", "blocking", {"actual_lines": len(lines), "max_lines": 2, "lines": texts}))

    if len(lines) >= 2:
        last = normalized[-1]
        longest = max((len(value) for value in normalized), default=0)
        if 0 < len(last) <= 3:
            issues.append(("JAPANESE_SHORT_LAST_LINE", "review", {"last_line": texts[-1], "lines": texts}))
        elif 0 < len(last) <= 6 and longest and len(last) / longest < 0.35:
            issues.append(("JAPANESE_UNBALANCED_LAST_LINE", "warning", {"last_line": texts[-1], "lines": texts}))

    for index in range(1, len(texts)):
        previous = normalized[index - 1]
        current = normalized[index]
        if not previous or not current:
            continue
        if current[0] in PROHIBITED_LINE_START:
            issues.append(("JAPANESE_PROHIBITED_LINE_START", "blocking", {"line": index + 1, "token": texts[index], "lines": texts}))
        if previous[-1] in PROHIBITED_LINE_END:
            issues.append(("JAPANESE_PROHIBITED_LINE_END", "blocking", {"line": index, "token": texts[index - 1], "lines": texts}))
        if any(current.startswith(particle) and len(current) > 1 for particle in PARTICLES) and not previous.endswith(("。", "、", "：", ":", "；", ";")):
            issues.append(("JAPANESE_PARTICLE_LINE_START", "warning", {"line": index + 1, "starts_with": texts[index], "lines": texts}))
        if current[0] in CLOSE_BRACKETS:
            issues.append(("JAPANESE_ORPHAN_CLOSE_BRACKET", "blocking", {"line": index + 1, "token": texts[index], "lines": texts}))
        if previous[-1] in OPEN_BRACKETS:
            issues.append(("JAPANESE_ORPHAN_OPEN_BRACKET", "blocking", {"line": index, "token": texts[index - 1], "lines": texts}))
        if re.search(r"\d$", previous) and any(current.startswith(unit) for unit in UNITS):
            issues.append(("NUMBER_UNIT_SPLIT", "blocking", {"line": index + 1, "previous": texts[index - 1], "current": texts[index], "lines": texts}))

    # Latin terms are token-sensitive, so inspect the first/last rendered tokens if available.
    for index in range(1, len(lines)):
        prev_line = lines[index - 1]
        cur_line = lines[index]
        if not isinstance(prev_line, list) or not isinstance(cur_line, list) or not prev_line or not cur_line:
            continue
        prev = compact_text(str(prev_line[-1].get("text", "")))
        cur = compact_text(str(cur_line[0].get("text", "")))
        if LATIN_TOKEN.match(prev or "") and LATIN_TOKEN.match(cur or ""):
            pair = f"{prev} {cur}"
            if pair in normalize_text(render_text):
                issues.append(("LATIN_TERM_SPLIT", "warning", {"line": index + 1, "term": pair, "lines": texts}))
    # Remove exact duplicate diagnoses produced by overlapping bracket/kinsoku rules.
    deduped: list[tuple[str, str, dict[str, Any]]] = []
    seen: set[tuple[str, int | None, str | None]] = set()
    for code, severity, detail in issues:
        key = (code, detail.get("line"), detail.get("token") or detail.get("term") or detail.get("last_line"))
        if key in seen:
            continue
        seen.add(key); deduped.append((code, severity, detail))
    return deduped
