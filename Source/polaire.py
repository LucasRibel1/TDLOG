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


def load_polar_diagram(csv_path):
    """
    Charge polaires depuis CSV.

    Returns:
        (twa_array, tws_array, speed_matrix)
    """
    df = pd.read_csv(csv_path)

    twa_array = df.iloc[:, 0].to_numpy()
    tws_array = df.columns[1:].astype(float).to_numpy()
    speed_matrix = df.iloc[:, 1:].to_numpy()

    print(f"✓ Polaires chargées: {len(twa_array)} TWA × {len(tws_array)} TWS")

    return twa_array, tws_array, speed_matrix


def get_boat_speed(twa, tws, twa_array, tws_array, speed_matrix):
    """
    Vitesse bateau interpolée depuis polaires.

    Args:
        twa: True Wind Angle (degrés)
        tws: True Wind Speed (nœuds)
        twa_array, tws_array, speed_matrix: données polaires

    Returns:
        Vitesse bateau (nœuds)
    """
    # Normaliser TWA (0-180)
    twa = abs(twa) % 360
    if twa > 180:
        twa = 360 - twa

    # Clamp dans limites
    twa = np.clip(twa, twa_array.min(), twa_array.max())
    tws = np.clip(tws, tws_array.min(), tws_array.max())

    # Indices encadrants
    i = np.searchsorted(twa_array, twa)
    j = np.searchsorted(tws_array, tws)

    i_low = max(i - 1, 0)
    i_high = min(i, len(twa_array) - 1)
    j_low = max(j - 1, 0)
    j_high = min(j, len(tws_array) - 1)

    # 4 vitesses
    v_ll = speed_matrix[i_low, j_low]
    v_lh = speed_matrix[i_low, j_high]
    v_hl = speed_matrix[i_high, j_low]
    v_hh = speed_matrix[i_high, j_high]

    # Fractions interpolation
    if tws_array[j_high] == tws_array[j_low]:
        tx = 0.0
    else:
        tx = (tws - tws_array[j_low]) / (tws_array[j_high] - tws_array[j_low])

    if twa_array[i_high] == twa_array[i_low]:
        ty = 0.0
    else:
        ty = (twa - twa_array[i_low]) / (twa_array[i_high] - twa_array[i_low])

    # Interpolation bilinéaire
    speed = (v_ll * (1 - tx) * (1 - ty) +
             v_lh * tx * (1 - ty) +
             v_hl * (1 - tx) * ty +
             v_hh * tx * ty)

    return float(max(speed, 0.0))


def get_max_speed(speed_matrix):
    """Vitesse maximale théorique du bateau."""
    return float(speed_matrix.max())






