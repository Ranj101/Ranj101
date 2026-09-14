#!/usr/bin/env python3
"""Generate three information-card proposals without changing the published profile."""

from __future__ import annotations

import argparse
import html
import json
import textwrap
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

from generate import CONCEPTS, PROFILE_WIDTH, ROOT, information_svg, profile_description


FONT = {
    "A": "01110/10001/10001/11111/10001/10001/10001",
    "D": "11110/10001/10001/10001/10001/10001/11110",
    "H": "10001/10001/10001/11111/10001/10001/10001",
    "I": "11111/00100/00100/00100/00100/00100/11111",
    "J": "00111/00010/00010/00010/10010/10010/01100",
    "N": "10001/11001/11001/10101/10011/10011/10001",
    "R": "11110/10001/10001/11110/10100/10010/10001",
    "S": "01111/10000/10000/01110/00001/00001/11110",
    " ": "000/000/000/000/000/000/000",
}


@dataclass(frozen=True)
class Study:
    key: str
    name: str
    description: str
    accent_index: int


STUDIES = (
    Study("terminal", "Terminal manifest", "The selected profile design. Character-drawn borders, a command prompt, and bracketed statistics match the geometric ASCII animation.", 0),
    Study("signature", "Glyph signature", "Your name assembled from a matrix of zeroes and ones. An open layout with less framing and a stronger personal signature.", 2),
    Study("source", "Source file", "A profile written like code: line numbers, syntax colors, and a public-statistics footer. The most understated developer-focused option.", 3),
)


def palette(study: Study, theme: str) -> dict:
    dark = theme == "dark"
    return {
        "background": "#0d1117" if dark else "#ffffff",
        "text": "#e6edf3" if dark else "#1f2937",
        "muted": "#9da7b5" if dark else "#596675",
        "line": "#28323e" if dark else "#dce3e9",
        "accent": getattr(CONCEPTS[study.accent_index], theme),
    }


class Card:
    def __init__(self, study: Study, profile: dict, theme: str, height: int):
        self.colors = palette(study, theme)
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{PROFILE_WIDTH}" height="{height}" '
            f'viewBox="0 0 {PROFILE_WIDTH} {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{html.escape(study.name)} / {html.escape(profile["name"])}</title>',
            f'<desc id="desc">{html.escape(profile_description(profile))}</desc>',
            '<style>text{font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;'
            'font-variant-ligatures:none;font-variant-numeric:tabular-nums}</style>',
            f'<rect width="{PROFILE_WIDTH}" height="{height}" fill="{self.colors["background"]}"/>',
        ]

    def text(self, x, y, value, size=16, color="text", weight=400, extra="", max_width=None):
        if max_width:
            size = min(size, max_width / (max(1, len(value)) * 0.62))
        self.parts.append(f'<text x="{x}" y="{y}" fill="{self.colors[color]}" font-size="{size:.2f}" '
                          f'font-weight="{weight}" {extra}>{html.escape(value)}</text>')

    def rule(self, y):
        self.text(32, y, "─" * 64, 12, "line", extra='aria-hidden="true" textLength="536" lengthAdjust="spacingAndGlyphs"')

    def metrics(self, profile, value_y, label_y, note_y):
        for index, metric in enumerate(profile["metrics"]):
            x = 32 + index * 184
            self.text(x, value_y, metric["value"], 27, "accent", 500, max_width=148)
            self.text(x, label_y, metric["label"], 12, "muted", max_width=156)
        self.text(32, note_y, profile["note"], 11, "muted", max_width=536)

    def finish(self) -> str:
        return "\n".join(self.parts + ["</svg>"]) + "\n"


def terminal(_study: Study, profile: dict, theme: str) -> str:
    return information_svg(profile, theme)


def glyph_name(card: Card, name: str):
    if any(letter not in FONT for letter in name.upper()):
        card.text(32, 103, name, 38, "accent", 600, max_width=536)
        return
    rows = ["0".join(FONT[letter].split("/")[row] for letter in name.upper()) for row in range(7)]
    advance = 536 / len(rows[0])
    card.parts.append('<g aria-hidden="true">')
    for row, pixels in enumerate(rows):
        for col, pixel in enumerate(pixels):
            value = str((row + col) % 2) if pixel == "1" else "·"
            card.text(round(32 + col * advance, 2), 52 + row * 11, value, 11,
                      "accent" if pixel == "1" else "line", 600 if pixel == "1" else 400)
    card.parts.append('</g>')


def signature(study: Study, profile: dict, theme: str) -> str:
    card = Card(study, profile, theme, 450)
    fields = {field["label"]: field["value"] for field in profile["fields"]}
    card.text(32, 21, "@" + profile["handle"], 12, "muted")
    glyph_name(card, profile["name"])
    card.text(32, 151, profile["tagline"], 14, "text", max_width=536)
    for x, label, value in ((32, "role", fields["role"]), (336, "location", fields["location"])):
        card.text(x, 192, label.upper(), 12, "muted", extra='letter-spacing="1.5"')
        card.text(x, 219, value, 18, "text", 500, max_width=280 if x == 32 else 232)
    card.text(32, 262, "BUILDING", 12, "muted", extra='letter-spacing="1.5"')
    card.text(32, 289, fields["building"], 18, "text", 500, max_width=280)
    card.text(336, 262, "STACK", 12, "muted", extra='letter-spacing="1.5"')
    stack = fields["stack"].split(" · ")
    card.text(336, 289, " · ".join(stack[:2]), 18, "text", 500, max_width=232)
    card.text(336, 313, " · ".join(stack[2:]), 15, "text", max_width=232)
    card.text(32, 343, fields["website"], 16, "accent", extra='text-decoration="underline"', max_width=480)
    card.text(568, 343, "↗", 18, "accent", extra='text-anchor="end"')
    card.rule(366)
    card.metrics(profile, 398, 419, 441)
    return card.finish()


def source(study: Study, profile: dict, theme: str) -> str:
    card = Card(study, profile, theme, 474)
    card.text(32, 35, "profile.rs", 14, "accent", 500)
    card.text(568, 35, "@" + profile["handle"], 12, "muted", extra='text-anchor="end"')
    card.rule(55)
    card.text(32, 85, "01", 12, "muted", extra='aria-hidden="true"')
    card.text(72, 85, "Profile {", 19, "accent", 500)
    values = [("name", profile["name"])] + [(field["label"], field["value"]) for field in profile["fields"]]
    for index, (label, value) in enumerate(values):
        y = 113 + index * 28
        card.text(32, y, f"{index + 2:02d}", 12, "muted", extra='aria-hidden="true"')
        tokens = [("muted", "  "), ("accent", label), ("muted", ': "'), ("text", value), ("muted", '",')]
        line = "".join(f'<tspan fill="{card.colors[color]}">{html.escape(text)}</tspan>' for color, text in tokens)
        decoration = 'text-decoration="underline"' if label == "website" else ""
        card.parts.append(f'<text x="72" y="{y}" font-size="15" xml:space="preserve" {decoration}>{line}</text>')
    card.text(32, 281, "08", 12, "muted", extra='aria-hidden="true"')
    card.text(72, 281, "}", 19, "accent", 500)
    for index, line in enumerate(textwrap.wrap(profile["tagline"], width=56)):
        card.text(72, 316 + index * 23, "// " + line, 14, "muted", max_width=496)
    card.rule(361)
    card.metrics(profile, 397, 420, 451)
    card.text(568, 451, "LinkedIn ↗", 11, "accent", extra='text-anchor="end"')
    return card.finish()


RENDERERS = {"terminal": terminal, "signature": signature, "source": source}


def generate_studies(config: Path, output: Path):
    profile = json.loads(config.read_text(encoding="utf-8"))
    website = next(field["href"] for field in profile["fields"] if field["label"] == "website")
    url = urlsplit(website)
    if url.scheme != "https" or not url.netloc:
        raise ValueError("The website href must be an HTTPS URL.")
    assets = output / "assets" / "card-studies"
    assets.mkdir(parents=True, exist_ok=True)
    figures = []
    for index, study in enumerate(STUDIES):
        for theme in ("dark", "light"):
            svg = RENDERERS[study.key](study, profile, theme)
            ElementTree.fromstring(svg)
            (assets / f"{study.key}-{theme}.svg").write_text(svg, encoding="utf-8")
        alt = html.escape(study.name + ". " + profile_description(profile) + " Open LinkedIn profile.")
        figures.append(
            f'<figure class="study" id="{study.key}" data-card="{study.key}">'
            f'<figcaption><span class="number">0{index + 1}</span><div><h2>{html.escape(study.name)}</h2>'
            f'<p>{html.escape(study.description)}</p></div></figcaption>'
            f'<div class="stage"><img class="geometry" src="assets/motion-dark-poster.png" alt="" hidden>'
            f'<a class="card-link" href="{html.escape(website)}" target="_blank" rel="noopener noreferrer">'
            f'<img class="card" src="assets/card-studies/{study.key}-dark.svg" width="600" alt="{alt}"></a></div>'
            f'<div class="card-actions"><button type="button" data-inspect="{study.key}">View with geometry</button>'
            f'<a class="svg-link" href="assets/card-studies/{study.key}-dark.svg" target="_blank" rel="noopener">Open SVG ↗</a></div></figure>'
        )
        print(f"Generated {study.name}: dark and light SVG")
    template = (ROOT / "card-studies.template.html").read_text(encoding="utf-8")
    (output / "card-studies.html").write_text(template.replace("__CARD_STUDIES__", "\n".join(figures)), encoding="utf-8")
    print(f"Review: {output / 'card-studies.html'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "profile.json")
    parser.add_argument("--output", type=Path, default=ROOT)
    args = parser.parse_args()
    generate_studies(args.config, args.output)
