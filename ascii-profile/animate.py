#!/usr/bin/env python3
"""Render the ASCII studies as a rotating, particle-morphing GIF loop."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, replace
from functools import lru_cache, partial
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

from generate import COLS, CONCEPTS, PROFILE_INSET, PROFILE_WIDTH, ROOT, ROWS, render_ascii, terrain


WIDTH, HEIGHT = 840, 588
ART_SCALE = 1.30
ART_BOUNDS = (32, 8, 808, 512)
GRID_CENTER = (34 + (COLS - 1) * 7.3 / 2, 119 + (ROWS - 1) * 11.2 / 2)
ART_CENTER = (WIDTH / 2, (ART_BOUNDS[1] + ART_BOUNDS[3]) / 2)
CAPTION_INSET = PROFILE_INSET * WIDTH / PROFILE_WIDTH
GLYPH_FONT_SIZE = 16
GLYPH_WIDTH, GLYPH_HEIGHT, GLYPH_BASELINE = 18, 30, 21
DEFAULT_HOLD = 3.0
DEFAULT_TRANSITION = 2.0


@dataclass(frozen=True)
class Rotation:
    axis: int
    radians_per_second: float
    label: str


@dataclass(frozen=True)
class Wave:
    cycles_per_second: float
    label: str = "Traveling wave / fixed view"


MOTIONS = {
    "01-cube": Rotation(1, 0.70 / 7, "Y-axis rotation"),
    "02-torus": Rotation(0, 0.62 / 7, "X-axis rotation"),
    "03-orbit": Rotation(2, 0.65 / 7, "Z-axis rotation"),
    "04-crystal": Rotation(1, -0.85 / 7, "Reverse Y-axis rotation"),
    "05-terrain": Wave(2 / 7),
    "06-twist": Rotation(1, -0.60 / 7, "Reverse Y-axis rotation"),
    "07-chain": Rotation(0, 0.70 / 7, "X-axis rotation"),
    "08-gyroid": Rotation(1, 0.65 / 7, "Y-axis rotation"),
}

THEMES = {
    "dark": {"background": "#0d1117", "text": "#e6edf3", "muted": "#9da7b5", "line": "#28323e", "shadow": "#263344"},
    "light": {"background": "#ffffff", "text": "#1f2937", "muted": "#596675", "line": "#dce3e9", "shadow": "#bbc4cf"},
}


@dataclass(frozen=True)
class Glyph:
    x: float
    y: float
    char: str
    intensity: float
    opacity: float = 1.0


def smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6 - 15) + 10)


def mix(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def concept_at(index: int, progress: float, hold: float = DEFAULT_HOLD):
    concept = CONCEPTS[index]
    motion = MOTIONS[concept.key]
    if isinstance(motion, Wave):
        phase = (progress * hold * motion.cycles_per_second % 1) * math.tau
        return replace(concept, distance=partial(terrain, phase=phase))
    rotation = list(concept.rotation)
    rotation[motion.axis] += motion.radians_per_second * hold * (smooth(progress) - 0.5)
    return replace(concept, rotation=tuple(rotation))


def shape_at(index: int, progress: float, hold: float = DEFAULT_HOLD) -> list[Glyph]:
    grid = render_ascii(concept_at(index, progress, hold))
    return [Glyph(34 + col * 7.3, 119 + row * 11.2, char, intensity)
            for row, cells in enumerate(grid)
            for col, (char, intensity) in enumerate(cells) if char != " "]


def particle_pairs(source: list[Glyph], target: list[Glyph]) -> list[tuple[Glyph, Glyph]]:
    def angular_key(glyph: Glyph):
        x, y = (glyph.x - 280) / 220, (glyph.y - 295) / 175
        return math.atan2(y, x), x * x + y * y

    source, target = sorted(source, key=angular_key), sorted(target, key=angular_key)
    count = max(len(source), len(target))

    def spread(glyphs: list[Glyph]) -> list[Glyph]:
        occupied = {i * count // len(glyphs): glyph for i, glyph in enumerate(glyphs)}
        return [occupied.get(i, replace(glyphs[min(len(glyphs) - 1, i * len(glyphs) // count)], opacity=0.0))
                for i in range(count)]

    return list(zip(spread(source), spread(target)))


def morph(pairs: list[tuple[Glyph, Glyph]], progress: float) -> list[Glyph]:
    if progress <= 0:
        return [source for source, _ in pairs]
    if progress >= 1:
        return [target for _, target in pairs]
    particles = []
    for i, (source, target) in enumerate(pairs):
        delay = (i * 0.61803398875) % 1 * 0.10
        t = max(0.0, min(1.0, (progress - delay) / 0.90))
        eased = smooth(t)
        scatter = math.sin(math.pi * eased) ** 2
        radius = math.sqrt((i * 0.754877666) % 1)
        angle = i * 2.39996323 + 1.3 * (eased - 0.5)
        swirl_x = 280 + math.cos(angle) * (55 + 163 * radius)
        swirl_y = 295 + math.sin(angle) * (35 + 130 * radius)
        x = source.x + (target.x - source.x) * eased
        y = source.y + (target.y - source.y) * eased
        x += (swirl_x - x) * scatter
        y += (swirl_y - y) * scatter
        intensity = source.intensity + (target.intensity - source.intensity) * eased
        opacity = source.opacity + (target.opacity - source.opacity) * eased
        char = source.char if eased < 0.5 else target.char
        particles.append(Glyph(x, y, char, intensity * (1 - 0.12 * scatter), opacity))
    return particles


def find_font(requested: Path | None) -> str:
    candidates = [requested] if requested else [
        Path("/System/Library/Fonts/Menlo.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf"),
        Path("C:/Windows/Fonts/consola.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise ValueError("No monospace font found. Pass --font /path/to/font.ttf.")


class Painter:
    def __init__(self, theme: str, font_path: str):
        self.theme = theme
        self.font_path = font_path
        self.colors = {key: ImageColor.getrgb(value) for key, value in THEMES[theme].items()}
        glyph_font = self.font(GLYPH_FONT_SIZE)
        self.glyph_advance = glyph_font.getlength("M")
        _, top, _, bottom = glyph_font.getbbox("M", anchor="ls")
        self.glyph_ink_center = (top + bottom) / 2
        self.base = self.make_base()

    @lru_cache(maxsize=48)
    def font(self, size: int):
        return ImageFont.truetype(self.font_path, size)

    def text(self, draw, x, y, value, size=14, color=None, max_width=None):
        font = self.font(size)
        if max_width:
            while font.getlength(value) > max_width and size > 6:
                size -= 1
                font = self.font(size)
        draw.text((x, y), value, font=font, fill=color or self.colors["muted"], anchor="ls")

    def make_base(self) -> Image.Image:
        return Image.new("RGB", (WIDTH, HEIGHT), self.colors["background"])

    @lru_cache(maxsize=64)
    def glyph_mask(self, char: str) -> Image.Image:
        mask = Image.new("L", (GLYPH_WIDTH, GLYPH_HEIGHT))
        ImageDraw.Draw(mask).text((0, GLYPH_BASELINE), char, font=self.font(GLYPH_FONT_SIZE), fill=255, anchor="ls")
        return mask

    def frame(self, particles: list[Glyph], accent: tuple, index: int, transition: float | None = None):
        image = self.base.copy()
        for glyph in sorted(particles, key=lambda glyph: (glyph.y, glyph.x)):
            if glyph.opacity <= 0:
                continue
            shade = mix(self.colors["shadow"], accent, 0.28 + 0.72 * glyph.intensity)
            shade = mix(self.colors["background"], shade, glyph.opacity)
            x = round(ART_CENTER[0] + (glyph.x - GRID_CENTER[0]) * ART_SCALE - self.glyph_advance / 2)
            y = round(ART_CENTER[1] + (glyph.y - GRID_CENTER[1]) * ART_SCALE - self.glyph_ink_center) - GLYPH_BASELINE
            image.paste(shade, (x, y, x + GLYPH_WIDTH, y + GLYPH_HEIGHT), self.glyph_mask(glyph.char))
        draw = ImageDraw.Draw(image)
        if transition is None:
            self.text(draw, CAPTION_INSET, 550, f"{index + 1:02d} / {CONCEPTS[index].name.upper()}", 18, accent)
            self.text(draw, CAPTION_INSET, 574, MOTIONS[CONCEPTS[index].key].label, 15)
        else:
            next_index = (index + 1) % len(CONCEPTS)
            self.text(draw, CAPTION_INSET, 550, f"{index + 1:02d} > {next_index + 1:02d} / RECONSTRUCTING", 18, accent)
            self.text(draw, CAPTION_INSET, 574, f"FORMING {CONCEPTS[next_index].name.upper()}", 15)
        for i in range(len(CONCEPTS)):
            color = accent if i == index else self.colors["line"]
            x = round(WIDTH - CAPTION_INSET - 162 + i * 150 / max(1, len(CONCEPTS) - 1))
            draw.line((x, 564, x + 12, 564), fill=color, width=3)
        return image


def global_palette(theme: str) -> Image.Image:
    colors = {key: ImageColor.getrgb(value) for key, value in THEMES[theme].items()}
    accents = [ImageColor.getrgb(getattr(concept, theme)) for concept in CONCEPTS]
    entries = list(colors.values())
    entries += [mix(colors["background"], colors["text"], step / 31) for step in range(32)]
    hue_steps = (256 - len(entries)) // (len(accents) * 6)
    for i, accent in enumerate(accents):
        for step in range(hue_steps):
            hue = mix(accent, accents[(i + 1) % len(accents)], step / hue_steps)
            entries += [mix(colors["background"], hue, shade) for shade in (0.12, 0.25, 0.42, 0.60, 0.80, 1.0)]
    entries = list(dict.fromkeys(entries))
    entries += [colors["background"]] * (256 - len(entries))
    palette = Image.new("P", (1, 1))
    palette.putpalette([channel for entry in entries for channel in entry])
    return palette


def animation_embed() -> str:
    prefix = "ascii-profile/assets/motion"
    alt = f"{len(CONCEPTS)} ASCII geometries rotate, ripple, and reconstruct into one another."
    return (
        '<p align="center">\n'
        '<picture>\n'
        f'  <source media="(prefers-reduced-motion: reduce) and (prefers-color-scheme: dark)" srcset="{prefix}-dark-poster.png">\n'
        f'  <source media="(prefers-reduced-motion: reduce)" srcset="{prefix}-light-poster.png">\n'
        f'  <source media="(prefers-color-scheme: dark)" srcset="{prefix}-dark.gif">\n'
        f'  <img alt="{alt}" src="{prefix}-light.gif" width="{PROFILE_WIDTH}">\n'
        '</picture>\n'
        '</p>\n'
    )


def generate(output: Path, font_path: str, fps=20, hold=DEFAULT_HOLD, transition=DEFAULT_TRANSITION):
    hold_frames, morph_frames = round(hold * fps), round(transition * fps)
    if min(hold_frames, morph_frames) < 2:
        raise ValueError("Hold and transition must each contain at least two frames.")
    hold = hold_frames / fps
    output.mkdir(parents=True, exist_ok=True)
    painters = {theme: Painter(theme, font_path) for theme in THEMES}
    palettes = {theme: global_palette(theme) for theme in THEMES}
    frames = {theme: [] for theme in THEMES}
    samples = []
    starts = [shape_at(i, 0, hold) for i in range(len(CONCEPTS))]

    def append(particles, index, progress=None):
        for theme, painter in painters.items():
            accent = ImageColor.getrgb(getattr(CONCEPTS[index], theme))
            if progress is not None:
                next_accent = ImageColor.getrgb(getattr(CONCEPTS[(index + 1) % len(CONCEPTS)], theme))
                accent = mix(accent, next_accent, smooth(progress))
            frame = painter.frame(particles, accent, index, progress)
            with BytesIO() as buffer:
                frame.quantize(palette=palettes[theme], dither=Image.Dither.NONE).save(buffer, format="PNG", compress_level=1)
                frames[theme].append(buffer.getvalue())

    for index, concept in enumerate(CONCEPTS):
        print(f"Rendering {concept.name}: {MOTIONS[concept.key].label.lower()} and character reconstruction", flush=True)
        for frame in range(hold_frames):
            append(shape_at(index, frame / (hold_frames - 1), hold), index)
        pairs = particle_pairs(shape_at(index, 1, hold), starts[(index + 1) % len(CONCEPTS)])
        for frame in range(morph_frames):
            progress = (frame + 1) / morph_frames
            append(morph(pairs, progress), index, progress)
        start_frame = index * (hold_frames + morph_frames)
        samples.append((concept.name, start_frame + hold_frames // 2, start_frame + hold_frames + morph_frames // 2))

    count = len(frames["dark"])
    durations = [round((i + 1) * 100 / fps) * 10 - round(i * 100 / fps) * 10 for i in range(count)]
    manifest = {"width": WIDTH, "height": HEIGHT, "fps": fps, "frames": count,
                "duration_ms": sum(durations), "hold_frames": hold_frames, "transition_frames": morph_frames,
                "font": Path(font_path).name, "themes": {}, "shapes": []}
    for concept in CONCEPTS:
        motion = MOTIONS[concept.key]
        state = {"key": concept.key, "name": concept.name, "motion": motion.label}
        if isinstance(motion, Rotation):
            state.update(kind="rotation", rotation_degrees=round(math.degrees(motion.radians_per_second * hold), 1))
        else:
            state.update(kind="wave", wave_cycles=round(motion.cycles_per_second * hold, 4))
        manifest["shapes"].append(state)
    for theme, sequence in frames.items():
        target = output / f"motion-{theme}.gif"
        print(f"Encoding {theme}: {count} frames", flush=True)
        def decoded_frames():
            for data in sequence[1:]:
                with Image.open(BytesIO(data)) as frame:
                    yield frame

        with Image.open(BytesIO(sequence[0])) as first:
            first.save(target, save_all=True, append_images=decoded_frames(), duration=durations,
                       loop=0, disposal=1, optimize=True, palette=palettes[theme].getpalette())
            first.save(output / f"motion-{theme}-poster.png")
        with Image.open(target) as encoded:
            encoded_frames = encoded.n_frames
        manifest["themes"][theme] = {"file": target.name, "bytes": target.stat().st_size, "encoded_frames": encoded_frames}
        print(f"Saved {target.name}: {target.stat().st_size / 1024 / 1024:.2f} MiB", flush=True)

    thumbnail_width = WIDTH // 2
    thumbnail_height = HEIGHT // 2
    row_height = thumbnail_height + 22
    sheet = Image.new("RGB", (WIDTH, len(CONCEPTS) * row_height), THEMES["dark"]["background"])
    draw = ImageDraw.Draw(sheet)
    for row, (name, shape_frame, morph_frame) in enumerate(samples):
        draw.text((16, row * row_height + 5), name + " / motion                 transition / scattered characters",
                  font=painters["dark"].font(12), fill=THEMES["dark"]["text"])
        for col, frame in enumerate((shape_frame, morph_frame)):
            with Image.open(BytesIO(frames["dark"][frame])) as sample:
                sheet.paste(sample.convert("RGB").resize((thumbnail_width, thumbnail_height), Image.Resampling.LANCZOS),
                            (col * thumbnail_width, row * row_height + 22))
    sheet.save(output / "motion-contact-sheet.jpg", quality=90)
    (output / "motion-embed.html").write_text(animation_embed(), encoding="utf-8")
    (output / "motion.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Complete: {sum(durations) / 1000:g}-second seamless sequence, both themes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "assets")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--fps", type=int, choices=(10, 20, 25), default=20)
    parser.add_argument("--hold", type=float, default=DEFAULT_HOLD, help="Seconds of motion per shape")
    parser.add_argument("--transition", type=float, default=DEFAULT_TRANSITION, help="Seconds of particle motion per transition")
    args = parser.parse_args()
    generate(args.output, find_font(args.font), args.fps, args.hold, args.transition)
