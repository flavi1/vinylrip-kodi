# vinylrip-kodi

Extension Kodi (Python 3, Kodi 21 « Omega » visé) qui pilote le moteur en ligne de commande
[`vinylrip`](https://github.com/flavi1/vinylrip) pour numériser des vinyles depuis une platine USB
en FLAC vérifié bit à bit. Le plugin reste mince : tout le travail (enregistrement, découpe,
identification MusicBrainz, encodage, vérification) est fait par le moteur, lancé en sous-processus
et piloté en JSON-lignes (`vinylrip --json session`).

## Fonctionnement

- **Service** : au démarrage de Kodi et pendant son exécution, surveille `/proc/asound/cards`.
  Quand la platine apparaît (carte USB audio, ou celle désignée dans les réglages), il propose
  *Enregistrer / Écouter / Annuler*.
- **Menu Musique > Extensions > Vinylrip** : enregistrer un disque, un album de plusieurs disques
  (nombre de disques prérempli à 2), écouter, choisir la qualité parmi celles que la carte annonce.
- **Par face** : « Démarrer la face A » → « Terminer la face A / Écouter / Annuler » →
  « Face suivante / Disque terminé / Annuler ». Annuler demande s'il faut supprimer l'enregistrement.
- **Erreur** : affichée avec le dossier où les enregistrements bruts sont conservés, pour finir à la main
  (`vinylrip process <dossier>`).
- **Choix de l'album** : automatique, ou liste à choisir selon le réglage `identify_mode`.

## Installation

1. Installer le moteur : `pip install vinylrip` (ou depuis le dépôt) ; `arecord`, `aplay`, `fpcalc`
   (chromaprint) et `flac` ≥ 1.4 (ou ffmpeg) doivent être présents.
2. Installer l'extension (zip de ce dépôt, dossier `plugin.audio.vinylrip`).
3. Réglages : commande du moteur, platine, clé AcoustID, dossier de sortie, modèles de nom…
   Les réglages sont convertis en fichier TOML pour le moteur à chaque lancement.

Kodi en Flatpak/Snap n'est pas pris en charge (le bac à sable bloque ALSA et le moteur).

## Tests

```
VINYLRIP_SRC=/chemin/vers/vinylrip/src python3 -m unittest discover -s tests
```

L'API Kodi est simulée (`tests/kodi_mock.py`) ; le moteur l'est aussi (`tests/fake_engine.py`).
Avec `VINYLRIP_SRC`, un test lance le vrai moteur et vérifie le protocole.

## Limites connues

- Non validé sur une vraie platine ni dans un vrai Kodi.
- Les boîtes de dialogue de Kodi sont modales : si `arecord` meurt pendant une face, l'erreur
  n'apparaît qu'à la fermeture de la boîte (« Terminer la face »).

## Licence

GPL-2.0-or-later (convention Kodi). Le moteur `vinylrip` est en GPL-3.0-or-later.
