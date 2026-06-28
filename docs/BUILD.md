# Build local (debug de la CI)

Pour reproduire/déboguer un job de la CI en local avant de pousser.

## Principe

La CI ([`.github/workflows/build.yml`](../.github/workflows/build.yml)) fait, par OS :

1. `git clone` de `fritzing/fritzing-app` (réf `FRITZING_REF`) et `fritzing/fritzing-parts`
   en **dossiers sœurs** ;
2. install **Qt 6** + deps (libgit2, boost, quazip, ngspice) ;
3. `qmake phoenix.pro CONFIG+=release` puis `make` ;
4. déploiement Qt + bundle des pièces + archive.

## macOS (arm64) — pas à pas

```bash
brew install qt libgit2 boost quazip ngspice
export PATH="$(brew --prefix qt)/bin:$PATH"

mkdir -p ~/src/fritzing && cd ~/src/fritzing
git clone --branch CD-625 https://github.com/fritzing/fritzing-app.git
git clone https://github.com/fritzing/fritzing-parts.git

cd fritzing-app
qmake phoenix.pro CONFIG+=release
make -j$(sysctl -n hw.ncpu)
```

Packaging propre : `tools/deploy_fritzing_mac.sh` (script officiel) → `.dmg`.
Voir aussi [`../../nidmi-modular/docs/BUILD_FRITZING.md`](../../nidmi-modular/docs/BUILD_FRITZING.md).

## Points sensibles connus

- **qmake introuvable** → `export PATH="$(brew --prefix qt)/bin:$PATH"`.
- **modules Qt manquants** → vérifier `modules:` dans le workflow vs ce qu'attend `phoenix.pro`
  (souvent `qtserialport`, `qt5compat`).
- **libgit2 / API** → la version distrib peut différer de l'attendue : se rabattre sur une
  libgit2 compilée localement si erreurs de link (cf. wiki officiel Fritzing).
- **dépendances sœurs** (Clipper2, svgpp…) : si `phoenix.pro` les réclame, les cloner en
  dossiers sœurs de `fritzing-app/`.
