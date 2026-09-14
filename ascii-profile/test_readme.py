"""Check profile typography, link targets, and generated README assets."""

import copy
import hashlib
import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from generate import PROFILE_END, PROFILE_START, ROOT, generate, information_svg, profile_panel, write_readme


SVG = {"svg": "http://www.w3.org/2000/svg"}


class ProfileHTML(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.tags = []
        self.links = []
        self.images = []
        self.image_links = []
        self.sources = []
        self.text = []
        self.active_link = None
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append(tag)
        if tag == "a":
            self.links.append(attributes["href"])
            self.active_link = attributes["href"]
        if tag == "img":
            self.images.append(attributes)
            self.image_links.append(self.active_link)
        if tag == "source":
            self.sources.append(attributes)

    def handle_data(self, data):
        self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "a":
            self.active_link = None


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / "profile.json").read_text())

    def test_terminal_profile_has_aligned_fields_and_even_metric_columns(self):
        svg = ElementTree.fromstring(information_svg(self.profile, "dark"))
        labels = svg.findall("svg:text", SVG)
        for field in self.profile["fields"]:
            label = next(node for node in labels if node.text == field["label"])
            self.assertEqual(float(label.attrib["x"]), 40)
        metrics = [svg.find(f"svg:text[@id='metric-{index}']", SVG) for index in range(3)]
        positions = [float(metric.attrib["x"]) for metric in metrics]
        self.assertEqual(positions, [40, 220, 400])
        self.assertEqual(positions[1] - positions[0], positions[2] - positions[1])
        for metric, configuration in zip(metrics, self.profile["metrics"]):
            label = next(node for node in labels if node.text == configuration["label"])
            self.assertEqual(metric.attrib["x"], label.attrib["x"])
            self.assertEqual(metric.attrib.get("text-anchor", "start"), "start")
            self.assertEqual(label.attrib.get("text-anchor", "start"), "start")

    def test_profile_card_is_themed_clickable_and_has_complete_alternative_text(self):
        document = ProfileHTML(profile_panel(self.profile))
        self.assertEqual(len(document.images), 1)
        self.assertEqual(document.images[0]["src"], "ascii-profile/assets/profile-light.svg")
        self.assertEqual(document.images[0]["width"], "600")
        self.assertNotIn("height", document.images[0])
        self.assertEqual(document.sources, [{"media": "(prefers-color-scheme: dark)", "srcset": "ascii-profile/assets/profile-dark.svg"}])
        self.assertEqual(document.image_links, ["https://www.linkedin.com/in/ranjrashid/"])
        text = document.images[0]["alt"]
        for value in (self.profile["name"], self.profile["tagline"], "Software Engineer", "Erbil, Iraq", "KRG Projects", "C#", "Rust", ".NET", "PostgreSQL"):
            self.assertEqual(text.count(value), 1, value)
        for metric in self.profile["metrics"]:
            self.assertIn(f"{metric['label']}: {metric['value']}", text)
        self.assertIn(self.profile["note"], text)
        self.assertIn("Open LinkedIn profile.", text)
        self.assertEqual("".join(document.text).strip(), "")
        self.assertTrue(set(document.tags) <= {"p", "a", "picture", "source", "img"})

    def test_svg_uses_terminal_typography_and_displays_each_detail_once(self):
        for theme in ("dark", "light"):
            with self.subTest(theme=theme):
                svg = ElementTree.fromstring(information_svg(self.profile, theme))
                self.assertEqual(svg.attrib["viewBox"], "0 0 600 480")
                self.assertIn("Terminal manifest", svg.find("svg:title", SVG).text)
                self.assertIn('"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace', svg.find("svg:style", SVG).text)
                labels = svg.findall("svg:text", SVG)
                text = [label.text for label in labels]
                self.assertIn("> whoami", text)
                self.assertIn("[ manifest ]", text)
                self.assertEqual(text.count("::"), 5)
                self.assertIn("┌" + "─" * 66 + "┐", text)
                self.assertIn("└" + "─" * 66 + "┘", text)
                expected = [self.profile["name"], self.profile["tagline"], self.profile["note"]]
                expected += [field[key] for field in self.profile["fields"] for key in ("label", "value")]
                expected += [metric["label"] for metric in self.profile["metrics"]]
                for value in expected:
                    self.assertEqual(text.count(value), 1, value)
                name = next(label for label in labels if label.text == self.profile["name"])
                self.assertEqual(name.attrib["font-size"], "34.00")
                self.assertEqual(name.attrib["font-weight"], "600")
                for index, field in enumerate(self.profile["fields"]):
                    value = next(label for label in labels if label.text == field["value"])
                    self.assertEqual(value.attrib["x"], "174")
                    self.assertEqual(value.attrib["y"], str(208 + index * 30))
                    if field["label"] == "website":
                        self.assertEqual(value.attrib["text-decoration"], "underline")
                for index, metric in enumerate(self.profile["metrics"]):
                    self.assertEqual(svg.find(f"svg:text[@id='metric-{index}']", SVG).text, f'[{metric["value"]}]')
                self.assertTrue({node.tag.split("}")[-1] for node in svg.iter()} <= {"svg", "title", "desc", "style", "rect", "path", "text"})

    def test_personal_text_is_escaped_and_unsafe_links_are_rejected(self):
        self.profile["name"] = '<script>alert("name")</script>'
        document = ProfileHTML(profile_panel(self.profile))
        self.assertNotIn("script", document.tags)
        self.assertIn(self.profile["name"], document.images[0]["alt"])
        svg = ElementTree.fromstring(information_svg(self.profile, "dark"))
        self.assertIsNone(svg.find(".//svg:script", SVG))
        self.assertIn(self.profile["name"], [node.text for node in svg.findall("svg:text", SVG)])
        website = next(field for field in self.profile["fields"] if field["label"] == "website")
        for href in ("javascript:alert(1)", "http://example.com", "https:///missing-host"):
            website["href"] = href
            with self.subTest(href=href), self.assertRaises(ValueError):
                profile_panel(self.profile)

    def test_public_stat_changes_update_only_the_count_and_accessible_description(self):
        for index, metric in enumerate(self.profile["metrics"]):
            for theme in ("dark", "light"):
                with self.subTest(metric=metric["label"], theme=theme):
                    changed = copy.deepcopy(self.profile)
                    count = str(int(metric["value"]) + 1)
                    changed["metrics"][index]["value"] = count
                    before = information_svg(self.profile, theme)
                    after = information_svg(changed, theme)
                    expected = before.replace(f'id="metric-{index}">[{metric["value"]}]</text>', f'id="metric-{index}">[{count}]</text>')
                    expected = expected.replace(f'{metric["label"]}: {metric["value"]}', f'{metric["label"]}: {count}')
                    self.assertNotEqual(before, after)
                    self.assertEqual(expected, after)
                    self.assertIn(f'{metric["label"]}: {count}', ProfileHTML(profile_panel(changed)).images[0]["alt"])

    def test_readme_updates_preserve_content_outside_the_generated_section(self):
        with tempfile.TemporaryDirectory() as directory:
            readme = Path(directory) / "README.md"
            readme.write_text(f"My projects\n{PROFILE_START}\nOld profile\n{PROFILE_END}\nContact me\n")
            write_readme(readme, "New profile\n")
            expected = f"My projects\n{PROFILE_START}\nNew profile\n{PROFILE_END}\nContact me\n"
            self.assertEqual(readme.read_text(), expected)
            write_readme(readme, "New profile\n")
            self.assertEqual(readme.read_text(), expected)
            for contents in ("Handwritten README\n", f"{PROFILE_END}\n{PROFILE_START}", f"{PROFILE_START}\n{PROFILE_START}\n{PROFILE_END}"):
                readme.write_text(contents)
                with self.subTest(contents=contents), self.assertRaises(ValueError):
                    write_readme(readme, "Replacement\n")
                self.assertEqual(readme.read_text(), contents)

    def test_generated_readme_matches_the_gallery_and_preserves_motion_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "preview"
            assets = output / "assets"
            assets.mkdir(parents=True)
            for name in ("motion.json", "motion-embed.html"):
                (assets / name).write_bytes((ROOT / "assets" / name).read_bytes())
            animation_hashes = {}
            for name in ("motion-dark.gif", "motion-light.gif"):
                content = (ROOT / "assets" / name).read_bytes()
                (assets / name).write_bytes(content)
                animation_hashes[name] = hashlib.sha256(content).hexdigest()
            readme = Path(directory) / "README.md"
            generate(ROOT / "profile.json", output, readme)
            actual = readme.read_text()
            panel = profile_panel(self.profile)
            expected = (assets / "motion-embed.html").read_text() + "\n" + panel
            marked = PROFILE_START + "\n" + expected + PROFILE_END + "\n"
            self.assertEqual(actual, marked)
            self.assertIn(marked, (ROOT.parent / "README.md").read_text())
            document = ProfileHTML(actual)
            self.assertEqual(len(document.images), 2)
            for image in document.images:
                self.assertEqual(image["width"], "600")
                self.assertNotIn("height", image)
            self.assertNotIn(self.profile["name"], document.images[0]["alt"])
            self.assertIn(self.profile["name"], document.images[1]["alt"])
            self.assertEqual(document.image_links, [None, "https://www.linkedin.com/in/ranjrashid/"])
            self.assertIn("prefers-reduced-motion: reduce", actual)
            self.assertIn("prefers-color-scheme: dark", actual)
            gallery = (output / "index.html").read_text()
            self.assertIn(profile_panel(self.profile, prefix="assets/"), gallery)
            self.assertNotIn("__PROFILE_", gallery)
            self.assertLess(actual.index("motion-light.gif"), actual.index("profile-light.svg"))
            self.assertEqual("".join(document.text).strip(), "")
            for theme in ("dark", "light"):
                self.assertEqual((assets / f"profile-{theme}.svg").read_text(), information_svg(self.profile, theme))
                self.assertEqual((ROOT / "assets" / f"profile-{theme}.svg").read_text(), information_svg(self.profile, theme))
            for name, expected_hash in animation_hashes.items():
                self.assertEqual(hashlib.sha256((assets / name).read_bytes()).hexdigest(), expected_hash)


if __name__ == "__main__":
    unittest.main()
