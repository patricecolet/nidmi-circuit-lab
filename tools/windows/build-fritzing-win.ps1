# build-fritzing-win.ps1 — compile Fritzing (develop) depuis les sources sur Windows (MSVC x64).
#
# Parallèle de tools/macos/build-fritzing-mac.sh. PREMIER JET piloté par la CI :
# Windows n'est pas testable depuis macOS, on débogue au run GitHub Actions.
#
# Pré-requis (fournis par le job CI `windows`) :
#   - environnement MSVC actif (ilammy/msvc-dev-cmd) => cl.exe / nmake.exe dans le PATH
#   - Qt 6.5.x (QtDir = .../6.5.3/msvc2019_64), cmake, 7-Zip, git
#   - lancé depuis un dossier contenant `fritzing-app/` (+ `fritzing-parts/` pour parts.db)
#
# Sortie : .\release64\Fritzing.exe  +  Fritzing-win-x64.zip
#
param(
  [string]$Arch  = "x64",
  [string]$QtDir = $env:QT_ROOT_DIR
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# --- Versions épinglées (cf. pri/*detect.pri, section win32) --------------------
$LIBGIT2_VERSION = "1.7.1"   # libgit2detect.pri : ../libgit2 (dynamique sur Windows)
$NGSPICE_VERSION = "42"      # spicedetect.pri   : ../ngspice-42 (DLL précompilée)
$CLIPPER_VERSION = "6.4.2"   # clipper1detect.pri: ../../Clipper1-6.4.2 (tiret !)
$SVGPP_VERSION   = "1.3.1"   # svgppdetect.pri   : ../svgpp-1.3.1
$QUAZIP_VERSION  = "1.4"     # quazipdetect.pri  : ../quazip-<QtVer>-1.4intuisphere
$BOOST_USCORE    = "1_85_0"  # boostdetect.pri (develop) : sœur boost_1_85_0

$ROOT  = (Get-Location).Path
$FA    = Join-Path $ROOT "fritzing-app"
if (-not (Test-Path $FA)) { throw "fritzing-app introuvable dans $ROOT" }
if (-not $QtDir) { throw "QtDir / QT_ROOT_DIR non défini" }
$QMAKE = Join-Path $QtDir "bin\qmake.exe"
$QtVer = (& $QMAKE -query QT_VERSION).Trim()
$SevenZip = "$env:ProgramFiles\7-Zip\7z.exe"
# Clipper 6.4.2 exige cmake_minimum_required 2.8, refusé par CMake >= 4 : on relâche.
$PolicyMin = "-DCMAKE_POLICY_VERSION_MINIMUM=3.5"
Write-Host ">> Qt $QtVer ($QtDir) — arch $Arch"

function Get-File($url, $dest) { Write-Host ">> télécharge $url"; Invoke-WebRequest -Uri $url -OutFile $dest }

# --- 1. libgit2 (dynamique : git2.lib + git2.dll) -------------------------------
# detect win32 attend ../libgit2/include/git2.h + ../libgit2/build64/Release/git2.lib
if (-not (Test-Path "$ROOT\libgit2\build64\Release\git2.lib")) {
  Write-Host "== libgit2 $LIBGIT2_VERSION =="
  Get-File "https://github.com/libgit2/libgit2/archive/refs/tags/v$LIBGIT2_VERSION.zip" "$env:TEMP\libgit2.zip"
  Expand-Archive "$env:TEMP\libgit2.zip" -DestinationPath "$env:TEMP\libgit2x" -Force
  if (Test-Path "$ROOT\libgit2") { Remove-Item "$ROOT\libgit2" -Recurse -Force }
  Move-Item (Get-ChildItem "$env:TEMP\libgit2x" -Directory)[0].FullName "$ROOT\libgit2"
  cmake -S "$ROOT\libgit2" -B "$ROOT\libgit2\build64" -A x64 $PolicyMin `
    -DBUILD_SHARED_LIBS=ON -DBUILD_TESTS=OFF -DBUILD_CLI=OFF -DUSE_SSH=OFF -DREGEX_BACKEND=builtin
  cmake --build "$ROOT\libgit2\build64" --config Release
}

# --- 2. ngspice (DLL Windows précompilée + headers) -----------------------------
if (-not (Test-Path "$ROOT\ngspice-$NGSPICE_VERSION\include\ngspice\sharedspice.h")) {
  Write-Host "== ngspice $NGSPICE_VERSION (DLL précompilée) =="
  Get-File "https://downloads.sourceforge.net/project/ngspice/ng-spice-rework/old-releases/$NGSPICE_VERSION/ngspice-${NGSPICE_VERSION}_dll_64.7z" "$env:TEMP\ngspice.7z"
  & $SevenZip x "$env:TEMP\ngspice.7z" "-o$env:TEMP\ngspicex" -y | Out-Null
  $spice = Join-Path "$env:TEMP\ngspicex" "Spice64_dll"
  New-Item -ItemType Directory -Force "$ROOT\ngspice-$NGSPICE_VERSION" | Out-Null
  Copy-Item "$spice\include" "$ROOT\ngspice-$NGSPICE_VERSION\include" -Recurse -Force
  Copy-Item "$spice\dll-vs"  "$ROOT\ngspice-$NGSPICE_VERSION\dll-vs"  -Recurse -Force  # ngspice.dll + libomp140
}

# --- 3. Clipper1 / polyclipping (dossier Clipper1-6.4.2) ------------------------
if (-not (Test-Path "$ROOT\Clipper1-$CLIPPER_VERSION\lib\polyclipping.lib")) {
  Write-Host "== Clipper1 $CLIPPER_VERSION =="
  Get-File "https://downloads.sourceforge.net/project/polyclipping/clipper_ver$CLIPPER_VERSION.zip" "$env:TEMP\clipper.zip"
  Expand-Archive "$env:TEMP\clipper.zip" -DestinationPath "$env:TEMP\clipperx" -Force
  cmake -S "$env:TEMP\clipperx\cpp" -B "$env:TEMP\clipperx\cpp\build" -A x64 $PolicyMin `
    -DBUILD_SHARED_LIBS=ON -DCMAKE_INSTALL_PREFIX="$ROOT\Clipper1-$CLIPPER_VERSION"
  cmake --build "$env:TEMP\clipperx\cpp\build" --config Release --target install
}

# --- 4. svgpp (header-only) -----------------------------------------------------
if (-not (Test-Path "$ROOT\svgpp-$SVGPP_VERSION\include\svgpp\svgpp.hpp")) {
  Write-Host "== svgpp $SVGPP_VERSION =="
  Get-File "https://github.com/svgpp/svgpp/archive/refs/tags/v$SVGPP_VERSION.zip" "$env:TEMP\svgpp.zip"
  Expand-Archive "$env:TEMP\svgpp.zip" -DestinationPath "$env:TEMP\svgppx" -Force
  if (Test-Path "$ROOT\svgpp-$SVGPP_VERSION") { Remove-Item "$ROOT\svgpp-$SVGPP_VERSION" -Recurse -Force }
  Move-Item (Get-ChildItem "$env:TEMP\svgppx" -Directory)[0].FullName "$ROOT\svgpp-$SVGPP_VERSION"
}

# --- 5. boost (headers, sœur boost_1_85_0 auto-détectée) ------------------------
if (-not (Test-Path "$ROOT\boost_$BOOST_USCORE\boost\version.hpp")) {
  Write-Host "== boost $BOOST_USCORE (headers) =="
  $bv = $BOOST_USCORE.Replace("_", ".") -replace "\.0$",""   # 1_85_0 -> 1.85.0
  Get-File "https://archives.boost.io/release/$bv/source/boost_$BOOST_USCORE.7z" "$env:TEMP\boost.7z"
  & $SevenZip x "$env:TEMP\boost.7z" "-o$ROOT" -y | Out-Null
}

# --- 6. QuaZip (Qt6, chemin spécifique à la version Qt) -------------------------
$QUAZIP_DIR = "$ROOT\quazip-$QtVer-${QUAZIP_VERSION}intuisphere"
if (-not (Test-Path "$QUAZIP_DIR\lib\quazip1-qt6.lib")) {
  Write-Host "== QuaZip $QUAZIP_VERSION (Qt $QtVer) =="
  Get-File "https://github.com/stachenov/quazip/archive/refs/tags/v$QUAZIP_VERSION.zip" "$env:TEMP\quazip.zip"
  Expand-Archive "$env:TEMP\quazip.zip" -DestinationPath "$env:TEMP\quazipx" -Force
  $qsrc = (Get-ChildItem "$env:TEMP\quazipx" -Directory)[0].FullName
  cmake -S $qsrc -B "$qsrc\build" -A x64 $PolicyMin -DQUAZIP_QT_MAJOR_VERSION=6 `
    -DBUILD_SHARED_LIBS=ON -DCMAKE_PREFIX_PATH="$QtDir" -DCMAKE_INSTALL_PREFIX="$QUAZIP_DIR"
  cmake --build "$qsrc\build" --config Release --target install
}

# --- 7. Build (qmake + nmake) ---------------------------------------------------
Write-Host "== build Fritzing =="
$env:RELEASE_SCRIPT = "release_script"
Push-Location $FA
& $QMAKE -o Makefile phoenix.pro
nmake release
if ($LASTEXITCODE -ne 0) { throw "nmake a échoué ($LASTEXITCODE)" }
Pop-Location

$EXE = "$ROOT\release64\Fritzing.exe"
if (-not (Test-Path $EXE)) { throw "Fritzing.exe non produit" }

# --- 8. Packaging (windeployqt + DLLs + pièces -> zip) --------------------------
Write-Host "== packaging =="
$DEPLOY = "$ROOT\release64\deploy"
if (Test-Path $DEPLOY) { Remove-Item $DEPLOY -Recurse -Force }
New-Item -ItemType Directory -Force $DEPLOY | Out-Null
Copy-Item $EXE $DEPLOY

& "$QtDir\bin\windeployqt.exe" "$DEPLOY\Fritzing.exe" --release --no-translations

# DLLs tierces (windeployqt ne les voit pas)
Copy-Item "$ROOT\libgit2\build64\Release\git2.dll" $DEPLOY
Copy-Item "$QUAZIP_DIR\bin\quazip1-qt6.dll" $DEPLOY
Copy-Item "$ROOT\Clipper1-$CLIPPER_VERSION\bin\polyclipping.dll" $DEPLOY
Copy-Item "$ROOT\ngspice-$NGSPICE_VERSION\dll-vs\*.dll" $DEPLOY   # ngspice.dll + libomp140
# QtCore5Compat : référencé par QuaZip, pas toujours tiré par windeployqt
Copy-Item "$QtDir\bin\Qt6Core5Compat.dll" $DEPLOY -ErrorAction SilentlyContinue

# Ressources runtime
foreach ($d in @("sketches","help","translations")) { Copy-Item "$FA\$d" $DEPLOY -Recurse -Force }
Copy-Item "$FA\INSTALL.txt","$FA\README.md","$FA\LICENSE.GPL2","$FA\LICENSE.GPL3","$FA\LICENSE.CC-BY-SA" $DEPLOY -Force
Get-ChildItem "$DEPLOY\translations\*.ts" -ErrorAction SilentlyContinue | Remove-Item -Force

# Pièces + base de données
if (Test-Path "$ROOT\fritzing-parts") {
  Copy-Item "$ROOT\fritzing-parts" $DEPLOY -Recurse -Force
  & "$DEPLOY\Fritzing.exe" -pp "$DEPLOY\fritzing-parts" -db "$DEPLOY\fritzing-parts\parts.db"
} else {
  Write-Host "AVERTISSEMENT : fritzing-parts absent — pièces non embarquées"
}

# Zip final (binaires NON signés -> SmartScreen au 1er lancement, cf. README)
$ZIP = "$ROOT\Fritzing-win-$Arch.zip"
if (Test-Path $ZIP) { Remove-Item $ZIP -Force }
Compress-Archive -Path "$DEPLOY\*" -DestinationPath $ZIP
Write-Host ">> ZIP : $ZIP"
Write-Host ">> terminé."
