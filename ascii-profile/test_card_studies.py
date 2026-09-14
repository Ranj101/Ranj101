"""Check the isolated card proposals and the data shown in both themes."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

from card_studies import RENDERERS, ROOT, STUDIES, generate_studies, palette
from generate import information_svg, profile_description
from test_readme import ProfileHTML


SVG = {"svg": "http://www.w3.org/2000/svg"}


def contrast(first, second):
    def luminance(color):
        channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
        return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


class CardStudyTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / "profile.json").read_text())

    def test_terminal_study_matches_the_production_card(self):
        for theme in ("dark", "light"):
            with self.subTest(theme=theme):
                expected = information_svg(self.profile, theme)
                self.assertEqual(RENDERERS["terminal"](STUDIES[0], self.profile, theme), expected)
                self.assertEqual((ROOT / "assets" / "card-studies" / f"terminal-{theme}.svg").read_text(), expected)

    def test_three_distinct_self_contained_designs_preserve_profile_content(self):
        self.assertEqual(len(STUDIES), 3)
        designs = set()
        for study in STUDIES:
            for theme in ("dark", "light"):
                with self.subTest(design=study.key, theme=theme):
                    source = RENDERERS[study.key](study, self.profile, theme)
                    designs.add(source)
                    svg = ElementTree.fromstring(source)
                    self.assertEqual(svg.attrib["width"], "600")
                    self.assertEqual(svg.find("svg:desc", SVG).text, profile_description(self.profile))
                    self.assertIn(self.profile["name"], svg.find("svg:title", SVG).text)
                    labels = ["".join(node.itertext()) for node in svg.findall(".//svg:text", SVG)]
                    visible = " ".join(labels)
                    for field in self.profile["fields"]:
                        for value in field["value"].split(" · "):
                            self.assertIn(value, visible)
                    for metric in self.profile["metrics"]:
                        self.assertIn(metric["label"], visible)
                        self.assertIn(metric["value"], visible)
                    self.assertIn(self.profile["note"], visible)
                    self.assertTrue({node.tag.split("}")[-1] for node in svg.iter()} <= {"svg", "title", "desc", "style", "rect", "text", "tspan", "g"})
                    self.assertNotIn("url(", source)
        self.assertEqual(len(designs), 6)

    def test_normal_text_colors_meet_wcag_aa_in_both_themes(self):
        for study in STUDIES:
            for theme in ("dark", "light"):
                colors = palette(study, theme)
                for role in ("text", "muted", "accent"):
                    with self.subTest(design=study.key, theme=theme, role=role):
                        self.assertGreaterEqual(contrast(colors[role], colors["background"]), 4.5)

    def test_personal_text_is_escaped_and_unmapped_names_still_render(self):
        profile = copy.deepcopy(self.profile)
        profile["name"] = '<script>alert("name")</script>'
        for study in STUDIES:
            svg = ElementTree.fromstring(RENDERERS[study.key](study, profile, "dark"))
            self.assertIsNone(svg.find(".//svg:script", SVG))
            self.assertIn(profile["name"], svg.find("svg:desc", SVG).text)
            self.assertIn(profile["name"], " ".join("".join(node.itertext()) for node in svg.findall(".//svg:text", SVG)))

    def test_generator_is_repeatable_and_keeps_the_proposals_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            generate_studies(ROOT / "profile.json", output)
            before = {path.relative_to(output): hashlib.sha256(path.read_bytes()).hexdigest() for path in output.rglob("*") if path.is_file()}
            self.assertEqual(len(before), 7)
            self.assertFalse((output / "README.md").exists())
            self.assertFalse((output / "assets" / "motion-dark.gif").exists())
            document = ProfileHTML((output / "card-studies.html").read_text())
            linked_cards = [link for image, link in zip(document.images, document.image_links) if "card-studies/" in image["src"]]
            self.assertEqual(linked_cards, ["https://www.linkedin.com/in/ranjrashid/"] * 3)
            generate_studies(ROOT / "profile.json", output)
            after = {path.relative_to(output): hashlib.sha256(path.read_bytes()).hexdigest() for path in output.rglob("*") if path.is_file()}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
