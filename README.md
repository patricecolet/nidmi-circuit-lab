# nidmi-circuit-lab

Builds **gratuits et multiplateformes de [Fritzing](https://fritzing.org)** pour un usage
**pédagogique** : les étudiants travaillent sur le projet [`nidmi-modular`](../nidmi-modular)
(schémas, breadboard, stripboard) **sans payer** le binaire officiel.

Fritzing est open-source (GPLv3) : seul le binaire pré-compilé est payant. Ce dépôt
**compile Fritzing depuis les sources** via GitHub Actions et publie les binaires en
**Releases** — il suffit de télécharger.

> **Build éducatif non-officiel.** Ce n'est pas le projet Fritzing. Pour le binaire
> officiel et pour **soutenir le développement**, voir [fritzing.org](https://fritzing.org).

## Pour les étudiants — installer

1. Aller dans l'onglet **Releases** de ce dépôt.
2. Télécharger l'archive de son système : macOS (Apple Silicon / Intel), Windows ou Linux.
3. Décompresser et lancer Fritzing. (Pas de licence à payer.)

### macOS — première ouverture (app **non notarisée**)

Ces builds ne sont **ni signés ni notarisés** (pas de compte Apple Developer payant).
macOS (Gatekeeper) bloque donc le **premier** lancement.

> **Symptôme typique : rien ne se passe.** Sur macOS récent, l'app **ne s'ouvre pas et
> aucune fenêtre n'apparaît** — souvent **sans aucun message d'erreur**. Ce n'est pas un
> plantage : c'est Gatekeeper qui bloque une app téléchargée via un navigateur. Le
> déblocage ci-dessous (méthode A) règle le problème.

Faire glisser `Fritzing.app` dans **Applications**, puis débloquer :

**A. Le plus fiable — Terminal** (retire la mise en quarantaine). Fonctionne **même quand
aucun message n'apparaît** :

```bash
xattr -dr com.apple.quarantine /Applications/Fritzing.app
```

(adapter le chemin si l'app est ailleurs que dans `/Applications`). Relancer l'app ensuite.

**B. Interface** : clic droit sur l'app ▸ **Ouvrir** ▸ **Ouvrir** ; ou, si un message est
apparu, **Réglages Système ▸ Confidentialité et sécurité** ▸ **« Ouvrir quand même »**.
Sur macOS récent ce bouton **n'apparaît pas toujours** pour une app ad-hoc — dans ce cas,
utiliser la méthode A.

> Une fois débloquée, l'app s'ouvre normalement les fois suivantes. C'est attendu pour un
> logiciel libre auto-compilé, ce n'est pas un problème de sécurité.

### Windows — avertissement SmartScreen

Binaire non signé → SmartScreen peut afficher « Windows a protégé votre PC » :
**Informations complémentaires ▸ Exécuter quand même**.

## Statut

**Phase 1** (en cours) : compiler l'upstream **tel quel** pour les 3 OS → Releases.
Prochaines phases :

- **Phase 2** : précharger une **bibliothèque de pièces du projet** (virtualGround,
  whiteNoise, ADG2188…) pour démarrer prêt à l'emploi.
- **Phase 3** : léger **rebranding** (nom/icône « édition cours ») pour la question de marque.

## Comment ça marche

[`.github/workflows/build.yml`](.github/workflows/build.yml) :

- récupère `fritzing/fritzing-app` (épinglé `FRITZING_REF`) et `fritzing/fritzing-parts` ;
- installe **Qt 6** + dépendances (libgit2, boost, quazip, ngspice) par OS ;
- compile via **qmake** (`phoenix.pro`) ;
- archive les binaires en artefacts, et publie une **Release** (brouillon) sur tag `vX.Y.Z`.

> ⚠️ Le workflow est un **scaffold** : le build Fritzing est sensible aux versions, chaque
> job demandera 1–2 itérations pour passer. On débogue au premier run CI (voir les `TODO`).

## Conformité licence & crédits

- **Fritzing** — application : **GPLv3** (voir [`LICENSE`](LICENSE)). Code source :
  <https://github.com/fritzing/fritzing-app>. Toute redistribution de binaire ici garde la
  GPLv3 et pointe vers les sources, conformément à la licence.
- **fritzing-parts** — **CC-BY-SA**. Source : <https://github.com/fritzing/fritzing-parts>.
- « Fritzing » est une **marque** de l'association Fritzing ; ce dépôt n'est pas affilié.
  Le rebranding (Phase 3) lèvera toute ambiguïté de marque sur les binaires distribués.

### Soutenir Fritzing

Ce dépôt bénéficie du travail du projet Fritzing sans contribuer à son financement par la
vente du binaire. **Geste recommandé** : faire un **don de classe** à Fritzing et
**remonter les correctifs de build en upstream**. (Bon réflexe à enseigner.)

## Voir aussi

- [`docs/BUILD.md`](docs/BUILD.md) — build local manuel (pour déboguer la CI).
- [`../nidmi-modular/docs/BUILD_FRITZING.md`](../nidmi-modular/docs/BUILD_FRITZING.md) —
  notes de build d'origine.
