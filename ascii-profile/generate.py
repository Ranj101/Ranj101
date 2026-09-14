#!/usr/bin/env python3
"""Generate original ASCII profile studies using only the standard library."""

from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parent
WIDTH, HEIGHT = 1120, 600
PROFILE_WIDTH = 600
PROFILE_INSET = 32
PROFILE_START = "<!-- PROFILE:START -->"
PROFILE_END = "<!-- PROFILE:END -->"
COLS, ROWS = 68, 34
TERRAIN_HALF_EXTENT = 1.08
TERRAIN_BASE = -0.42
TERRAIN_AMPLITUDES = (0.20, 0.075)
Point = tuple[float, float, float]
SDF = Callable[[Point], float]


@dataclass(frozen=True)
class Concept:
    key: str
    name: str
    description: str
    dark: str
    light: str
    rotation: Point
    distance: SDF


def rotate(p: Point, angles: Point) -> Point:
    x, y, z = p
    a, b, c = angles
    y, z = y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)
    x, z = x * math.cos(b) + z * math.sin(b), -x * math.sin(b) + z * math.cos(b)
    x, y = x * math.cos(c) - y * math.sin(c), x * math.sin(c) + y * math.cos(c)
    return x, y, z


def cube(p: Point) -> float:
    q = [abs(v) - 0.88 for v in p]
    return math.sqrt(sum(max(v, 0) ** 2 for v in q)) + min(max(q), 0)


def torus(p: Point) -> float:
    x, y, z = p
    return math.hypot(math.hypot(x, y) - 1.04, z) - 0.36


def orbit(p: Point) -> float:
    sphere = math.sqrt(sum(v * v for v in p)) - 1.06
    rings = []
    for angles in ((0.88, 0.18, 0.0), (-0.68, 0.42, 0.0)):
        x, y, z = rotate(p, angles)
        rings.append(math.hypot(math.hypot(x, y) - 1.38, z) - 0.045)
    return min(sphere, *rings)


def crystal(p: Point) -> float:
    x, y, z = p
    return (abs(x) / 0.83 + abs(y) / 1.48 + abs(z) / 0.83 - 1) * 0.50


def terrain_height(x: float, z: float, phase: float = 0.0) -> float:
    return TERRAIN_AMPLITUDES[0] * math.sin(3.5 * x - phase) + TERRAIN_AMPLITUDES[1] * math.sin(3.0 * z - phase * 2)


def terrain(p: Point, phase: float = 0.0) -> float:
    x, y, z = p
    return max((y - terrain_height(x, z, phase)) * 0.55, TERRAIN_BASE - y,
               abs(x) - TERRAIN_HALF_EXTENT, abs(z) - TERRAIN_HALF_EXTENT)


def twisted_column(p: Point) -> float:
    x, y, z = p
    angle = y * 1.25
    x, z = x * math.cos(angle) - z * math.sin(angle), x * math.sin(angle) + z * math.cos(angle)
    qx, qz = abs(x) - 0.57, abs(z) - 0.57
    section = math.hypot(max(qx, 0), max(qz, 0)) + min(max(qx, qz), 0)
    return max(section, abs(y) - 1.35) * 0.45


def chain(p: Point) -> float:
    x, y, z = p
    center = math.hypot(math.hypot(x, z) - 0.64, y) - 0.14
    outer = [math.hypot(math.hypot(x - offset, y) - 0.64, z) - 0.14 for offset in (-0.90, 0.90)]
    return min(center, *outer)


def gyroid(p: Point) -> float:
    x, y, z = (v * 3.1 for v in p)
    surface = math.sin(x) * math.cos(y) + math.sin(y) * math.cos(z) + math.sin(z) * math.cos(x)
    shell = abs(surface) / (3.1 * 3.5) - 0.032
    bound = max(abs(v) for v in p) - 1.04
    dx, dy, dz = (abs(abs(v) - 1.08) for v in p)
    frame = max(min(math.hypot(dx, dy), math.hypot(dx, dz), math.hypot(dy, dz)) - 0.048,
                max(abs(v) for v in p) - 1.08)
    return min(max(shell, bound), frame)


CONCEPTS = (
    Concept("01-cube", "Isometric cube", "Sharp edges, quiet structure. A compact architectural study.",
            "#7dd3fc", "#03638d", (-math.asin(1 / math.sqrt(3)), -math.pi / 4, 0.0), cube),
    Concept("02-torus", "Torus", "A continuous surface, drawn with light and character density.",
            "#f5bd6c", "#945400", (0.68, 0.27, -0.28), torus),
    Concept("03-orbit", "Orbital sphere", "A shaded globe with clean meridians, latitude bands, and two orbital rings.",
            "#8bd5b2", "#167047", (0.22, 0.25, -0.08), orbit),
    Concept("04-crystal", "Faceted crystal", "An elongated octahedron. Angular, spare, and a little otherworldly.",
            "#c4b5fd", "#7151b8", (-0.10, 0.52, -0.12), crystal),
    Concept("05-terrain", "Terrain wave", "Small traveling ripples cross a compact, shaded terrain tile with visible depth.",
            "#f8a995", "#a84831", (-0.68, -0.24, 0.0), terrain),
    Concept("06-twist", "Twisted column", "A square column twisted into a continuous architectural ribbon.",
            "#94b6ff", "#385fb5", (-0.18, 0.46, -0.12), twisted_column),
    Concept("07-chain", "Interlocking chain", "Three rounded links, alternating through perpendicular planes.",
            "#d8df8b", "#687117", (0.50, 0.34, -0.24), chain),
    Concept("08-gyroid", "Gyroid lattice", "Curved channels and shaded walls inside a fine cubic guide frame.",
            "#f29ec6", "#9e326b", (-0.32, 0.55, 0.10), gyroid),
)


def render_ascii(concept: Concept) -> list[list[tuple[str, float]]]:
    grid = [[(" ", 0.0) for _ in range(COLS)] for _ in range(ROWS)]
    light = (-0.50, 0.65, 0.57)
    ramp = ".,:;irsXA253hMHGS#9B&@"

    def distance(p: Point) -> float:
        return concept.distance(rotate(p, concept.rotation))

    for row in range(ROWS):
        for col in range(COLS):
            x = (col + 0.5 - COLS / 2) / ROWS * 3.25 * 7.3 / 11.2
            y = -(row + 0.5 - ROWS / 2) / ROWS * 3.25
            z = 3.5
            hit = False
            for _ in range(150):
                d = distance((x, y, z))
                if d < 0.005:
                    hit = True
                    break
                z -= max(d * 0.85, 0.003)
                if z < -2.8:
                    break
            if not hit:
                continue

            epsilon = 0.003
            normal = []
            for axis in range(3):
                plus, minus = [x, y, z], [x, y, z]
                plus[axis] += epsilon
                minus[axis] -= epsilon
                normal.append(distance(tuple(plus)) - distance(tuple(minus)))
            norm = math.sqrt(sum(n * n for n in normal)) or 1
            diffuse = max(0, sum(n / norm * l for n, l in zip(normal, light)))
            intensity = 0.20 + diffuse * 0.80
            glyph = ramp[min(len(ramp) - 1, int(intensity * (len(ramp) - 1)))]
            local = rotate((x, y, z), concept.rotation)

            if concept.key == "01-cube":
                edges = sorted(abs(abs(v) - 0.88) for v in local)
                if edges[1] < 0.045:
                    glyph, intensity = "@", 1.0
            elif concept.key == "03-orbit":
                radius = math.sqrt(sum(v * v for v in local))
                if radius < 1.13:
                    longitude = math.atan2(local[2], local[0])
                    latitude = math.asin(max(-1, min(1, local[1] / 1.06)))
                    meridian = abs(math.sin(longitude * 6)) < 0.15
                    parallel = abs(math.sin(latitude * 6)) < 0.17
                    intensity = 0.22 + 0.73 * diffuse
                    sphere_ramp = ".,:;irsXAH#"
                    glyph = sphere_ramp[min(len(sphere_ramp) - 1, int(intensity * (len(sphere_ramp) - 1)))]
                    if meridian or parallel:
                        glyph = "+" if meridian and parallel else "|" if meridian else "="
                        intensity = 0.70 + 0.30 * diffuse
                else:
                    glyph, intensity = "o", 0.80 + diffuse * 0.20
            elif concept.key == "04-crystal":
                if min(abs(v) for v in local) < 0.03:
                    glyph, intensity = "+", 1.0
            elif concept.key == "05-terrain":
                side = max(abs(local[0]), abs(local[2])) > TERRAIN_HALF_EXTENT - 0.012 or local[1] < TERRAIN_BASE + 0.012
                elevation = max(0, min(1, (local[1] / sum(TERRAIN_AMPLITUDES) + 1) / 2))
                intensity = 0.16 + 0.30 * diffuse if side else 0.24 + 0.66 * diffuse + 0.08 * elevation
                terrain_ramp = ".,:;irsXA25hMH#@"
                glyph = terrain_ramp[min(len(terrain_ramp) - 1, int(intensity * (len(terrain_ramp) - 1)))]
            elif concept.key == "08-gyroid":
                depth = max(0, min(1, (z + 1.6) / 3.2))
                rim = (1 - max(0, normal[2] / norm)) ** 3
                intensity = min(1, (0.24 + 0.66 * diffuse + 0.25 * rim) * (0.52 + 0.48 * depth))
                gyroid_ramp = " .:oxX#%@"
                glyph = gyroid_ramp[min(8, max(1, int(intensity * 8)))]
                edges = sorted(abs(abs(v) - 1.08) for v in local)
                if edges[1] < 0.065 and max(abs(v) for v in local) > 1.04:
                    glyph, intensity = "+", 0.85
            grid[row][col] = glyph, intensity
    return grid


def blend(first: str, second: str, fraction: float) -> str:
    a = [int(first[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(second[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * fraction):02x}" for x, y in zip(a, b))


def card_svg(concept: Concept, grid: list, profile: dict, theme: str) -> str:
    dark = theme == "dark"
    background = "#0d1117" if dark else "#ffffff"
    text = "#e6edf3" if dark else "#1f2937"
    muted = "#9da7b5" if dark else "#596675"
    line = "#28323e" if dark else "#dce3e9"
    accent = concept.dark if dark else concept.light
    art_shadow = "#263344" if dark else "#bbc4cf"
    number = concept.key[:2]
    esc = html.escape
    desc = f"{profile['name']}, @{profile['handle']}. {concept.name} drawn entirely with ASCII characters. "
    desc += ". ".join(f"{f['label']}: {f['value']}" for f in profile["fields"])
    desc += ". " + profile["note"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{esc(profile["name"])} / {esc(concept.name)}</title>',
        f'<desc id="desc">{esc(desc)}</desc>',
        '<style>text{font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;'
        'font-variant-ligatures:none}.art{white-space:pre}</style>',
        f'<rect x="0.5" y="0.5" width="1119" height="599" rx="12" fill="{background}" stroke="{line}"/>',
        f'<path d="M1 63H1119M559 96V510M32 542H1088" stroke="{line}" fill="none"/>',
    ]

    def label(x: float, y: float, value: str, size=14, color=muted, weight=400,
              max_width=None, extra=""):
        if max_width:
            size = min(size, max_width / (max(1, len(value)) * 0.62))
        parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size:.2f}" '
                     f'font-weight="{weight}" {extra}>{esc(value)}</text>')

    label(32, 39, f"{profile['handle'].lower()}@github", 15, text)
    label(826, 39, f"GEOMETRIC STUDY / {number}", 13)
    for row, cells in enumerate(grid):
        runs = []
        for col, (glyph, intensity) in enumerate(cells):
            if glyph == " ":
                continue
            shade = blend(art_shadow, accent, 0.28 + 0.72 * intensity)
            runs.append(f'<tspan x="{34 + col * 7.3:.1f}" fill="{shade}">{esc(glyph)}</tspan>')
        if runs:
            parts.append(f'<text class="art" y="{119 + row * 11.2:.1f}" font-size="12.4">'
                         + "".join(runs) + '</text>')
    label(34, 511, concept.name.upper(), 12, accent, extra='letter-spacing="2"')
    label(602, 120, "HELLO, I'M", 12, accent, extra='letter-spacing="2"')
    label(600, 169, profile["name"], 37, text, 600, 475)
    label(602, 200, profile["tagline"], 14, muted, max_width=468)
    for i, field in enumerate(profile["fields"]):
        y = 255 + i * 35
        label(602, y, field["label"], 14, muted, max_width=98)
        label(709, y, ":", 14, muted)
        label(728, y, field["value"], 15, text, max_width=350)
    parts.append(f'<path d="M602 431H1079" stroke="{line}"/>')
    for i, metric in enumerate(profile["metrics"]):
        x = 602 + i * 164
        label(x, 470, metric["value"], 26, accent, 500, 130)
        label(x, 496, metric["label"], 11, muted, max_width=134)
    label(32, 575, "ASCII / MONOSPACE / SVG", 11)
    label(622, 575, profile["note"], 10, muted, max_width=462)
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def embed(concept: Concept, profile: dict, prefix="ascii-profile/assets/") -> str:
    description = f"{profile['name']}'s profile with {concept.name} ASCII art. {profile['note']}"
    return (
        '<picture>\n'
        f'  <source media="(prefers-color-scheme: dark)" srcset="{prefix}{concept.key}-dark.svg">\n'
        f'  <img alt="{html.escape(description)}" '
        f'src="{prefix}{concept.key}-light.svg" width="100%">\n'
        '</picture>\n'
    )


def profile_description(profile: dict) -> str:
    details = [f"{profile['name']}, @{profile['handle']}", profile["tagline"].rstrip(".")]
    details.extend(f"{field['label']}: {field['value']}" for field in profile["fields"])
    details.extend(f"{metric['label']}: {metric['value']}" for metric in profile["metrics"])
    return ". ".join(details) + ". " + profile["note"]


def information_svg(profile: dict, theme: str) -> str:
    dark = theme == "dark"
    background = "#0d1117" if dark else "#ffffff"
    text = "#e6edf3" if dark else "#1f2937"
    muted = "#9da7b5" if dark else "#596675"
    line = "#28323e" if dark else "#dce3e9"
    accent = CONCEPTS[0].dark if dark else CONCEPTS[0].light
    left, right = PROFILE_INSET, PROFILE_WIDTH - PROFILE_INSET
    content_width = right - left
    esc = html.escape
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{PROFILE_WIDTH}" height="474" '
        f'viewBox="0 0 {PROFILE_WIDTH} 474" role="img" aria-labelledby="title desc">',
        f'<title id="title">{esc(profile["name"])} / Profile</title>',
        f'<desc id="desc">{esc(profile_description(profile))}</desc>',
        '<style>text{font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;'
        'font-variant-ligatures:none;font-variant-numeric:tabular-nums}</style>',
        f'<rect x="0.5" y="0.5" width="{PROFILE_WIDTH - 1}" height="473" rx="12" fill="{background}" stroke="{line}"/>',
        f'<path d="M1 60H{PROFILE_WIDTH - 1}M{left} 350H{right}" stroke="{line}" fill="none"/>',
    ]

    def label(x, y, value, size=14, color=muted, weight=400, max_width=None, extra=""):
        if max_width:
            size = min(size, max_width / (max(1, len(value)) * 0.62))
        parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size:.2f}" '
                     f'font-weight="{weight}" {extra}>{esc(value)}</text>')

    label(left, 37, f"{profile['handle'].lower()}@github", 14, text, max_width=370)
    label(right, 37, "LINKEDIN ↗", 11, accent, extra='text-anchor="end"')
    label(left, 90, "HELLO, I'M", 12, accent, extra='letter-spacing="2"')
    label(left - 2, 129, profile["name"], 37, text, 600, content_width)
    label(left, 158, profile["tagline"], 14, muted, max_width=content_width)
    for i, field in enumerate(profile["fields"]):
        y = 201 + i * 32
        label(left, y, field["label"], 14, muted, max_width=88)
        label(left + 96, y, ":", 14, muted)
        website = field["label"] == "website"
        label(left + 120, y, field["value"], 15, accent if website else text, max_width=content_width - 120,
              extra='text-decoration="underline"' if website else "")
    for i, metric in enumerate(profile["metrics"]):
        x = left + (i + 0.5) * content_width / len(profile["metrics"])
        label(x, 390, metric["value"], 26, accent, 500, 162, extra=f'text-anchor="middle" id="metric-{i}"')
        label(x, 414, metric["label"], 11, muted, max_width=162, extra='text-anchor="middle"')
    label(PROFILE_WIDTH / 2, 457, profile["note"], 10, muted, max_width=content_width, extra='text-anchor="middle"')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def profile_panel(profile: dict, prefix="ascii-profile/assets/") -> str:
    esc = html.escape
    fields = {field["label"]: field for field in profile["fields"]}
    website = fields["website"]["href"]
    url = urlsplit(website)
    if url.scheme != "https" or not url.netloc:
        raise ValueError("The website href must be an HTTPS URL.")
    description = profile_description(profile) + " Open LinkedIn profile."
    return (
        '<p align="center">\n'
        f'<a href="{esc(website)}">\n'
        '<picture>\n'
        f'  <source media="(prefers-color-scheme: dark)" srcset="{prefix}profile-dark.svg">\n'
        f'  <img alt="{esc(description)}" src="{prefix}profile-light.svg" width="{PROFILE_WIDTH}">\n'
        '</picture>\n'
        '</a>\n'
        '</p>\n'
    )


def write_readme(path: Path, profile: str) -> None:
    generated = PROFILE_START + "\n" + profile + PROFILE_END
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing.count(PROFILE_START) != 1 or existing.count(PROFILE_END) != 1:
            raise ValueError("The README must contain exactly one PROFILE:START and PROFILE:END marker.")
        before, remainder = existing.split(PROFILE_START)
        if PROFILE_END not in remainder:
            raise ValueError("The README profile markers are out of order.")
        _, after = remainder.split(PROFILE_END)
        content = before + generated + after
    else:
        content = generated + "\n"
    path.write_text(content, encoding="utf-8")


def generate(config: Path, output: Path, readme: Path | None = None) -> None:
    profile = json.loads(config.read_text(encoding="utf-8"))
    if len(profile["fields"]) != 5 or len(profile["metrics"]) != 3:
        raise ValueError("This card layout needs five profile fields and three metrics.")
    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    panel = profile_panel(profile)
    for theme in ("dark", "light"):
        svg = information_svg(profile, theme)
        ElementTree.fromstring(svg)
        (assets / f"profile-{theme}.svg").write_text(svg, encoding="utf-8")
    print("Generated profile card: dark SVG, light SVG, linked README embed")
    catalog = []
    for concept in CONCEPTS:
        grid = render_ascii(concept)
        art = "\n".join("".join(cell[0] for cell in row).rstrip() for row in grid)
        (assets / f"{concept.key}.txt").write_text(art.rstrip() + "\n", encoding="ascii")
        for theme in ("dark", "light"):
            svg = card_svg(concept, grid, profile, theme)
            ElementTree.fromstring(svg)
            (assets / f"{concept.key}-{theme}.svg").write_text(svg, encoding="utf-8")
        (assets / f"{concept.key}-embed.html").write_text(embed(concept, profile), encoding="utf-8")
        catalog.append({"key": concept.key, "name": concept.name, "description": concept.description,
                        "accent": concept.dark, "embed": embed(concept, profile)})
        print(f"Generated {concept.key}: dark SVG, light SVG, ASCII text, README embed")

    data = json.dumps(catalog, ensure_ascii=True).replace("<", "\\u003c")
    motion_path = assets / "motion.json"
    motion = json.loads(motion_path.read_text(encoding="utf-8")) if motion_path.exists() else None
    if motion:
        animation = (assets / "motion-embed.html").read_text(encoding="utf-8")
        motion["embed"] = animation + "\n" + panel
    if readme is not None:
        if not motion:
            raise ValueError("Generate the animation before exporting the README.")
        write_readme(readme, motion["embed"])
    template = (ROOT / "gallery.template.html").read_text(encoding="utf-8")
    gallery = template.replace("__CONCEPT_DATA__", data).replace("__MOTION_DATA__", json.dumps(motion).replace("<", "\\u003c"))
    gallery = gallery.replace("__PROFILE_PANEL__", profile_panel(profile, prefix="assets/"))
    gallery = gallery.replace("__PROFILE_WIDTH__", str(PROFILE_WIDTH))
    (output / "index.html").write_text(gallery, encoding="utf-8")
    print(f"Gallery: {output / 'index.html'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "profile.json")
    parser.add_argument("--output", type=Path, default=ROOT)
    parser.add_argument("--readme", type=Path, help="Also write the linked profile card and animation to this README")
    args = parser.parse_args()
    generate(args.config.resolve(), args.output.resolve(), args.readme)
