# Build local (debug de la CI)

Pour reproduire/déboguer un job de la CI en local avant de pousser.

## Principe

La CI ([`.github/workflows/build.yml`](../.github/workflows/build.yml)) fait, pour macOS :

1. `git clone` de `fritzing/fritzing-app` (commit `FRITZING_REF`, branche `develop`) et
   `fritzing/fritzing-parts` en **dossiers sœurs** ;
2. install **Qt 6.5.3** (modules `qtserialport` + `qt5compat`) ;
3. lance [`tools/macos/build-fritzing-mac.sh`](../tools/macos/build-fritzing-mac.sh) qui
   construit les deps sœurs, patche l'archi, `qmake`/`make`, puis package en `.app` + `.dmg`.

## macOS — pas à pas (validé arm64)

```bash
brew install boost cmake          # bison/flex/curl/unzip système suffisent

# Qt 6.5.3 : installeur Qt officiel, ou aqtinstall :
#   pipx run aqtinstall install-qt mac desktop 6.5.3 clang_64 -m qtserialport qt5compat
export QT_DIR="$HOME/Qt/6.5.3/macos"      # dossier contenant bin/qmake

mkdir -p ~/src/fritzing && cd ~/src/fritzing
git clone https://github.com/fritzing/fritzing-app.git
git clone https://github.com/fritzing/fritzing-parts.git
( cd fritzing-app && git checkout develop )

# le script attend fritzing-app/ (et fritzing-parts/) dans le dossier courant
QT_DIR="$QT_DIR" /chemin/vers/nidmi-circuit-lab/tools/macos/build-fritzing-mac.sh
# => ./release64/Fritzing.app  +  ./Fritzing-arm64.dmg
```

Le script construit ces **dépendances sœurs** (versions imposées par les `pri/*detect.pri`
de fritzing-app), toutes en `arch` cible :

| Dépendance | Version | Type | Pourquoi pas Homebrew |
|---|---|---|---|
| libgit2 | 1.7.1 | statique | `.pro` exige 1.7.1 static précis |
| ngspice | 42 | shared (`--with-ngshared`) | le brew est CLI-only, sans `libngspice`/headers |
| Clipper1 (polyclipping) | 6.4.2 | shared (`install_name @rpath`) | absent de brew |
| svgpp | 1.3.1 | header-only | absent de brew |
| QuaZip | 1.4 (vs Qt6) | shared | chemin `quazip-<QtVer>-1.4intuisphere` |
| boost | brew | headers | OK via `boost_root=$(brew --prefix)/include` |

## Points sensibles connus

- **Qt > 6.5.10** → `phoenix.pro` plafonne (`QT_MOST=6.5.10`) ; Qt 6.10 **compile les deps
  mais casse Fritzing** (API `QString::arg`, `QChar`). Rester en **6.5.3**.
- **`CONFIG += x86_64` codé en dur** dans `phoenix.pro` (section `macx`) : le script le
  remplace par l'arch cible (sinon build x86_64 forcé, link KO contre un Qt arm64).
- **macdeployqt ne bundle pas `QtCore5Compat`** (réclamé par QuaZip via rpath) → le script
  le copie à la main dans `Contents/Frameworks`.
- **`libngspice` n'est pas lié** (chargé par `dlopen` au runtime) → le script le place dans
  `Contents/PlugIns/` (cherché via `QCoreApplication::libraryPaths()`).
- **Signature ad-hoc obligatoire** : un binaire **arm64 non signé ne se lance pas**. Le script
  `codesign --force --deep --sign -` après chaque modification du bundle. Pas de notarisation
  (Gatekeeper bloque le 1er lancement — déblocage dans le [README](../README.md)).

Voir aussi [`../../nidmi-modular/docs/BUILD_FRITZING.md`](../../nidmi-modular/docs/BUILD_FRITZING.md).
