"""Presentation-only SVG rendering for the terminal-style profile card.

Takes already-normalized data (CardData) and produces a self-contained SVG
string. Never reads config.yml or performs network calls - that separation
is what keeps this module "exclusively" about visual generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.sax.saxutils import escape as _escape

MARGIN = 32
LINE_HEIGHT = 20
SECTION_GAP = 24
SECTION_LABEL_HEIGHT = 24

# (svg_fragment_or_None, new_y)
SectionResult = tuple


@dataclass
class CardData:
    theme: dict
    name: str
    username: str
    title: str
    description: str
    status: dict
    current: list
    stats: dict
    languages: list
    activity: dict | None
    stack: dict
    featured: dict | None
    journey: list
    organizations: list
    generated_at: str


def generate_svg(card: CardData) -> str:
    theme = card.theme
    x = MARGIN
    width = theme["width"] - 2 * MARGIN
    y = MARGIN

    fragments = []
    header, y = build_header(card, x, y, width)
    fragments.append(header)

    for builder in (
        build_status_section,
        build_stats_section,
        build_languages_section,
        build_activity_section,
        build_stack_section,
        build_current_section,
        build_featured_section,
        build_journey_section,
        build_organizations_section,
    ):
        frag, y = builder(card, x, y, width)
        if frag:
            fragments.append(frag)

    footer, y = build_footer(card, x, y, width)
    fragments.append(footer)

    return _wrap_svg(total_height=y + MARGIN, theme=theme, body="".join(fragments))


def build_header(card: CardData, x: int, y: int, width: int) -> SectionResult:
    theme = card.theme
    frag = [
        _text(x, y + 12, f"SYSTEM PROFILE :: {card.username.upper()}", size=12,
              color=theme["accent_secondary"], weight="bold"),
    ]
    y += 30

    frag.append(_text(x, y + 20, card.name, size=24, color=theme["foreground"], weight="bold"))
    y += 32

    frag.append(_text(x, y + 12, card.title.upper(), size=12, color=theme["muted"]))
    y += 22

    if card.description:
        for line in _wrap_text(card.description, max_chars=95):
            frag.append(_text(x, y + 10, line, size=12, color=theme["muted"]))
            y += 16
        y += 4

    y += 8
    frag.append(_hline(x, y, width, theme["accent"]))
    y += SECTION_GAP

    return "".join(frag), y


def build_status_section(card: CardData, x: int, y: int, width: int) -> SectionResult:
    theme = card.theme
    status = card.status
    if not status:
        return None, y

    frag = []
    label, y = _section_label(x, y, "> system.status", theme)
    frag.append(label)

    rows = [
        ("STATUS", status.get("status", "ONLINE")),
        ("USER", status.get("user", "")),
        ("ROLE", status.get("role", "")),
        ("BUILD", status.get("build", "")),
    ]
    if status.get("mode"):
        rows.append(("MODE", status["mode"]))

    for label_text, value in rows:
        frag.append(_kv_text(x + 8, y + 13, label_text, value, theme))
        y += LINE_HEIGHT
    y += SECTION_GAP

    return "".join(frag), y


def build_stats_section(card: CardData, x: int, y: int, width: int) -> SectionResult:
    theme = card.theme
    stats = card.stats
    if not stats:
        return None, y

    frag = []
    label, y = _section_label(x, y, "> github.stats", theme)
    frag.append(label)

    rows = [
        ("REPOSITORIES", str(stats.get("public_repos", 0))),
        ("FOLLOWERS", str(stats.get("followers", 0))),
        ("STARS", str(stats.get("stars", 0))),
    ]
    if stats.get("contributions") is not None:
        rows.append(("CONTRIBUTIONS", str(stats["contributions"])))

    for label_text, value in rows:
        frag.append(_kv_text(x + 8, y + 13, label_text, value, theme))
        y += LINE_HEIGHT
    y += SECTION_GAP

    return "".join(frag), y


def build_languages_section(card: CardData, x: int, y: int, width: int) -> SectionResult:
    theme = card.theme
    languages = card.languages
    if not languages:
        return None, y

    frag = []
    label, y = _section_label(x, y, "> system.languages", theme)
    frag.append(label)

    name_col = 130
    pct_col = 50
    bar_x = x + 8 + name_col + pct_col
    bar_width = width - 8 - name_col - pct_col

    for lang in languages:
        frag.append(_text(x + 8, y + 13, lang.name.upper(), size=12, color=theme["foreground"]))
        frag.append(_text(x + 8 + name_col, y + 13, f"{lang.percent}%", size=12, color=theme["muted"]))
        frag.append(_bar(bar_x, y + 4, bar_width, lang.percent, theme))
        y += LINE_HEIGHT
    y += SECTION_GAP

    return "".join(frag), y


def build_activity_section(card: CardData, x: int, y: int, width: int) -> SectionResult:
    theme = card.theme
    activity = card.activity
    if not activity:
        return None, y

    frag = []
    label, y = _section_label(x, y, "> github.activity", theme)
    frag.append(label)

    weeks = activity.get("weeks", [])
    total = activity.get("total", 0)
    frag.append(_text(x + 8, y + 13, f"TOTAL: {total} (last {len(weeks)}w)", size=12, color=theme["muted"]))
    y += LINE_HEIGHT + 6

    if total <= 0:
        frag.append(_text(x + 8, y + 13, "NO RECENT ACTIVITY LOGGED", size=12, color=theme["muted"]))
        y += LINE_HEIGHT
    else:
        cell, gap = 10, 3
        grid_x, grid_y = x + 8, y
        for week_idx, week in enumerate(weeks):
            for day in week:
                cx = grid_x + week_idx * (cell + gap)
                cy = grid_y + day.get("weekday", 0) * (cell + gap)
                frag.append(_activity_cell(cx, cy, cell, day.get("count", 0), theme))
        y += 7 * (cell + gap)
    y += SECTION_GAP

    return "".join(frag), y


def build_stack_section(card: CardData, x: int, y: int, width: int) -> SectionResult:
    theme = card.theme
    stack = card.stack
    if not stack:
        return None, y

    frag = []
    label, y = _section_label(x, y, "> system.stack", theme)
    frag.append(label)

    for category, items in stack.items():
        frag.append(_text(x + 8, y + 13, category.upper(), size=12, color=theme["muted"]))
        y += LINE_HEIGHT
        frag.append(_text(x + 8, y + 13, " · ".join(items), size=13, color=theme["foreground"]))
        y += LINE_HEIGHT
    y += SECTION_GAP

    return "".join(frag), y


def build_current_section(card: CardData, x: int, y: int, width: int) -> SectionResult:
    theme = card.theme
    items = card.current
    if not items:
        return None, y

    frag = []
    label, y = _section_label(x, y, "> current.process", theme)
    frag.append(label)

    for i, item in enumerate(items, start=1):
        frag.append(_text(x + 8, y + 13, f"[{i:02d}] {item.upper()}", size=12, color=theme["foreground"]))
        y += LINE_HEIGHT
    y += SECTION_GAP

    return "".join(frag), y


def build_featured_section(card: CardData, x: int, y: int, width: int) -> SectionResult:
    theme = card.theme
    featured = card.featured
    if not featured:
        return None, y

    frag = []
    label, y = _section_label(x, y, "> featured.project", theme)
    frag.append(label)

    frag.append(_text(x + 8, y + 14, featured["name"], size=14, color=theme["foreground"], weight="bold"))
    y += 22

    if featured.get("description"):
        for line in _wrap_text(featured["description"], max_chars=90):
            frag.append(_text(x + 8, y + 10, line, size=12, color=theme["muted"]))
            y += 16
        y += 4

    if featured.get("language"):
        frag.append(_text(x + 8, y + 13, featured["language"], size=12, color=theme["accent_secondary"]))
        y += LINE_HEIGHT

    frag.append(_kv_text(x + 8, y + 13, "STARS", str(featured.get("stars", 0)), theme, label_chars=8))
    y += LINE_HEIGHT
    y += SECTION_GAP

    return "".join(frag), y


def build_journey_section(card: CardData, x: int, y: int, width: int) -> SectionResult:
    theme = card.theme
    journey = card.journey
    if not journey:
        return None, y

    frag = []
    label, y = _section_label(x, y, "> profile.journey", theme)
    frag.append(label)

    for entry in journey:
        frag.append(_kv_text(x + 8, y + 13, str(entry["year"]), entry["focus"], theme, label_chars=8))
        y += LINE_HEIGHT
    y += SECTION_GAP

    return "".join(frag), y


def build_organizations_section(card: CardData, x: int, y: int, width: int) -> SectionResult:
    theme = card.theme
    orgs = [o for o in (card.organizations or []) if o.get("display", True)]
    if not orgs:
        return None, y

    frag = []
    label, y = _section_label(x, y, "> profile.organizations", theme)
    frag.append(label)

    for org in orgs:
        frag.append(_text(x + 8, y + 13, org.get("name", ""), size=13, color=theme["foreground"], weight="bold"))
        y += LINE_HEIGHT
        if org.get("description"):
            for line in _wrap_text(org["description"], max_chars=90):
                frag.append(_text(x + 16, y + 10, line, size=12, color=theme["muted"]))
                y += 16
        if org.get("url"):
            frag.append(_text(x + 16, y + 10, org["url"], size=11, color=theme["accent_secondary"]))
            y += 16
        y += 6
    y += SECTION_GAP - 6

    return "".join(frag), y


def build_footer(card: CardData, x: int, y: int, width: int) -> SectionResult:
    theme = card.theme
    frag = [_hline(x, y, width, theme["accent"])]
    y += 24

    frag.append(_text(x + width / 2, y + 12, "[ SYSTEM READY ]", size=12,
                       color=theme["accent"], weight="bold", anchor="middle"))
    y += 20

    frag.append(_text(x + width / 2, y + 10, card.generated_at, size=10,
                       color=theme["muted"], anchor="middle"))
    y += 20

    return "".join(frag), y


def _wrap_svg(total_height: int, theme: dict, body: str) -> str:
    width = theme["width"]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height}" '
        f'viewBox="0 0 {width} {total_height}">'
        f'<style>text {{ font-family: {theme["font_family"]}; }}</style>'
        f'<rect x="0" y="0" width="{width}" height="{total_height}" fill="{theme["background"]}" />'
        f'<rect x="3" y="3" width="{width - 6}" height="{total_height - 6}" fill="none" '
        f'stroke="{theme["muted"]}" stroke-opacity="0.4" stroke-width="1" rx="6" />'
        f"{body}"
        f"</svg>"
    )


def _text(x, y, content, size=13, color="#ffffff", weight="normal", anchor="start") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
        f'fill="{color}" text-anchor="{anchor}">{_escape(str(content))}</text>'
    )


def _kv_text(x, y, label, value, theme, label_chars=14, size=12) -> str:
    padded = f"{label:<{label_chars}}"
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}">'
        f'<tspan fill="{theme["muted"]}">{_escape(padded)}</tspan>'
        f'<tspan fill="{theme["foreground"]}">{_escape(str(value))}</tspan>'
        f"</text>"
    )


def _section_label(x, y, text, theme) -> tuple[str, int]:
    return _text(x, y + 13, text, size=13, color=theme["accent_secondary"], weight="bold"), y + SECTION_LABEL_HEIGHT


def _hline(x, y, width, color) -> str:
    return f'<line x1="{x}" y1="{y}" x2="{x + width}" y2="{y}" stroke="{color}" stroke-width="1" opacity="0.5" />'


def _bar(x, y, width, pct, theme, height=8) -> str:
    fill_w = max(0.0, min(float(width), width * pct / 100))
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height}" fill="{theme["surface"]}" />'
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{fill_w:.1f}" height="{height}" fill="{theme["accent"]}" />'
    )


def _activity_cell(cx, cy, cell, count, theme) -> str:
    if count <= 0:
        fill, opacity = theme["surface"], 1
    elif count <= 2:
        fill, opacity = theme["accent"], 0.35
    elif count <= 5:
        fill, opacity = theme["accent"], 0.65
    else:
        fill, opacity = theme["accent"], 1

    return f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" rx="2" fill="{fill}" fill-opacity="{opacity}" />'


def _wrap_text(text: str, max_chars: int = 90) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines
