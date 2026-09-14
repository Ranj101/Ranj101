"""Check geometry, particle paths, and the actual exported GIFs."""

import json
import hashlib
import unittest

from PIL import Image, ImageChops, ImageColor, ImageSequence

from animate import ART_BOUNDS, CONCEPTS, HEIGHT, MOTIONS, ROOT, WIDTH, Glyph, Painter, Rotation, Wave, concept_at, find_font, global_palette, mix, morph, particle_pairs, shape_at, smooth
from generate import COLS, PROFILE_INSET, PROFILE_WIDTH, ROWS, TERRAIN_AMPLITUDES, TERRAIN_BASE, TERRAIN_HALF_EXTENT, rotate, terrain, terrain_height


class AnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.starts = [shape_at(i, 0) for i in range(len(CONCEPTS))]
        cls.ends = [shape_at(i, 1) for i in range(len(CONCEPTS))]
        cls.painter = Painter("dark", find_font(None))
        cls.palette = global_palette("dark")

    def art(self, particles):
        image = self.painter.frame(particles, (125, 211, 252), 0)
        return image.quantize(palette=self.palette, dither=Image.Dither.NONE).convert("RGB").crop(ART_BOUNDS)

    def test_art_stage_has_no_sidebar_or_personal_information(self):
        self.assertGreater((ART_BOUNDS[2] - ART_BOUNDS[0]) / WIDTH, 0.90)
        self.assertEqual(self.painter.base.getextrema(), ((13, 13), (17, 17), (23, 23)))

    def test_geometry_is_centered_on_the_profile_column(self):
        for index in (0, 1, 2, 3, 6, 7):
            for progress in (0, 0.5, 1):
                with self.subTest(shape=CONCEPTS[index].key, progress=progress):
                    frame = self.painter.frame(shape_at(index, progress), (125, 211, 252), index)
                    bounds = ImageChops.difference(frame, self.painter.base).crop(ART_BOUNDS).getbbox()
                    center = ART_BOUNDS[0] + (bounds[0] + bounds[2]) / 2
                    self.assertAlmostEqual(center, WIDTH / 2, delta=2)

    def test_animation_caption_aligns_with_profile_text(self):
        frame = self.painter.frame([], (125, 211, 252), 0)
        bounds = ImageChops.difference(frame, self.painter.base).getbbox()
        self.assertAlmostEqual(bounds[0] * PROFILE_WIDTH / WIDTH, PROFILE_INSET, delta=2)
        self.assertLessEqual(bounds[2] * PROFILE_WIDTH / WIDTH, PROFILE_WIDTH - PROFILE_INSET + 1)

    def test_complete_character_grid_fits_with_ink_clearance(self):
        corners = [Glyph(x, y, chr(code), 1) for x in (34, 34 + (COLS - 1) * 7.3)
                   for y in (119, 119 + (ROWS - 1) * 11.2) for code in range(33, 127)]
        frame = self.painter.frame(corners, (125, 211, 252), 0)
        bounds = ImageChops.difference(frame, self.painter.base).crop((0, 0, WIDTH, 528)).getbbox()
        self.assertGreaterEqual(bounds[0], ART_BOUNDS[0])
        self.assertGreaterEqual(bounds[1], ART_BOUNDS[1])
        self.assertLessEqual(bounds[2], ART_BOUNDS[2])
        self.assertLessEqual(bounds[3], ART_BOUNDS[3])

    def test_compact_stage_preserves_clearance_for_every_shape_and_transition(self):
        for index in range(len(CONCEPTS)):
            pairs = particle_pairs(self.ends[index], self.starts[(index + 1) % len(CONCEPTS)])
            for progress in (0, 0.125, 0.25, 0.5, 0.75, 0.875, 1):
                for particles in (shape_at(index, progress), morph(pairs, progress)):
                    frame = self.painter.frame(particles, (125, 211, 252), index)
                    bounds = ImageChops.difference(frame, self.painter.base).crop((0, 0, WIDTH, 528)).getbbox()
                    with self.subTest(shape=CONCEPTS[index].key, progress=progress):
                        self.assertGreaterEqual(bounds[0], ART_BOUNDS[0])
                        self.assertGreaterEqual(bounds[1], ART_BOUNDS[1])
                        self.assertLessEqual(bounds[2], ART_BOUNDS[2])
                        self.assertLessEqual(bounds[3], ART_BOUNDS[3])

    def test_every_rotation_moves(self):
        for index in range(len(CONCEPTS)):
            if not isinstance(MOTIONS[CONCEPTS[index].key], Rotation):
                continue
            with self.subTest(shape=CONCEPTS[index].name):
                self.assertNotEqual(self.starts[index], self.ends[index])
                self.assertIsNotNone(ImageChops.difference(self.art(self.starts[index]), self.art(self.ends[index])).getbbox())

    def test_previous_rotation_speeds_are_preserved(self):
        expected = {"01-cube": 0.70, "02-torus": 0.62, "03-orbit": 0.65, "04-crystal": -0.85,
                    "06-twist": -0.60, "07-chain": 0.70, "08-gyroid": 0.65}
        for key, travel in expected.items():
            self.assertEqual(MOTIONS[key].travel, travel)

    def test_terrain_deforms_without_rotating(self):
        index = next(i for i, concept in enumerate(CONCEPTS) if concept.key == "05-terrain")
        self.assertIsInstance(MOTIONS["05-terrain"], Wave)
        for progress in (0, 0.125, 0.25, 0.375, 1):
            self.assertEqual(concept_at(index, progress).rotation, CONCEPTS[index].rotation)
        self.assertNotEqual(shape_at(index, 0), shape_at(index, 0.125))
        self.assertNotEqual(concept_at(index, 0).distance((0.2, 0.1, 0.3)), concept_at(index, 0.125).distance((0.2, 0.1, 0.3)))
        self.assertEqual(shape_at(index, 0), shape_at(index, 1))

    def test_terrain_crests_fit_fixed_view(self):
        concept = next(concept for concept in CONCEPTS if concept.key == "05-terrain")
        for basis, limit in (((0, 1, 0), 3.25 / 2), ((1, 0, 0), COLS / 2 / ROWS * 3.25 * 7.3 / 11.2)):
            axis = rotate(basis, concept.rotation)
            height = max(abs(TERRAIN_BASE), sum(TERRAIN_AMPLITUDES)) + 0.01
            extent = (TERRAIN_HALF_EXTENT + 0.01) * (abs(axis[0]) + abs(axis[2])) + height * abs(axis[1])
            self.assertLess(extent, limit)

    def test_terrain_has_compact_solid_depth_and_lower_crests(self):
        self.assertLessEqual(TERRAIN_HALF_EXTENT, 1.10)
        self.assertLess(sum(TERRAIN_AMPLITUDES), 0.30)
        for phase in (0, 0.7, 1.8, 3.0, 5.2):
            for x, z in ((0, 0), (-0.75, -0.6), (0.6, 0.8)):
                top = terrain_height(x, z, phase)
                self.assertGreater(top - TERRAIN_BASE, 0.14)
                self.assertLess(terrain((x, top - 0.10, z), phase), 0)
                self.assertLess(terrain((x, TERRAIN_BASE + 0.05, z), phase), 0)
                self.assertGreater(terrain((x, TERRAIN_BASE - 0.02, z), phase), 0)

    def test_terrain_surface_has_shading_instead_of_sparse_grid(self):
        for progress in (0, 0.125, 0.25, 0.375):
            glyphs = shape_at(4, progress)
            shaded = [glyph for glyph in glyphs if glyph.char in "irsXA25hMH#@"]
            self.assertGreater(len(shaded), len(glyphs) * 0.55)
            self.assertGreater(max(g.intensity for g in glyphs) - min(g.intensity for g in glyphs), 0.40)

    def test_terrain_view_is_above_the_surface(self):
        concept = next(concept for concept in CONCEPTS if concept.key == "05-terrain")
        toward_camera = rotate((0, 0, 1), concept.rotation)
        self.assertGreater(toward_camera[1], 0)

    def test_particle_endpoints_reconstruct_exactly(self):
        for index in range(len(CONCEPTS)):
            source, target = self.ends[index], self.starts[(index + 1) % len(CONCEPTS)]
            pairs = particle_pairs(source, target)
            with self.subTest(shape=CONCEPTS[index].name):
                self.assertIsNone(ImageChops.difference(self.art(source), self.art(morph(pairs, 0))).getbbox())
                self.assertIsNone(ImageChops.difference(self.art(target), self.art(morph(pairs, 1))).getbbox())

    def test_particles_travel_and_stay_inside_art_panel(self):
        for index in range(len(CONCEPTS)):
            pairs = particle_pairs(self.ends[index], self.starts[(index + 1) % len(CONCEPTS)])
            midpoint = morph(pairs, 0.5)
            travelled = sum(abs(g.x - a.x) + abs(g.y - a.y) > 45 for g, (a, _) in zip(midpoint, pairs))
            self.assertGreater(travelled, len(pairs) * 0.5)
            for frame in range(37):
                for glyph in morph(pairs, frame / 36):
                    self.assertGreaterEqual(glyph.x, 30)
                    self.assertLessEqual(glyph.x + 12, 551)
                    self.assertGreaterEqual(glyph.y - 14, 98)
                    self.assertLessEqual(glyph.y + 6, 500)

    def test_encoded_gifs_have_correct_timing_and_seamless_geometry(self):
        assets = ROOT / "assets"
        manifest = json.loads((assets / "motion.json").read_text())
        for theme in ("dark", "light"):
            with self.subTest(theme=theme), Image.open(assets / f"motion-{theme}.gif") as animation:
                base = Painter(theme, find_font(None)).base
                self.assertEqual(animation.size, (WIDTH, HEIGHT))
                self.assertEqual(animation.size, (manifest["width"], manifest["height"]))
                self.assertEqual(animation.info["loop"], 0)
                first = animation.convert("RGB")
                duration = 0
                seen = set()
                for frame in ImageSequence.Iterator(animation):
                    rendered = frame.convert("RGB")
                    bounds = ImageChops.difference(rendered, base).crop((0, 0, WIDTH, 528)).getbbox()
                    self.assertGreaterEqual(bounds[0], ART_BOUNDS[0])
                    self.assertGreaterEqual(bounds[1], ART_BOUNDS[1])
                    self.assertLessEqual(bounds[2], ART_BOUNDS[2])
                    self.assertLessEqual(bounds[3], ART_BOUNDS[3])
                    self.assertGreaterEqual(frame.info["duration"], 1000 / manifest["fps"])
                    seen.add(hashlib.sha256(rendered.crop(ART_BOUNDS).tobytes()).digest())
                    duration += frame.info["duration"]
                self.assertEqual(duration, manifest["duration_ms"])
                self.assertGreater(len(seen), manifest["frames"] * 0.85)
                seam = ImageChops.difference(first.crop(ART_BOUNDS), rendered.crop(ART_BOUNDS))
                self.assertIsNone(seam.getbbox())
                with Image.open(assets / f"motion-{theme}-poster.png") as poster:
                    self.assertIsNone(ImageChops.difference(first, poster.convert("RGB")).getbbox())

    def test_encoded_samples_match_renderer(self):
        assets = ROOT / "assets"
        manifest = json.loads((assets / "motion.json").read_text())
        hold, transition, fps = (manifest[key] for key in ("hold_frames", "transition_frames", "fps"))
        for theme in ("dark", "light"):
            painter, palette = Painter(theme, find_font(None)), global_palette(theme)
            samples = {}
            for index, concept in enumerate(CONCEPTS):
                accent = ImageColor.getrgb(getattr(concept, theme))
                for phase_frame in (hold // 2, hold + transition // 2):
                    progress = None
                    color = accent
                    if phase_frame < hold:
                        particles = shape_at(index, phase_frame / (hold - 1))
                    else:
                        progress = (phase_frame - hold + 1) / transition
                        pairs = particle_pairs(self.ends[index], self.starts[(index + 1) % len(CONCEPTS)])
                        particles = morph(pairs, progress)
                        next_accent = ImageColor.getrgb(getattr(CONCEPTS[(index + 1) % len(CONCEPTS)], theme))
                        color = mix(accent, next_accent, smooth(progress))
                    frame = painter.frame(particles, color, index, progress)
                    timestamp = (index * (hold + transition) + phase_frame) * 1000 / fps
                    samples[timestamp] = frame.quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB")
            with Image.open(assets / f"motion-{theme}.gif") as animation:
                elapsed = 0
                checked = 0
                for frame in ImageSequence.Iterator(animation):
                    duration = frame.info["duration"]
                    for timestamp, expected in samples.items():
                        if elapsed <= timestamp < elapsed + duration:
                            with self.subTest(theme=theme, time_ms=timestamp):
                                self.assertIsNone(ImageChops.difference(expected, frame.convert("RGB")).getbbox())
                                checked += 1
                    elapsed += duration
                self.assertEqual(checked, len(CONCEPTS) * 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
