#!/usr/bin/env bash
#
# build-fritzing-linux.sh — compile Fritzing (develop) depuis les sources sur Linux (x86_64)
# et produit un AppImage. Parallèle des scripts macOS/Windows.
#
# PREMIER JET piloté par la CI (non testable depuis macOS) : on débogue au run.
#
# Pré-requis (fournis par le job CI `linux`) :
#   - build-essential, libssl-dev, zlib1g-dev, libgl1-mesa-dev, bison, flex,
#     pkg-config, patchelf, libfuse2, file, curl  (apt)
#   - Qt 6.5.x (QtDir = QT_ROOT_DIR, gcc_64), modules qtserialport + qt5compat
#   - lancé depuis un dossier contenant `fritzing-app/` (+ `fritzing-parts/`)
#
# Sortie : ./Fritzing-x86_64.AppImage
#
set -euo pipefail

# --- Versions épinglées (cf. pri/*detect.pri, section unix:!macx) ---------------
LIBGIT2_VERSION="${LIBGIT2_VERSION:-1.7.1}"   # ../libgit2-1.7.1 (DYNAMIQUE sur Linux)
NGSPICE_VERSION="${NGSPICE_VERSION:-42}"      # ../ngspice-42 (shared)
CLIPPER_VERSION="${CLIPPER_VERSION:-6.4.2}"   # ../Clipper1/6.4.2
SVGPP_VERSION="${SVGPP_VERSION:-1.3.1}"       # ../svgpp-1.3.1
QUAZIP_VERSION="${QUAZIP_VERSION:-1.4}"       # ../quazip-<QtVer>-1.4intuisphere
BOOST_USCORE="${BOOST_USCORE:-1_85_0}"        # sœur boost_1_85_0

ROOT="$(pwd)"
FA="$ROOT/fritzing-app"
JOBS="$(nproc)"
[ -d "$FA" ] || { echo "ERREUR : $FA introuvable"; exit 1; }

if [ -n "${QT_DIR:-}" ]; then QMAKE="$QT_DIR/bin/qmake"; else
  QMAKE="$(command -v qmake || true)"; [ -n "$QMAKE" ] || { echo "qmake introuvable"; exit 1; }
  QT_DIR="$(cd "$(dirname "$QMAKE")/.." && pwd)"
fi
QT_VERSION="$("$QMAKE" -query QT_VERSION)"
echo ">> Qt $QT_VERSION ($QT_DIR) — Linux x86_64"

# Clipper 6.4.2 exige cmake_minimum_required 2.8, refusé par CMake >= 4 : on relâche.
CMAKE_COMMON=(-DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5)
fetch() { echo ">> télécharge $1"; curl -fL --retry 3 -o "$2" "$1"; }

run_with_timeout() { # secs cmd...
  local secs="$1"; shift; "$@" & local p=$!; local n=0
  while kill -0 "$p" 2>/dev/null; do sleep 5; n=$((n+5))
    [ "$n" -ge "$secs" ] && { echo ">> timeout ${secs}s -> kill"; kill -9 "$p" 2>/dev/null || true; return 124; }
  done; wait "$p"
}

# --- 1. libgit2 (DYNAMIQUE, OpenSSL) --------------------------------------------
if [ ! -f "$ROOT/libgit2-$LIBGIT2_VERSION/lib/libgit2.so" ]; then
  echo "== libgit2 $LIBGIT2_VERSION (shared) =="
  fetch "https://github.com/libgit2/libgit2/archive/refs/tags/v$LIBGIT2_VERSION.tar.gz" /tmp/libgit2.tgz
  rm -rf /tmp/libgit2-src && mkdir -p /tmp/libgit2-src
  tar xzf /tmp/libgit2.tgz -C /tmp/libgit2-src --strip-components=1
  cmake -S /tmp/libgit2-src -B /tmp/libgit2-src/build "${CMAKE_COMMON[@]}" \
    -DBUILD_SHARED_LIBS=ON -DBUILD_TESTS=OFF -DBUILD_CLI=OFF -DUSE_SSH=OFF \
    -DUSE_HTTPS=OpenSSL -DCMAKE_INSTALL_PREFIX="$ROOT/libgit2-$LIBGIT2_VERSION" \
    -DCMAKE_INSTALL_LIBDIR=lib
  cmake --build /tmp/libgit2-src/build --target install -j"$JOBS"
fi

# --- 2. ngspice (shared, dlopen au runtime) -------------------------------------
if [ ! -f "$ROOT/ngspice-$NGSPICE_VERSION/lib/libngspice.so" ]; then
  echo "== ngspice $NGSPICE_VERSION (shared) =="
  fetch "https://downloads.sourceforge.net/project/ngspice/ng-spice-rework/old-releases/$NGSPICE_VERSION/ngspice-$NGSPICE_VERSION.tar.gz" /tmp/ngspice.tgz
  rm -rf /tmp/ngspice-src && mkdir -p /tmp/ngspice-src
  tar xzf /tmp/ngspice.tgz -C /tmp/ngspice-src --strip-components=1
  ( cd /tmp/ngspice-src && mkdir -p release && cd release
    ../configure --with-ngshared --enable-xspice --enable-cider --disable-debug \
      --prefix="$ROOT/ngspice-$NGSPICE_VERSION"
    make -j"$JOBS" && make install )
fi

# --- 3. Clipper1 / polyclipping (../Clipper1/6.4.2) -----------------------------
if [ ! -f "$ROOT/Clipper1/$CLIPPER_VERSION/lib/libpolyclipping.so" ]; then
  echo "== Clipper1 $CLIPPER_VERSION =="
  fetch "https://downloads.sourceforge.net/project/polyclipping/clipper_ver$CLIPPER_VERSION.zip" /tmp/clipper.zip
  rm -rf /tmp/clipper-src && mkdir -p /tmp/clipper-src && unzip -q -o /tmp/clipper.zip -d /tmp/clipper-src
  cmake -S /tmp/clipper-src/cpp -B /tmp/clipper-src/cpp/build "${CMAKE_COMMON[@]}" \
    -DBUILD_SHARED_LIBS=ON -DCMAKE_INSTALL_PREFIX="$ROOT/Clipper1/$CLIPPER_VERSION" -DCMAKE_INSTALL_LIBDIR=lib
  cmake --build /tmp/clipper-src/cpp/build --target install -j"$JOBS"
fi

# --- 4. svgpp (header-only) -----------------------------------------------------
if [ ! -f "$ROOT/svgpp-$SVGPP_VERSION/include/svgpp/svgpp.hpp" ]; then
  echo "== svgpp $SVGPP_VERSION =="
  fetch "https://github.com/svgpp/svgpp/archive/refs/tags/v$SVGPP_VERSION.tar.gz" /tmp/svgpp.tgz
  rm -rf "$ROOT/svgpp-$SVGPP_VERSION" && mkdir -p "$ROOT/svgpp-$SVGPP_VERSION"
  tar xzf /tmp/svgpp.tgz -C "$ROOT/svgpp-$SVGPP_VERSION" --strip-components=1
fi

# --- 5. boost (headers, sœur boost_1_85_0) --------------------------------------
if [ ! -f "$ROOT/boost_$BOOST_USCORE/boost/version.hpp" ]; then
  echo "== boost $BOOST_USCORE (headers) =="
  bv="${BOOST_USCORE//_/.}"
  fetch "https://archives.boost.io/release/$bv/source/boost_$BOOST_USCORE.tar.gz" /tmp/boost.tgz
  tar xzf /tmp/boost.tgz -C "$ROOT"
fi

# --- 6. QuaZip (Qt6, zlib système) ----------------------------------------------
QUAZIP_DIR="$ROOT/quazip-$QT_VERSION-${QUAZIP_VERSION}intuisphere"
if [ ! -f "$QUAZIP_DIR/lib/libquazip1-qt6.so" ]; then
  echo "== QuaZip $QUAZIP_VERSION (Qt $QT_VERSION) =="
  fetch "https://github.com/stachenov/quazip/archive/refs/tags/v$QUAZIP_VERSION.tar.gz" /tmp/quazip.tgz
  rm -rf /tmp/quazip-src && mkdir -p /tmp/quazip-src
  tar xzf /tmp/quazip.tgz -C /tmp/quazip-src --strip-components=1
  cmake -S /tmp/quazip-src -B /tmp/quazip-src/build "${CMAKE_COMMON[@]}" \
    -DQUAZIP_QT_MAJOR_VERSION=6 -DBUILD_SHARED_LIBS=ON \
    -DCMAKE_PREFIX_PATH="$QT_DIR" -DCMAKE_INSTALL_PREFIX="$QUAZIP_DIR" -DCMAKE_INSTALL_LIBDIR=lib
  cmake --build /tmp/quazip-src/build --target install -j"$JOBS"
fi

# --- 7. Build (qmake + make, in-source) -----------------------------------------
echo "== build Fritzing =="
( cd "$FA"
  if command -v ccache >/dev/null 2>&1; then
    "$QMAKE" phoenix.pro CONFIG+=release boost_root="$ROOT/boost_$BOOST_USCORE" \
      "QMAKE_CXX=ccache g++" "QMAKE_CC=ccache gcc"
  else
    "$QMAKE" phoenix.pro CONFIG+=release boost_root="$ROOT/boost_$BOOST_USCORE"
  fi
  make -j"$JOBS" )
[ -x "$FA/Fritzing" ] || { echo "ERREUR : binaire non produit"; exit 1; }

# --- 8. AppDir (données incluses) -> parts.db -> linuxdeploy+qt -> AppImage ------
echo "== packaging =="
APPDIR="$ROOT/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib" \
         "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp "$FA/Fritzing" "$APPDIR/usr/bin/"
cp "$FA/org.fritzing.Fritzing.desktop" "$APPDIR/usr/share/applications/"
cp "$FA/resources/system_icons/linux/fz_icon256.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/fritzing.png"
cp -P "$ROOT/ngspice-$NGSPICE_VERSION/lib/"libngspice.so* "$APPDIR/usr/lib/" 2>/dev/null || true
# données : usr/ (FolderUtils y cherche translations+help, puis fritzing-parts)
cp -r "$FA/sketches" "$FA/help" "$FA/translations" "$APPDIR/usr/"
cp -r "$ROOT/fritzing-parts" "$APPDIR/usr/fritzing-parts"
rm -f "$APPDIR/usr/translations/"*.ts 2>/dev/null || true
find "$APPDIR/usr/translations" -name "*.qm" -size -128c -delete 2>/dev/null || true

# libs des deps + Qt accessibles (pour parts.db ET pour que linuxdeploy résolve les NEEDED)
export LD_LIBRARY_PATH="$QT_DIR/lib:$ROOT/libgit2-$LIBGIT2_VERSION/lib:$ROOT/Clipper1/$CLIPPER_VERSION/lib:$QUAZIP_DIR/lib:$ROOT/ngspice-$NGSPICE_VERSION/lib:${LD_LIBRARY_PATH:-}"
export PATH="$QT_DIR/bin:$PATH"   # qmake pour le plugin qt

# parts.db en headless (offscreen), via le Qt d'install.
# IMPORTANT : .git de fritzing-parts encore présent ici — la génération (`-db`, fullLoad)
# appelle PartsChecker::getSha() -> git_repository_open() ; sans .git le SHA est vide,
# loadReferenceModel() renvoie false et parts.db n'est jamais écrit (AppImage sans pièces).
QT_QPA_PLATFORM=offscreen QT_PLUGIN_PATH="$QT_DIR/plugins" run_with_timeout 600 \
  "$APPDIR/usr/bin/Fritzing" -db "$APPDIR/usr/fritzing-parts/parts.db" \
  -pp "$APPDIR/usr/fritzing-parts" -f "$APPDIR/usr/fritzing-parts" \
  || echo ">> parts.db : échec/timeout"
# Garde-fou : ne jamais packager un AppImage sans base de pièces.
[ -s "$APPDIR/usr/fritzing-parts/parts.db" ] || { echo "ERREUR : parts.db non généré"; exit 1; }
echo ">> parts.db : $(du -h "$APPDIR/usr/fritzing-parts/parts.db" | cut -f1)"
# .git/.github retirés APRÈS génération (inutiles au runtime, alourdissent l'AppImage)
rm -rf "$APPDIR/usr/fritzing-parts/.git" "$APPDIR/usr/fritzing-parts/.github"

# linuxdeploy + plugin qt : bundle Qt + libgit2/quazip/clipper/ngspice -> AppImage.
# (icône passée explicitement -> pas de scan hasardeux de fritzing-parts)
for t in linuxdeploy-x86_64.AppImage linuxdeploy-plugin-qt-x86_64.AppImage; do
  [ -x "$ROOT/$t" ] || { fetch "https://github.com/linuxdeploy/${t%%-x86_64*}/releases/download/continuous/$t" "$ROOT/$t"; chmod +x "$ROOT/$t"; }
done
export QMAKE
export EXTRA_PLATFORM_PLUGINS="libqoffscreen.so"   # en plus de xcb (gui)
"$ROOT/linuxdeploy-x86_64.AppImage" --appimage-extract-and-run \
  --appdir "$APPDIR" \
  -e "$APPDIR/usr/bin/Fritzing" \
  -d "$APPDIR/usr/share/applications/org.fritzing.Fritzing.desktop" \
  -i "$APPDIR/usr/share/icons/hicolor/256x256/apps/fritzing.png" \
  --library "$ROOT/ngspice-$NGSPICE_VERSION/lib/libngspice.so" \
  --plugin qt --output appimage
mv -f Fritzing*.AppImage "$ROOT/Fritzing-x86_64.AppImage" 2>/dev/null \
  || mv -f ./*.AppImage "$ROOT/Fritzing-x86_64.AppImage"
echo ">> AppImage : $ROOT/Fritzing-x86_64.AppImage"
echo ">> terminé."
