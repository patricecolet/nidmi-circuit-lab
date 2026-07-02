# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This repo contains **no application source code**. It is a CI orchestrator: a GitHub Actions
workflow that compiles **upstream Fritzing from source** and publishes free, cross-platform
binaries (macOS Apple Silicon/Intel, Windows, Linux) for educational use, so students can use
Fritzing without paying for the official prebuilt binary.

The substance of the project is **`.github/workflows/build.yml`** plus the three per-OS build
scripts it drives (`tools/{macos,windows,linux}/`). `docs/BUILD.md` mirrors the macOS flow as
manual local steps for debugging. Everything else is README/license.

The Fritzing sources (`fritzing/fritzing-app`, `fritzing/fritzing-parts`) and all sibling
dependencies are **never committed** here — the CI clones/builds them at build time (see
`.gitignore`; they may exist as untracked dirs in a local checkout). Do not add them to the repo.

## How the build works

`build.yml` runs five jobs, each cloning `fritzing-app` (pinned `FRITZING_REF`) and `fritzing-parts`
(`PARTS_REF`) as sibling dirs, installing Qt 6.5.3, then running a per-OS script that builds the
sibling deps, patches `phoenix.pro`, `qmake`/`make`(/`nmake`), and packages the result:

| Job | Runner | Script | Output | Status |
|---|---|---|---|---|
| `macos-arm64` | macos-14 | `tools/macos/build-fritzing-mac.sh` | `Fritzing-arm64.dmg` | **validated, blocking** (release waits on it) |
| `macos-intel` | macos-13 | same (`ARCH=x86_64`) | `Fritzing-x86_64.dmg` | best-effort, `continue-on-error`, non-blocking |
| `windows` | windows-2022 | `tools/windows/build-fritzing-win.ps1` | `Fritzing-win-x64.zip` | **real, blocking**, still stabilizing |
| `linux` | ubuntu-22.04 | `tools/linux/build-fritzing-linux.sh` | `Fritzing-x86_64.AppImage` | best-effort AppImage, `continue-on-error`, non-blocking |
| `release` | ubuntu-22.04 | — | draft GitHub Release | on a `vX.Y.Z` tag; `needs: [macos-arm64, windows]` |

Best-effort jobs (`macos-intel`, `linux`) are outside the release `needs` and never block it;
their artifacts are attached to the release only if ready in time.

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
- **Windows and Linux now have real build scripts** but are debugged over CI runs (not testable from
  macOS). Each replays the macOS recipe with per-OS deps: sibling dep paths/linkage differ (e.g.
  libgit2 is **static** on macOS but **dynamic** on Linux/Windows; Windows uses `Clipper1-6.4.2` with a
  dash and a precompiled ngspice DLL; both add a sibling `boost_1_85_0`). The exact pins live in the
  headers of each `tools/<os>/build-*.{sh,ps1}` — read them before editing. Packaging: macOS
  `.dmg` (ad-hoc signed), Windows `.zip` (unsigned), Linux `.AppImage` (linuxdeploy + qt plugin).
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
