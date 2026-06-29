# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This repo contains **no application source code**. It is a CI orchestrator: a GitHub Actions
workflow that compiles **upstream Fritzing from source** and publishes free, cross-platform
binaries (macOS Apple Silicon/Intel, Windows, Linux) for educational use, so students can use
Fritzing without paying for the official prebuilt binary.

The entire substance of the project is **one file**: [`.github/workflows/build.yml`](.github/workflows/build.yml).
`docs/BUILD.md` mirrors that workflow as manual local steps for debugging. Everything else is README/license.

The Fritzing sources (`fritzing/fritzing-app`, `fritzing/fritzing-parts`) are **never committed**
here — the CI clones them at build time (see `.gitignore`). Do not add them to the repo.

## How the build works

`build.yml` has a **real, validated `macos` job** (matrix: `macos-14` arm64, `macos-13` x86_64)
and a **`build-others` scaffold** (linux + windows, still TODO). The macOS job clones `fritzing-app`
(pinned `FRITZING_REF`) and `fritzing-parts` (`PARTS_REF`) as sibling dirs, installs Qt 6.5.3, then
runs [`tools/macos/build-fritzing-mac.sh`](tools/macos/build-fritzing-mac.sh) which does everything:
builds the sibling deps, patches `phoenix.pro`, `qmake`/`make`, packages a signed `.app` + `.dmg`.
A `release` job (depends on `macos` only) publishes a **draft** GitHub Release on a `vX.Y.Z` tag.

Version pins live in the `env:` block at the top of `build.yml`. `FRITZING_REF` is a **`develop`
commit** (Qt6 + ngspice simulator), not the old `CD-625` tag (Qt5, 2020). `QT_VERSION` must stay
**6.5.3** — `phoenix.pro` caps at 6.5.10 and Qt 6.10 breaks compilation.

The whole macOS recipe — exact dep versions, why not Homebrew, the required patches, and the
packaging quirks (QtCore5Compat, dlopen'd libngspice, mandatory ad-hoc signing) — is documented in
`tools/macos/build-fritzing-mac.sh` (heavily commented) and [`docs/BUILD.md`](docs/BUILD.md). Read
those before touching the build; the sibling deps are non-obvious (static libgit2 1.7.1, ngspice-42
shared, Clipper1 6.4.2, svgpp 1.3.1, QuaZip 1.4 at a Qt-version-encoded path).

## Working on this repo

- **There is no local build/test/lint of this repo's own code** — the only "build" is the CI
  compiling Fritzing. Validate changes by pushing and watching the Actions run, or by reproducing
  a single OS job locally per `docs/BUILD.md` (macOS steps are fully spelled out there).
- **macOS is done and validated** (builds, launches, populated Parts bin, produces a signed `.dmg`).
  Debug it locally with `tools/macos/build-fritzing-mac.sh` (run from a dir containing `fritzing-app/`).
- **Linux + Windows are still scaffolds** (`build-others` job just echoes a TODO). Porting them means
  replaying the macOS recipe per-OS: same sibling deps (libgit2 dynamic on Linux, etc.), Qt 6.5.3,
  `qmake phoenix.pro`, then `linuxdeployqt` / `windeployqt`. Use `tools/macos/` as the pattern.
- The Fritzing build is version-sensitive; consult the "Points sensibles connus" section of
  `docs/BUILD.md` when something breaks.

## Project-specific constraints

- **macOS/Windows binaries are unsigned** (no paid Apple Developer / code-signing certs). This is
  intentional. When touching packaging or the README, keep the Gatekeeper/SmartScreen unblocking
  instructions accurate — they are how students actually launch the app.
- **License & branding:** Fritzing is GPLv3, fritzing-parts is CC-BY-SA. Any redistributed binary
  must keep GPLv3 and link back to upstream sources. "Fritzing" is a trademark and this repo is
  unaffiliated — a Phase-3 rebranding is planned to remove trademark ambiguity. Preserve
  attribution and the "unofficial educational build" framing.

## Roadmap context

Currently **Phase 1**: compile upstream as-is for all 3 OSes → Releases. Phase 2: preload the
project's own parts library (virtualGround, whiteNoise, ADG2188…). Phase 3: light rebrand
(name/icon). Documentation and primary audience are **French-speaking** (students); match that
language when editing README/docs.
