# amiga-simcity-printcity

Rendu en PNG des villes de **SimCity Amiga** (Maxis, 1989), comme le fait
l'utilitaire **PrintCity** fourni sur la disquette du jeu, mais en couleurs
et dans un fichier au lieu de l'imprimante.

![giltown](docs/giltown.png)

## Utilisation

```sh
pip install pillow
python3 simcity_render.py SimData2 giltown "San Francisco" -o cartes/
python3 simcity_render.py SimData2 giltown --scale 2 -o cartes/
python3 simcity_render.py SimData2 --tiles tuiles.png     # planche des tuiles
```

`SimData2` vient de la disquette de SimCity : il n'est pas fourni ici
(données © Maxis). Les villes sont les fichiers de sauvegarde du jeu et
les scénarios du dossier `Scenarios/`.

Chaque ville donne une image de 960 × 800 pixels (120 × 100 tuiles de 8 × 8).

## Comment fonctionne PrintCity

PrintCity n'a besoin que de `SimData2` et d'un fichier ville. Il colle les
tuiles de `SimData2` dans une image en mémoire, puis l'envoie à
`printer.device`. Ce script refait ce rendu directement.

### SimData2

| Octets | Contenu |
|---|---|
| 0–1 | magique `D5 DB` |
| 2–3 | `$0010` (16 couleurs) |
| 4–5 | `$03D0` |
| 6–7 | 0 |
| 8–39 | palette de 16 couleurs, mots Amiga RGB4 (`$0RGB`) |
| 40– | 960 tuiles de 32 octets |

Une tuile fait 8 × 8 pixels en 4 plans de bits, rangés plan après plan :
8 octets pour le plan 0, puis le plan 1, etc. Le bit de poids fort de
chaque octet est le pixel de gauche.

### Fichier ville

Le fichier est enveloppé au format **MacBinary** (le jeu vient du Mac) :

| Octets | Contenu |
|---|---|
| 0 | 0 |
| 1 | longueur du nom |
| 2– | nom de la ville |
| 65–72 | type `CITY`, créateur `MCRP` |
| 83–86 | taille des données : 27 120 |
| 128– | les données (27 120 octets), puis remplissage jusqu'à un multiple de 128 |

Dans les données, la carte occupe les **24 000 derniers octets** :
120 colonnes de 100 mots big-endian, rangées colonne par colonne.
Les 10 bits de poids faible de chaque mot donnent le numéro de tuile ;
les bits de poids fort sont des drapeaux du jeu (alimentation, etc.).

Attention à bien partir de la fin des données et non de la fin du
fichier : les 16 octets de remplissage MacBinary décaleraient la carte de
8 tuiles, et le haut de chaque colonne se retrouverait en bas de l'image.
