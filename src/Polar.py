#On charge un fichier text de polaire et on le rend continuer pour avoir la vitesse du bateau à un certain angle au vent
file_path_in="Figaro2.txt"
file_path_out="Figaro2.csv"

import numpy as np
import csv

def save_polar_to_csv(file_path_in, file_path_out):
    """
    Lit un fichier polaire TSV et l'enregistre en CSV.
    """
    # Charger le fichier TSV
    with open(file_path_in, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    # Écrire dans un fichier CSV
    with open(file_path_out, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        for line in lines:
            row = line.split("\t")
            writer.writerow(row)

    print(f"Fichier CSV créé : {file_path_out}")


save_polar_to_csv(file_path_in, file_path_out)



