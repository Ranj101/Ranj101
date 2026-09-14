#!/usr/bin/env python3
"""Render the ASCII studies as a rotating, particle-morphing GIF loop."""

from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import dataclass, replace
from functools import lru_cache, partial
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

from generate import CONCEPTS, HEIGHT, ROOT, WIDTH, render_ascii, terrain


@dataclass(frozen=True)
class Rotation:
    axis: int
    travel: float
    label: str


@dataclass(frozen=True)
class Wave:
    cycles: float
    label: str = "Traveling wave / fixed view"


MOTIONS = {
    "01-cube": Rotation(1, 0.70, "Y-axis rotation"),
    "02-torus": Rotation(0, 0.62, "X-axis rotation"),
    "03-orbit": Rotation(2, 0.65, "Z-axis rotation"),
    "04-crystal": Rotation(1, -0.85, "Reverse Y-axis rotation"),
    "05-terrain": Wave(2.0),
    "06-twist": Rotation(1, -0.60, "Reverse Y-axis rotation"),
    "07-chain": Rotation(0, 0.70, "X-axis rotation"),
    "08-gyroid": Rotation(1, 0.65, "Y-axis rotation"),
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


def concept_at(index: int, progress: float):
    concept = CONCEPTS[index]
    motion = MOTIONS[concept.key]
    if isinstance(motion, Wave):
        phase = (progress * motion.cycles % 1) * math.tau
        return replace(concept, distance=partial(terrain, phase=phase))
    rotation = list(concept.rotation)
    rotation[motion.axis] += motion.travel * (smooth(progress) - 0.5)
    return replace(concept, rotation=tuple(rotation))


def shape_at(index: int, progress: float) -> list[Glyph]:
    grid = render_ascii(concept_at(index, progress))
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
    def __init__(self, profile: dict, theme: str, font_path: str):
        self.profile = profile
        self.theme = theme
        self.font_path = font_path
        self.colors = {key: ImageColor.getrgb(value) for key, value in THEMES[theme].items()}
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
        image = Image.new("RGB", (WIDTH, HEIGHT), self.colors["background"])
        draw = ImageDraw.Draw(image)
        line = self.colors["line"]
        draw.rounded_rectangle((0, 0, WIDTH - 1, HEIGHT - 1), radius=12, outline=line)
        for coords in ((1, 63, 1119, 63), (559, 96, 559, 510), (32, 542, 1088, 542), (602, 431, 1079, 431)):
            draw.line(coords, fill=line)
        self.text(draw, 32, 39, f"{self.profile['handle'].lower()}@github", 15, self.colors["text"])
        self.text(draw, 826, 39, "GEOMETRY IN MOTION", 13)
        self.text(draw, 602, 120, "HELLO, I'M", 12)
        self.text(draw, 600, 169, self.profile["name"], 37, self.colors["text"], 475)
        self.text(draw, 602, 200, self.profile["tagline"], 14, max_width=468)
        for i, field in enumerate(self.profile["fields"]):
            y = 255 + i * 35
            self.text(draw, 602, y, field["label"], 14, max_width=98)
            self.text(draw, 709, y, ":", 14)
            self.text(draw, 728, y, field["value"], 15, self.colors["text"], 350)
        for i, metric in enumerate(self.profile["metrics"]):
            x = 602 + i * 164
            self.text(draw, x, 470, metric["value"], 26, self.colors["text"], 130)
            self.text(draw, x, 496, metric["label"], 11, max_width=134)
        self.text(draw, 32, 575, "ASCII / MOTION / RECONSTRUCT / REPEAT", 11)
        self.text(draw, 622, 575, self.profile["note"], 10, max_width=462)
        return image

    @lru_cache(maxsize=64)
    def glyph_mask(self, char: str) -> Image.Image:
        mask = Image.new("L", (12, 20))
        ImageDraw.Draw(mask).text((0, 14), char, font=self.font(12), fill=255, anchor="ls")
        return mask

    def frame(self, particles: list[Glyph], accent: tuple, index: int, transition: float | None = None):
        image = self.base.copy()
        for glyph in sorted(particles, key=lambda glyph: (glyph.y, glyph.x)):
            if glyph.opacity <= 0:
                continue
            shade = mix(self.colors["shadow"], accent, 0.28 + 0.72 * glyph.intensity)
            shade = mix(self.colors["background"], shade, glyph.opacity)
            x, y = round(glyph.x), round(glyph.y) - 14
            image.paste(shade, (x, y, x + 12, y + 20), self.glyph_mask(glyph.char))
        draw = ImageDraw.Draw(image)
        if transition is None:
            self.text(draw, 34, 511, f"{index + 1:02d} / {CONCEPTS[index].name.upper()}", 12, accent)
            self.text(draw, 34, 530, MOTIONS[CONCEPTS[index].key].label, 10)
        else:
            next_index = (index + 1) % len(CONCEPTS)
            self.text(draw, 34, 511, f"{index + 1:02d} > {next_index + 1:02d} / RECONSTRUCTING", 12, accent)
            self.text(draw, 34, 530, f"FORMING {CONCEPTS[next_index].name.upper()}", 10)
        for i in range(len(CONCEPTS)):
            color = accent if i == index else self.colors["line"]
            x = round(424 + i * 100 / max(1, len(CONCEPTS) - 1))
            draw.line((x, 522, x + 8, 522), fill=color, width=2)
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


def animation_embed(profile: dict) -> str:
    prefix = "ascii-profile/assets/motion"
    alt = html.escape(f"{profile['name']}'s profile. {len(CONCEPTS)} animated ASCII shapes reconstruct into one another. {profile['note']}")
    return (
        '<picture>\n'
        f'  <source media="(prefers-reduced-motion: reduce) and (prefers-color-scheme: dark)" srcset="{prefix}-dark-poster.png">\n'
        f'  <source media="(prefers-reduced-motion: reduce)" srcset="{prefix}-light-poster.png">\n'
        f'  <source media="(prefers-color-scheme: dark)" srcset="{prefix}-dark.gif">\n'
        f'  <img alt="{alt}" src="{prefix}-light.gif" width="100%">\n'
        '</picture>\n'
    )


def generate(config: Path, output: Path, font_path: str, fps=20, hold=7.0, transition=2.0):
    profile = json.loads(config.read_text(encoding="utf-8"))
    if len(profile["fields"]) != 5 or len(profile["metrics"]) != 3:
        raise ValueError("This card layout needs five profile fields and three metrics.")
    hold_frames, morph_frames = round(hold * fps), round(transition * fps)
    if min(hold_frames, morph_frames) < 2:
        raise ValueError("Hold and transition must each contain at least two frames.")
    output.mkdir(parents=True, exist_ok=True)
    painters = {theme: Painter(profile, theme, font_path) for theme in THEMES}
    palettes = {theme: global_palette(theme) for theme in THEMES}
    frames = {theme: [] for theme in THEMES}
    samples = []
    starts = [shape_at(i, 0) for i in range(len(CONCEPTS))]

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
            append(shape_at(index, frame / (hold_frames - 1)), index)
        pairs = particle_pairs(shape_at(index, 1), starts[(index + 1) % len(CONCEPTS)])
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
            state.update(kind="rotation", rotation_degrees=round(math.degrees(motion.travel), 1))
        else:
            state.update(kind="wave", wave_cycles=motion.cycles)
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

    sheet = Image.new("RGB", (WIDTH, len(CONCEPTS) * 322), THEMES["dark"]["background"])
    draw = ImageDraw.Draw(sheet)
    for row, (name, shape_frame, morph_frame) in enumerate(samples):
        draw.text((16, row * 322 + 5), name + " / motion                           transition / scattered characters",
                  font=painters["dark"].font(12), fill=THEMES["dark"]["text"])
        for col, frame in enumerate((shape_frame, morph_frame)):
            with Image.open(BytesIO(frames["dark"][frame])) as sample:
                sheet.paste(sample.convert("RGB").resize((560, 300), Image.Resampling.LANCZOS), (col * 560, row * 322 + 22))
    sheet.save(output / "motion-contact-sheet.jpg", quality=90)
    (output / "motion-embed.html").write_text(animation_embed(profile), encoding="utf-8")
    (output / "motion.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Complete: {sum(durations) / 1000:g}-second seamless sequence, both themes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "profile.json")
    parser.add_argument("--output", type=Path, default=ROOT / "assets")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--fps", type=int, choices=(10, 20, 25), default=20)
    parser.add_argument("--hold", type=float, default=7.0, help="Seconds of rotation per shape")
    parser.add_argument("--transition", type=float, default=2.0, help="Seconds of particle motion per transition")
    args = parser.parse_args()
    generate(args.config, args.output, find_font(args.font), args.fps, args.hold, args.transition)
