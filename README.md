# **Routeur météorologique A* – Projet scolaire TDLOG**

Ce dépôt contient un routeur météo pour la navigation à la voile, développé dans le cadre d’un projet scolaire de **TDLOG**.

L’objectif est de calculer une **route optimale** entre deux points en mer en tenant compte :
- de la **météo** (vent),
- des **performances du bateau** (polaires).

---

## **Objectifs du projet**

- Mettre en œuvre un **algorithme de recherche de chemin (A\*)** sur un problème réel de navigation.
- Intégrer des **données météorologiques** :
  - fichiers **GRIB**,
  - ou données issues d’une **API météo**.
- Utiliser des **polaires de bateau** pour modéliser la vitesse en fonction du vent.
- Prendre en compte plusieurs **contraintes réalistes** :
  - évolution du vent dans le temps,
  - évitement des côtes (*landmask*),
  - coût des manœuvres (virements / empannages),
  - temps total de parcours.

---

## **Fonctionnalités principales**

- Calcul d’une route « optimale » entre un **point de départ** et un **point d’arrivée** (latitude / longitude).
- Algorithme **A\*** spatio-temporel intégrant :
  - interpolation spatio-temporelle du vent,
  - prise en compte de la **VMG** et de la direction de la destination,
  - pénalités liées aux manœuvres et au vent faible.
- Lecture et gestion des données :
  - polaires sous forme de matrice **TWA × TWS**,
  - fichiers **GRIB** (U10 / V10 à 10 m, grille 2D),
  - **landmask raster** (terre / mer).
- Visualisation de la route sur une carte interactive (**Folium**) avec :
  - trace du trajet,
  - flèches de vent le long de la route,
  - informations sur la durée et la distance.

---

## **Organisation du dépôt**

- `main.py`  
  Point d’entrée du programme (configuration, lancement du routeur, affichage).

- `routeur.py`  
  Implémentation de l’algorithme **A\*** et génération des waypoints.

- `meteo.py`  
  Chargement et interpolation du vent à partir des fichiers **GRIB**.

- `meteo_openmeteo_*.py` *(optionnel)*  
  Intégration de l’API **Open-Meteo** pour annoter la route avec un vent « temps réel ».

- `polaires.py`  
  Chargement et interrogation des polaires du bateau.

- `landmask.py`  
  Gestion du masque terre / mer pour éviter de traverser les côtes.

- `affichage.py`  
  Génération de la carte interactive (**HTML**) de la route.

- `docs/`  
  Fichiers annexes (masque de terre, notes, etc.).

- `data/`  
  Fichiers de données (GRIB, polaires, exemples).

---

*Les noms de fichiers peuvent légèrement varier selon la version du projet, mais la structure logique reste la même.*
