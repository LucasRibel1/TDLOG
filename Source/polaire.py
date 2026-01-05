import numpy as np
import csv
import pandas as pd
from conventions import clamp


def save_polar_to_csv(file_path_in, file_path_out):
    """Lit un fichier polaire TSV et l'enregistre en CSV."""
    with open(file_path_in, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    with open(file_path_out, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        for line in lines:
            row = line.split("\t")
            writer.writerow(row)

    print(f"Fichier CSV créé : {file_path_out}")


def load_polar_diagram(csv_path):
    """
    Charge polaires depuis CSV.
    Returns: (twa_array, tws_array, speed_matrix)
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
    Returns: Vitesse bateau (nœuds)
    """
    twa = abs(twa) % 360
    if twa > 180:
        twa = 360 - twa

    twa = clamp(twa, float(twa_array.min()), float(twa_array.max()))
    tws = clamp(tws, float(tws_array.min()), float(tws_array.max()))

    i = np.searchsorted(twa_array, twa)
    j = np.searchsorted(tws_array, tws)

    i_low = max(i - 1, 0)
    i_high = min(i, len(twa_array) - 1)
    j_low = max(j - 1, 0)
    j_high = min(j, len(tws_array) - 1)

    v_ll = speed_matrix[i_low, j_low]
    v_lh = speed_matrix[i_low, j_high]
    v_hl = speed_matrix[i_high, j_low]
    v_hh = speed_matrix[i_high, j_high]

    if tws_array[j_high] == tws_array[j_low]:
        tx = 0.0
    else:
        tx = (tws - tws_array[j_low]) / (tws_array[j_high] - tws_array[j_low])

    if twa_array[i_high] == twa_array[i_low]:
        ty = 0.0
    else:
        ty = (twa - twa_array[i_low]) / (twa_array[i_high] - twa_array[i_low])

    speed = (v_ll * (1 - tx) * (1 - ty) +
             v_lh * tx * (1 - ty) +
             v_hl * (1 - tx) * ty +
             v_hh * tx * ty)

    return float(max(speed, 0.0))


def get_max_speed(speed_matrix):
    """Vitesse maximale théorique du bateau."""
    return float(speed_matrix.max())


def compute_vmg_upwind(twa_deg: float, boat_speed_kn: float) -> float:
    """VMG au près (projection sur l'axe du vent) = V * cos(TWA)."""
    return float(boat_speed_kn * np.cos(np.radians(twa_deg)))


def compute_vmg_downwind(twa_deg: float, boat_speed_kn: float) -> float:
    """VMG au portant: on veut avancer "dans le sens du vent", projection ~ cos(180-TWA)."""
    return float(boat_speed_kn * np.cos(np.radians(180.0 - twa_deg)))


def find_optimal_twa_upwind(tws_kn: float, twa_array, tws_array, speed_matrix, search_min=25, search_max=80, step=1):
    """Cherche l'angle de près optimal pour TWS donné (max VMG upwind)."""
    best_twa = None
    best_vmg = -1e9
    for twa in range(search_min, search_max + 1, step):
        v = get_boat_speed(twa, tws_kn, twa_array, tws_array, speed_matrix)
        vmg = compute_vmg_upwind(twa, v)
        if vmg > best_vmg:
            best_vmg = vmg
            best_twa = float(twa)
    return best_twa, float(best_vmg)


def find_optimal_twa_downwind(tws_kn: float, twa_array, tws_array, speed_matrix, search_min=100, search_max=175, step=1):
    """Cherche l'angle de portant optimal pour TWS donné (max VMG downwind)."""
    best_twa = None
    best_vmg = -1e9
    for twa in range(search_min, search_max + 1, step):
        v = get_boat_speed(twa, tws_kn, twa_array, tws_array, speed_matrix)
        vmg = compute_vmg_downwind(twa, v)
        if vmg > best_vmg:
            best_vmg = vmg
            best_twa = float(twa)
    return best_twa, float(best_vmg)
