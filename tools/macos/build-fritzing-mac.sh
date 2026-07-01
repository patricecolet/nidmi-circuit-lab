#!/usr/bin/env bash
#
# build-fritzing-mac.sh — compile Fritzing (develop) depuis les sources sur macOS.
#
# Recette validée le 2026-06-28 sur Apple Silicon (Qt 6.5.3). Utilisable en CI
# et en local pour déboguer (cf. docs/BUILD.md).
#
# Pré-requis :
#   - Xcode CLT, Homebrew, cmake, bison/flex (système OK), curl, unzip
#   - Qt 6.5.x (qmake dans le PATH, ou QT_DIR pointant sur .../<ver>/macos)
#   - Lancé depuis un dossier contenant `fritzing-app/` (sources upstream déjà clonées).
#     Les dépendances sœurs sont construites À CÔTÉ de fritzing-app (qmake les y cherche).
#
# Sortie : ./release64/Fritzing.app  (+ Fritzing-<arch>.dmg si PACKAGE=1)
#
set -euo pipefail

# --- Versions épinglées (cf. pri/*detect.pri de fritzing-app) -------------------
LIBGIT2_VERSION="${LIBGIT2_VERSION:-1.7.1}"   # libgit2detect.pri : macOS = 1.7.1 static
NGSPICE_VERSION="${NGSPICE_VERSION:-42}"      # spicedetect.pri   : ../ngspice-42
CLIPPER_VERSION="${CLIPPER_VERSION:-6.4.2}"   # clipper1detect.pri: Clipper1/6.4.2
SVGPP_VERSION="${SVGPP_VERSION:-1.3.1}"       # svgppdetect.pri   : svgpp-1.3.1
QUAZIP_VERSION="${QUAZIP_VERSION:-1.4}"       # quazipdetect.pri  : quazip-<QtVer>-1.4intuisphere
DEPLOY_TARGET="${MACOSX_DEPLOYMENT_TARGET:-11.0}"   # aligné sur le min de Qt 6.5

# --- Environnement --------------------------------------------------------------
ARCH="${ARCH:-$(uname -m)}"                   # arm64 | x86_64
ROOT="$(pwd)"
FA="$ROOT/fritzing-app"
JOBS="$(sysctl -n hw.ncpu)"
export MACOSX_DEPLOYMENT_TARGET="$DEPLOY_TARGET"

[ -d "$FA" ] || { echo "ERREUR : $FA introuvable (cloner fritzing-app d'abord)"; exit 1; }

# qmake : QT_DIR explicite, sinon déduit du qmake dans le PATH
if [ -n "${QT_DIR:-}" ]; then
  QMAKE="$QT_DIR/bin/qmake"
else
  QMAKE="$(command -v qmake || true)"
  [ -n "$QMAKE" ] || { echo "ERREUR : qmake introuvable (PATH ou QT_DIR)"; exit 1; }
  QT_DIR="$(cd "$(dirname "$QMAKE")/.." && pwd)"
fi
QT_VERSION="$("$QMAKE" -query QT_VERSION)"
echo ">> Qt $QT_VERSION ($QT_DIR) — arch $ARCH — deploy target $DEPLOY_TARGET"

CMAKE_COMMON=(-DCMAKE_BUILD_TYPE=Release
  -DCMAKE_OSX_ARCHITECTURES="$ARCH"
  -DCMAKE_OSX_DEPLOYMENT_TARGET="$DEPLOY_TARGET"
  # Clipper 6.4.2 exige cmake_minimum_required 2.8, refusé par CMake >= 4 : on relâche.
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5)

fetch() { # url dest
  echo ">> télécharge $1"; curl -fL --retry 3 -o "$2" "$1"
}

# timeout portable (le runner macOS n'a pas timeout/gtimeout)
run_with_timeout() { # secs cmd...
  local secs="$1"; shift
  "$@" & local p=$!
  local n=0
  while kill -0 "$p" 2>/dev/null; do
    sleep 5; n=$((n+5))
    if [ "$n" -ge "$secs" ]; then echo ">> timeout ${secs}s -> kill $p"; kill -9 "$p" 2>/dev/null || true; return 124; fi
  done
  wait "$p"
}

# --- 1. libgit2 (statique) ------------------------------------------------------
if [ ! -f "$ROOT/libgit2-$LIBGIT2_VERSION/lib/libgit2.a" ]; then
  echo "== libgit2 $LIBGIT2_VERSION (static) =="
  fetch "https://github.com/libgit2/libgit2/archive/refs/tags/v$LIBGIT2_VERSION.tar.gz" /tmp/libgit2.tgz
  rm -rf /tmp/libgit2-src && mkdir -p /tmp/libgit2-src
  tar xzf /tmp/libgit2.tgz -C /tmp/libgit2-src --strip-components=1
  cmake -S /tmp/libgit2-src -B /tmp/libgit2-src/build "${CMAKE_COMMON[@]}" \
    -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTS=OFF -DBUILD_CLI=OFF -DUSE_SSH=OFF \
    -DREGEX_BACKEND=builtin -DCMAKE_INSTALL_PREFIX="$ROOT/libgit2-$LIBGIT2_VERSION"
  cmake --build /tmp/libgit2-src/build --target install -j"$JOBS"
fi

# --- 2. ngspice (shared, dlopen au runtime) -------------------------------------
if [ ! -f "$ROOT/ngspice-$NGSPICE_VERSION/lib/libngspice.0.dylib" ]; then
  echo "== ngspice $NGSPICE_VERSION (shared) =="
  fetch "https://downloads.sourceforge.net/project/ngspice/ng-spice-rework/old-releases/$NGSPICE_VERSION/ngspice-$NGSPICE_VERSION.tar.gz" /tmp/ngspice.tgz
  rm -rf /tmp/ngspice-src && mkdir -p /tmp/ngspice-src
  tar xzf /tmp/ngspice.tgz -C /tmp/ngspice-src --strip-components=1
  ( cd /tmp/ngspice-src && mkdir -p release && cd release
    ../configure --with-ngshared --enable-xspice --enable-cider --disable-debug \
      --prefix="$ROOT/ngspice-$NGSPICE_VERSION" \
      CFLAGS="-arch $ARCH -O2 -mmacosx-version-min=$DEPLOY_TARGET" \
      LDFLAGS="-arch $ARCH -mmacosx-version-min=$DEPLOY_TARGET"
    make -j"$JOBS" && make install )
fi

# --- 3. Clipper1 / polyclipping (shared, install-name @rpath) -------------------
if [ ! -f "$ROOT/Clipper1/$CLIPPER_VERSION/lib/libpolyclipping.dylib" ]; then
  echo "== Clipper1 $CLIPPER_VERSION =="
  fetch "https://downloads.sourceforge.net/project/polyclipping/clipper_ver$CLIPPER_VERSION.zip" /tmp/clipper.zip
  rm -rf /tmp/clipper-src && mkdir -p /tmp/clipper-src
  unzip -q -o /tmp/clipper.zip -d /tmp/clipper-src
  cmake -S /tmp/clipper-src/cpp -B /tmp/clipper-src/cpp/build "${CMAKE_COMMON[@]}" \
    -DBUILD_SHARED_LIBS=ON -DCMAKE_INSTALL_NAME_DIR=@rpath \
    -DCMAKE_INSTALL_PREFIX="$ROOT/Clipper1/$CLIPPER_VERSION"
  cmake --build /tmp/clipper-src/cpp/build --target install -j"$JOBS"
fi

# --- 4. svgpp (header-only) -----------------------------------------------------
if [ ! -f "$ROOT/svgpp-$SVGPP_VERSION/include/svgpp/svgpp.hpp" ]; then
  echo "== svgpp $SVGPP_VERSION (headers) =="
  fetch "https://github.com/svgpp/svgpp/archive/refs/tags/v$SVGPP_VERSION.tar.gz" /tmp/svgpp.tgz
  rm -rf "$ROOT/svgpp-$SVGPP_VERSION" && mkdir -p "$ROOT/svgpp-$SVGPP_VERSION"
  tar xzf /tmp/svgpp.tgz -C "$ROOT/svgpp-$SVGPP_VERSION" --strip-components=1
fi

# --- 5. QuaZip (Qt6, chemin spécifique à la version Qt) -------------------------
QUAZIP_DIR="$ROOT/quazip-$QT_VERSION-${QUAZIP_VERSION}intuisphere"
if [ ! -f "$QUAZIP_DIR/lib/libquazip1-qt6.dylib" ]; then
  echo "== QuaZip $QUAZIP_VERSION (Qt $QT_VERSION) =="
  fetch "https://github.com/stachenov/quazip/archive/refs/tags/v$QUAZIP_VERSION.tar.gz" /tmp/quazip.tgz
  rm -rf /tmp/quazip-src && mkdir -p /tmp/quazip-src
  tar xzf /tmp/quazip.tgz -C /tmp/quazip-src --strip-components=1
  cmake -S /tmp/quazip-src -B /tmp/quazip-src/build "${CMAKE_COMMON[@]}" \
    -DQUAZIP_QT_MAJOR_VERSION=6 -DBUILD_SHARED_LIBS=ON \
    -DCMAKE_PREFIX_PATH="$QT_DIR" -DCMAKE_INSTALL_PREFIX="$QUAZIP_DIR"
  cmake --build /tmp/quazip-src/build --target install -j"$JOBS"
fi

# --- 6. Patch phoenix.pro : architecture macOS codée en dur ---------------------
# Le .pro force `CONFIG += x86_64` ; on le remplace par l'arch cible (natif arm64).
if grep -q '^    CONFIG += x86_64 # x86 ppc' "$FA/phoenix.pro"; then
  sed -i.bak "s/^    CONFIG += x86_64 # x86 ppc/    CONFIG += $ARCH # patché par build-fritzing-mac.sh/" "$FA/phoenix.pro"
fi

# --- 7. Build (qmake + make) ----------------------------------------------------
echo "== build Fritzing =="
BOOST_ROOT_INC="$(brew --prefix)/include"
# ccache si dispo (source figée => recompilations quasi instantanées en CI)
( cd "$FA"
  if command -v ccache >/dev/null 2>&1; then
    echo ">> ccache activé"
    "$QMAKE" phoenix.pro CONFIG+=release boost_root="$BOOST_ROOT_INC" \
      "QMAKE_CXX=ccache clang++" "QMAKE_CC=ccache clang"
  else
    "$QMAKE" phoenix.pro CONFIG+=release boost_root="$BOOST_ROOT_INC"
  fi
  make -j"$JOBS" release )

APP="$ROOT/release64/Fritzing.app"
[ -x "$APP/Contents/MacOS/Fritzing" ] || { echo "ERREUR : binaire non produit"; exit 1; }
echo ">> binaire : $(lipo -info "$APP/Contents/MacOS/Fritzing")"

# --- 8. Packaging ---------------------------------------------------------------
if [ "${PACKAGE:-1}" = "1" ]; then
  echo "== packaging (macdeployqt + ressources + signature) =="
  "$QT_DIR/bin/macdeployqt" "$APP" -verbose=1 || true

  # plugin QPA offscreen : permet de générer parts.db sans écran (runner CI headless)
  mkdir -p "$APP/Contents/PlugIns/platforms"
  cp "$QT_DIR/plugins/platforms/libqoffscreen.dylib" "$APP/Contents/PlugIns/platforms/" 2>/dev/null || true

  FW="$APP/Contents/Frameworks"
  # QtCore5Compat : macdeployqt ne sait pas le résoudre via le rpath de QuaZip.
  if [ ! -d "$FW/QtCore5Compat.framework" ]; then
    cp -R "$QT_DIR/lib/QtCore5Compat.framework" "$FW/"
    rm -rf "$FW/QtCore5Compat.framework/Headers" "$FW/QtCore5Compat.framework/Versions/A/Headers"
  fi
  # libngspice : chargé par dlopen depuis QCoreApplication::libraryPaths() => PlugIns/
  mkdir -p "$APP/Contents/PlugIns"
  cp "$ROOT/ngspice-$NGSPICE_VERSION/lib/libngspice.0.dylib" "$APP/Contents/PlugIns/"

  # Traductions : compiler les .ts -> .qm (sinon translations/ vide -> UI toujours en anglais).
  # lrelease est fourni par Qt. On compile toutes les langues ; au runtime Fritzing charge
  # fritzing_<locale>.qm selon QLocale::system() (donc français auto sur un macOS en français).
  echo "== traductions (lrelease) =="
  "$QT_DIR/bin/lrelease" "$FA"/translations/*.ts >/dev/null 2>&1 || echo ">> lrelease : avertissements (langues incomplètes)"
  [ -s "$FA/translations/fritzing_fr.qm" ] || { echo "ERREUR : fritzing_fr.qm non généré"; exit 1; }

  # Ressources runtime (le dossier data est résolu dans Contents/MacOS sur macOS)
  SUP="$APP/Contents/MacOS"
  cp -Rf "$FA/sketches" "$FA/help" "$FA/translations" \
         "$FA/INSTALL.txt" "$FA/README.md" "$FA"/LICENSE.* "$SUP/" 2>/dev/null || true
  rm -f "$SUP/translations/"*.ts 2>/dev/null || true
  find "$SUP/translations" -name "*.qm" -size -128c -delete 2>/dev/null || true

  # Pièces + base de données (clonées par l'appelant dans $ROOT/fritzing-parts)
  if [ -d "$ROOT/fritzing-parts" ]; then
    cp -Rf "$ROOT/fritzing-parts" "$SUP/"
    # IMPORTANT : générer parts.db AVANT de supprimer .git. La génération (`-db`,
    # fullLoad) appelle PartsChecker::getSha() -> git_repository_open() sur le dossier :
    # sans .git, le SHA est vide, loadReferenceModel() renvoie false et parts.db n'est
    # JAMAIS écrit (app publiée sans pièces -> « Unable to find parts git repository »).
    # offscreen + timeout : sans écran Fritzing -db pouvait hang indéfiniment (kill à 6 h en CI)
    QT_QPA_PLATFORM=offscreen run_with_timeout 600 "$SUP/Fritzing" -db "$SUP/fritzing-parts/parts.db" \
      -pp "$SUP/fritzing-parts" -f "$SUP/fritzing-parts" || echo ">> parts.db : échec/timeout"
    # Garde-fou : ne jamais packager/publier un bundle sans base de pièces.
    [ -s "$SUP/fritzing-parts/parts.db" ] || { echo "ERREUR : parts.db non généré (pièces manquantes)"; exit 1; }
    echo ">> parts.db : $(du -h "$SUP/fritzing-parts/parts.db" | cut -f1)"
    # .git/.github retirés APRÈS (codesign --deep s'étrangle dessus, et ils sont inutiles au runtime)
    rm -rf "$SUP/fritzing-parts/.git" "$SUP/fritzing-parts/.github"
  else
    echo "ERREUR : $ROOT/fritzing-parts absent — pièces non embarquées"; exit 1
  fi

  # Signature ad-hoc (obligatoire : un binaire arm64 non signé ne se lance pas).
  # Pas de notarisation (pas de compte Apple Developer) => Gatekeeper au 1er lancement.
  codesign --force --deep --sign - "$APP"
  codesign --verify --deep --strict "$APP" && echo ">> signature ad-hoc OK"

  # DMG compressé
  DMG="$ROOT/Fritzing-$ARCH.dmg"
  rm -f "$DMG"
  hdiutil create -volname "Fritzing" -srcfolder "$APP" -ov -format UDZO "$DMG"
  echo ">> DMG : $DMG"
fi

echo ">> terminé."
