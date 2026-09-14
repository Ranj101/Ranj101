# ASCII profile studies

The profile stacks a centered ASCII animation above the Terminal manifest SVG card. The card uses character-drawn borders, a command prompt, aligned fields, and bracketed statistics. Clicking it opens LinkedIn. Each detail appears once, and statistics can update without rebuilding the GIF. Eight earlier SVG card studies remain in the local gallery.

## Compare information-card designs

Open [card-studies.html](card-studies.html) to compare the selected Terminal manifest card with two alternatives, Glyph signature and Source file. Each has a light and dark SVG. Select a design to preview it below the existing geometry, switch to the 390-pixel card width, or play the animation. Playback starts only when you select **Play geometry**. The information cards stay still.

The comparison gallery uses the same Terminal manifest renderer as the published profile. All three designs read the public information from `profile.json`, and each card links to LinkedIn. The character-built name in Glyph signature uses a small glyph alphabet for the current name; other names fall back to normal monospace text. To refresh the comparison gallery after changing the profile, run:

```sh
python3 ascii-profile/card_studies.py
```

This command writes only `card-studies.html` and `assets/card-studies/`. It does not change the README, production information card, or animation. Edit `information_svg` in `generate.py` for Terminal manifest, `card_studies.py` for the alternatives, and `card-studies.template.html` for the comparison page. Regenerate the assets after editing their source.

## Review the concepts

Open `index.html` in a browser. The gallery works from disk with no server or dependencies. It opens the current animation layout at GitHub's approximate 830-pixel content width. Switch themes and select the 390-pixel mobile preview to check the scaled layout. The animation and information card each display at up to 600 pixels wide and shrink on narrower screens without changing their proportions.

| Concept | Geometry | Character |
| --- | --- | --- |
| 01 | Isometric cube | Structured, architectural, cyan |
| 02 | Torus | Curved, shaded, amber |
| 03 | Orbital sphere | Shaded globe, meridians, and two orbital rings, green |
| 04 | Faceted crystal | Elongated octahedron, violet |
| 05 | Terrain wave | Compact shaded tile with smaller traveling ripples, coral |
| 06 | Twisted column | Helical square column, periwinkle |
| 07 | Interlocking chain | Three links in alternating planes, chartreuse |
| 08 | Gyroid lattice | Curved channels inside a cubic guide frame, rose |

The profile contains the supplied role, location, current work, and LinkedIn address. The selected tagline is "Building dependable software for public services." The selected stack is C#, Rust, .NET, and PostgreSQL. The three statistics use public GitHub data only.

## Update public statistics

`update_stats.py` updates these metrics in `profile.json`:

| Metric | Definition |
| --- | --- |
| Public repos | Public repositories owned by the configured handle, including forks. Organization repositories and private repositories are excluded. |
| Stars received | Stars received by owned public non-fork repositories. This is not the number of repositories the user has starred. |
| Followers | The follower count visible on the public GitHub profile. |

The updater makes anonymous requests to GitHub's [public user endpoint](https://docs.github.com/en/rest/users/users#get-a-user) and [public repository endpoint](https://docs.github.com/en/rest/repos/repos#list-repositories-for-a-user). It does not read local GitHub credentials, token environment variables, or private endpoints. Only the aggregate counts are saved. Repository names and API responses are not stored.

To refresh the counts and information cards locally, use Python 3.12 with the test dependencies installed. Existing GIFs do not need to be regenerated:

```sh
python3 ascii-profile/update_stats.py
python3 ascii-profile/generate.py --readme README.md
python3 ascii-profile/card_studies.py
python3 -m unittest discover -s ascii-profile -p 'test_*.py'
```

Run `python3 ascii-profile/update_stats.py --check` to compare saved values against GitHub without writing files. It exits with status 1 when the values need updating. Network or validation failures leave the saved profile unchanged. A refresh with unchanged values does not rewrite the file.

### Automatic refresh

The workflow in [update-profile-stats.yml](../.github/workflows/update-profile-stats.yml) runs on `main`:

- Daily at 05:17 UTC, which is 08:17 in Erbil.
- After pushes that change the profile configuration, renderer, updater, gallery template, dependency file, or workflow.
- When you select **Actions → Update public profile statistics → Run workflow**.

After fetching changed statistics, the workflow refreshes the Terminal manifest card, README, alternative card designs, earlier SVG studies, and both galleries. Scheduled runs do not rebuild the GIFs because personal information is separate from the animation. Scheduled runs with unchanged counts do not rewrite the generated files. Pushes and manual runs also rebuild both animation themes and their posters. The workflow runs the tests before committing the changed profile data, generated README section, and assets. It never force-pushes. A concurrent push can cause its final push to fail safely; rerun the workflow against the latest `main`.

No personal access token or custom secret is required. Public data is fetched anonymously. The workflow uses its repository-scoped `GITHUB_TOKEN` only for checkout and the generated-file commit. Its job requests `contents: write`; repository rules must allow that bot commit to `main`. It uses a macOS runner for the same Menlo font as the reviewed preview and pins Pillow to the tested version. No font file is redistributed.

The workflow is installed on `main`; changes to it take effect after a push. GitHub can delay scheduled runs, and public repositories can have schedules disabled after 60 days without activity. Use the manual run when needed. See [GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Animated version

Select **Play animation** in the gallery. The preview starts still; **Stop animation** returns to its poster. Theme switching works for both the GIF and the poster. Reduced-motion preferences stop playback, and the README embed selects a still image when reduced motion is requested. Its image has no fixed display height, so narrow layouts preserve the artwork's aspect ratio.

The animation has an 840 × 588 source canvas and displays at 600 × 420 pixels in the desktop README. The shallower stage gives the information card more space in the first screenful. Glyph spacing is about 13% smaller than the preceding version, and the character grid is centered using the font's advance and ink bounds. It scales down further on narrower screens without distortion.

All personal information sits below the geometry in one 600 × 480 Terminal manifest SVG card. It keeps the SFMono-Regular, Consolas, Liberation Mono, Menlo, and monospace font stack. Box-drawing characters frame the card. Its prompt, field labels, and first statistic start at a 40-pixel inset. Values align after `::` separators, and the three bracketed counts start 180 pixels apart. The public-data note sits beneath the counts. The website is underlined, and the entire card links to LinkedIn through an HTML anchor around its themed `<picture>`. Individual regions of an embedded image are not separate links. The source configuration stores the full HTTPS address in the website field's `href`. The image's alternative text includes the personal details, current counts, and link destination. No external font or image is loaded by the SVG.

The loop lasts 40 seconds at a 20 fps render cadence. Each shape moves for 3 seconds and reconstructs over the next 2 seconds. Cube, crystal, column, and lattice rotate around Y; the torus and chain around X; and the orbital sphere around Z. The crystal and column turn in the opposite direction. Rotation speed is independent of the phase duration. The previous slow pace is preserved, with approximately 15–21 degrees of travel during each shorter phase.

Terrain is a separate wave motion, not a rotation. Its viewpoint stays fixed above the surface while two sine waves change the height of a solid tile. Its wave period remains 3.5 seconds, so the shorter phase shows about 0.86 cycles. `Rotation` and `Wave` have separate records in the keyed `MOTIONS` registry, so terrain does not have a rotation axis or angular travel.

The generator reuses the distance fields in `generate.py`, rotates or deforms the geometry, and samples fresh ASCII characters for each frame. The globe has a filled, shaded surface with less crowded coordinate lines. The terrain uses dense surface shading, darker solid sides, and smaller ripples. Its width and depth are about 25% smaller than the earlier sheet, and its maximum wave amplitude is about 56% lower. `TERRAIN_HALF_EXTENT`, `TERRAIN_BASE`, and `TERRAIN_AMPLITUDES` in `generate.py` control its footprint, depth, and wave height. The gyroid has thicker walls, depth shading, and a cubic guide frame to make the curved channels easier to follow.

During transitions, characters become particles: they leave their grid cells, follow curved paths through a loose swirl, and settle into the next shape. The accent color blends at the same time. The information card stays still below the animation. The last transition reconstructs the first cube orientation to close the loop.

`animate.py` renders those frames with Pillow and encodes two GIFs with a shared palette per theme, no dithering, and optimized delta frames. [Pillow's GIF writer](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#gif) stores the frame durations and infinite-loop setting. It may merge identical neighboring frames while retaining their combined duration. Exact sizes and encoded frame counts are in `assets/motion.json`. Intermediate frames are compressed in memory to avoid retaining the full uncompressed sequence. The animation renderer does not read profile data.

To regenerate, install the animation dependency in your Python environment and run:

```sh
python3 -m pip install -r ascii-profile/requirements-animation.txt
python3 ascii-profile/animate.py
python3 ascii-profile/generate.py --readme README.md
python3 ascii-profile/card_studies.py
python3 -m unittest discover -s ascii-profile -p 'test_*.py'
```

The SVG generator still needs only the standard library. The animation uses a locally installed monospace font: Menlo on macOS, DejaVu Sans Mono or Liberation Mono on Linux, or Consolas on Windows. Pass `--font /path/to/font.ttf` to select one explicitly. No font file is redistributed.

The timing controls are `--hold`, `--transition`, and `--fps` (10, 20, or 25). For example, `python3 ascii-profile/animate.py --hold 7 --transition 2 --fps 20` restores the previous 72-second loop with the eight current shapes. Edit the keyed `MOTIONS` entries to adjust rotation axes and mean radians per second or the terrain's cycles per second. Regenerate the gallery after every export to refresh its size, duration, and embed information.

The animation assets are:

- `assets/motion-dark.gif` and `assets/motion-light.gif`: looping README images.
- `assets/motion-dark-poster.png` and `assets/motion-light-poster.png`: still fallbacks.
- `assets/motion-embed.html`: geometry-only embed with theme-aware reduced-motion fallbacks. The gallery's copy control includes the linked information card as well.
- `assets/motion-contact-sheet.jpg`: one motion and one transition still for each shape.
- `assets/profile-dark.svg` and `assets/profile-light.svg`: separate information cards, regenerated when profile data or public statistics change.

The gallery can stop the animation by switching to its poster. A standalone GIF cannot offer its own playback controls, so the README embed also provides reduced-motion stills. GitHub [removes scripts and custom styles from README HTML](https://github.com/github/markup). An interactive canvas cannot run there. The separate SVG preserves the profile typography, its surrounding HTML link remains clickable, and statistics refresh through Actions rather than browser-side JavaScript.

## Edit and regenerate

Edit `profile.json`, then run these commands from the repository root with Python 3.9 or later:

```sh
python3 ascii-profile/generate.py --readme README.md
python3 ascii-profile/card_studies.py
```

The generator writes both information-card themes, plus two SVG themes, a plain ASCII file, and a README embed for each earlier concept in `assets/`. It also rebuilds `index.html` from `gallery.template.html`. Edit the template, not the generated gallery. The optional `--readme` path updates the linked profile card and animation section between `PROFILE:START` and `PROFILE:END` comments. Put handwritten additions outside those markers. Missing, repeated, or reversed markers stop the README update without replacing its content.

The configuration has five information fields and three metrics. Both arrays are in `profile.json`. SVG text keeps its alignment as the card scales, and longer values shrink to fit their columns. Preview long replacements before publishing, especially at mobile width. The statistics updater owns the three metrics and the public-data `note`. Personal information, the website `href`, and the tagline remain editable.

For a local browser preview:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory ascii-profile
```

Then open [the local gallery](http://127.0.0.1:8765).

## Use a selected concept

The gallery has a README embed for each concept. After choosing a design, place that embed in the root `README.md` and keep the referenced `assets/` files in the repository. For example:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="ascii-profile/assets/01-cube-dark.svg">
  <img alt="Ranj's profile with an ASCII cube" src="ascii-profile/assets/01-cube-light.svg" width="100%">
</picture>
```

The `<picture>` selects a theme. The SVG's `viewBox` and `width="100%"` let the earlier card scale with the README. The root README uses the smaller centered animation above a separate, linked information card instead. `update_stats.py` and the GitHub Actions workflow provide the public statistics refresh.

## How the reference works

[Andrew6rant's README](https://github.com/Andrew6rant/Andrew6rant/blob/main/README.md) embeds a dark or light SVG through `<picture>`. The [SVG](https://github.com/Andrew6rant/Andrew6rant/blob/main/dark_mode.svg) places a portrait made from characters and an information panel on a fixed canvas. Monospaced text, preserved spaces, and explicit positions keep everything aligned.

The [Python updater](https://github.com/Andrew6rant/Andrew6rant/blob/main/today.py) reads GitHub data through GraphQL. It caches repository commit and line counts, updates SVG text elements by ID, and adjusts dot leaders to align the values. The [GitHub workflow](https://github.com/Andrew6rant/Andrew6rant/blob/main/.github/workflows/build.yaml) runs the updater and commits the generated files.

This prototype independently implements the same general text-in-SVG technique. It uses original geometry, layout, colors, and code. Each shape is a mathematical distance field sampled by an orthographic ray marcher. Surface normals determine character density and color. Python's standard library is sufficient; the generated images contain no scripts, external fonts, or remote image dependencies.

## Design decisions

One profile data file supplies the information cards, accessible README embed, and gallery. A small `Concept` record owns each shape's distance function, orientation, and colors. `Painter` owns only the geometry image. It has no access to personal information or statistics.

The vertical layout keeps the geometry and information from competing for horizontal space. `PROFILE_WIDTH` in `generate.py` supplies the shared display width. `PROFILE_INSET` keeps the animation caption at 32 pixels; the card uses a 40-pixel content inset to leave room for its character-drawn frame. The production card and its gallery example share `information_svg`, so statistics updates preserve the selected design. The card remains clickable, profile text appears once, and count-only updates leave the GIF files unchanged.
