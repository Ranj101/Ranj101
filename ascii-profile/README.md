# ASCII profile studies

Eight original geometric profile concepts, rendered as ASCII text inside SVGs and a looping animation. The root profile README embeds the animation with theme-aware still fallbacks. The gallery remains available for local review.

## Review the concepts

Open `index.html` in a browser. The gallery works from disk with no server or dependencies. Use the concept buttons to inspect a card, switch between light and dark, and check its width. The mobile control scales the complete card to 390 pixels; it does not rearrange text inside the image.

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

To refresh the counts and all displayed images locally, use Python 3.12 with the renderer dependency installed:

```sh
python3 ascii-profile/update_stats.py
python3 ascii-profile/animate.py
python3 ascii-profile/generate.py
python3 -m unittest discover -s ascii-profile -p 'test_*.py'
```

Run `python3 ascii-profile/update_stats.py --check` to compare saved values against GitHub without writing files. It exits with status 1 when the values need updating. Network or validation failures leave the saved profile unchanged. A refresh with unchanged values does not rewrite the file.

### Automatic refresh

The workflow in [update-profile-stats.yml](../.github/workflows/update-profile-stats.yml) runs on `main`:

- Daily at 05:17 UTC, which is 08:17 in Erbil.
- After pushes that change the profile configuration, renderer, updater, gallery template, dependency file, or workflow.
- When you select **Actions → Update public profile statistics → Run workflow**.

After fetching the statistics, the workflow regenerates both GIFs, their still fallbacks, the static SVGs, and the gallery. Scheduled runs skip rendering when the counts are unchanged. Pushes and manual runs also rebuild the images so changes to the profile or renderer are included. The workflow runs the tests before committing only the changed profile data and generated assets. It never force-pushes. A concurrent push can cause its final push to fail safely; rerun the workflow against the latest `main`.

No personal access token or custom secret is required. Public data is fetched anonymously. The workflow uses its repository-scoped `GITHUB_TOKEN` only for checkout and the generated-file commit. Its job requests `contents: write`; repository rules must allow that bot commit to `main`. It uses a macOS runner for the same Menlo font as the reviewed preview and pins Pillow to the tested version. No font file is redistributed.

The workflow becomes available after these files are pushed to `main`. The local updater can run before then. GitHub can delay scheduled runs, and public repositories can have schedules disabled after 60 days without activity. Use the manual run when needed. See [GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Animated version

Choose **Animation** in the gallery, then **Play animation**. The preview starts still; **Stop animation** returns to its poster. Theme switching works for both the GIF and the poster. Reduced-motion preferences stop playback, and the README embed selects a still image when reduced motion is requested.

The loop lasts 72 seconds at a 20 fps render cadence. Each shape moves for 7 seconds and reconstructs over the next 2 seconds. Cube, crystal, column, and lattice rotate around Y; the torus and chain around X; and the orbital sphere around Z. The crystal and column turn in the opposite direction. The previous slow rotation speeds are preserved: each shape travels approximately 34–49 degrees during its phase, depending on the shape.

Terrain is a separate wave motion, not a rotation. Its viewpoint stays fixed above the surface while two sine waves change the height of a solid tile. It completes two wave cycles in its seven-second phase. `Rotation` and `Wave` have separate records in the keyed `MOTIONS` registry, so terrain does not have a rotation axis or angular travel.

The generator reuses the distance fields in `generate.py`, rotates or deforms the geometry, and samples fresh ASCII characters for each frame. The globe has a filled, shaded surface with less crowded coordinate lines. The terrain uses dense surface shading, darker solid sides, and smaller ripples. Its width and depth are about 25% smaller than the earlier sheet, and its maximum wave amplitude is about 56% lower. `TERRAIN_HALF_EXTENT`, `TERRAIN_BASE`, and `TERRAIN_AMPLITUDES` in `generate.py` control its footprint, depth, and wave height. The gyroid has thicker walls, depth shading, and a cubic guide frame to make the curved channels easier to follow.

During transitions, characters become particles: they leave their grid cells, follow curved paths through a loose swirl, and settle into the next shape. The accent color blends at the same time. The information panel never moves or changes color. The last transition reconstructs the first cube orientation to close the loop.

`animate.py` renders those frames with Pillow and encodes two GIFs with a shared palette per theme, no dithering, and optimized delta frames. [Pillow's GIF writer](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#gif) stores the frame durations and infinite-loop setting. It may merge identical neighboring frames while retaining their combined duration. The exports are 1120 × 600; exact sizes and encoded frame counts are in `assets/motion.json`. Intermediate frames are compressed in memory to avoid retaining the full uncompressed sequence.

To regenerate, install the animation dependency in your Python environment and run:

```sh
python3 -m pip install -r ascii-profile/requirements-animation.txt
python3 ascii-profile/animate.py
python3 ascii-profile/generate.py
python3 -m unittest discover -s ascii-profile -p 'test_*.py'
```

The SVG generator still needs only the standard library. The animation uses a locally installed monospace font: Menlo on macOS, DejaVu Sans Mono or Liberation Mono on Linux, or Consolas on Windows. Pass `--font /path/to/font.ttf` to select one explicitly. No font file is redistributed.

The timing controls are `--hold`, `--transition`, and `--fps` (10, 20, or 25). For example, `python3 ascii-profile/animate.py --hold 9 --transition 2 --fps 20` makes an 88-second loop with the eight current shapes. Edit the keyed `MOTIONS` entries to adjust rotation axes and angular travel or the terrain's wave cycles. Regenerate the gallery after every export to refresh its size, duration, and embed information.

The animation assets are:

- `assets/motion-dark.gif` and `assets/motion-light.gif`: looping README images.
- `assets/motion-dark-poster.png` and `assets/motion-light-poster.png`: still fallbacks.
- `assets/motion-embed.html`: theme-aware embed with reduced-motion fallbacks.
- `assets/motion-contact-sheet.jpg`: one motion and one transition still for each shape.

The gallery can stop the animation by switching to its poster. A standalone GIF cannot offer its own playback controls, so the README embed also provides reduced-motion stills. The embed has not been published or tested on a live GitHub README. Personal information inside the exported image is not selectable, and a full-width desktop card remains small on mobile; important links and biographical text should also appear as ordinary Markdown when a design is adopted.

## Edit and regenerate

Edit `profile.json`, then run this command from the repository root with Python 3.9 or later:

```sh
python3 ascii-profile/generate.py
```

The generator writes two SVG themes, a plain ASCII file, and a README embed for each concept in `assets/`. It also rebuilds `index.html` from `gallery.template.html`. Edit the template, not the generated gallery.

The card has five information fields and three metrics. Both arrays are in `profile.json`. Long values shrink to fit their column. The statistics updater owns the three metrics and the public-data `note`, which supplies the footer and the embed's alternative text. Personal information and the tagline remain editable.

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

The `<picture>` selects a theme. The SVG's `viewBox` and `width="100%"` let the card scale with the README. The root README currently uses the animation. The renderers read local profile data; `update_stats.py` and the GitHub Actions workflow provide the public statistics refresh.

## How the reference works

[Andrew6rant's README](https://github.com/Andrew6rant/Andrew6rant/blob/main/README.md) embeds a dark or light SVG through `<picture>`. The [SVG](https://github.com/Andrew6rant/Andrew6rant/blob/main/dark_mode.svg) places a portrait made from characters and an information panel on a fixed canvas. Monospaced text, preserved spaces, and explicit positions keep everything aligned.

The [Python updater](https://github.com/Andrew6rant/Andrew6rant/blob/main/today.py) reads GitHub data through GraphQL. It caches repository commit and line counts, updates SVG text elements by ID, and adjusts dot leaders to align the values. The [GitHub workflow](https://github.com/Andrew6rant/Andrew6rant/blob/main/.github/workflows/build.yaml) runs the updater and commits the generated files.

This prototype independently implements the same general text-in-SVG technique. It uses original geometry, layout, colors, and code. Each shape is a mathematical distance field sampled by an orthographic ray marcher. Surface normals determine character density and color. Python's standard library is sufficient; the generated images contain no scripts, external fonts, or remote image dependencies.

## Design decisions

The public command reads one profile data file and produces every concept in both themes. A small `Concept` record owns each shape's distance function, orientation, and colors. Layout and personal information are shared across all options so the comparison is about the artwork.

Two approaches were considered: editing separate hand-drawn SVG templates, or generating every card from shared data and mathematical geometry. The generator keeps both sets of themed outputs consistent and makes new shapes reproducible. Separate templates would make individual layout changes quicker, but require repeating every information edit.

The Build the Lever principle led to rerunnable generators and a public-statistics updater. Model the Domain led to a concept registry and one profile configuration. Prove It Works means checking the fetched counts against the emitted images, including both themes and narrow widths. Idempotent updates avoid rewriting unchanged data or adding daily commits without changed statistics.
