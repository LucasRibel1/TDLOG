import rasterio
import numpy as np


class LandMask:
    """Gestionnaire du masque terre/mer avec détection automatique."""

    def __init__(self, tif_path="landmask.tif", verbose=True):
        self.dataset = None
        self.data = None
        self.sea_value = None
        self.land_value = None

        try:
            self.dataset = rasterio.open(tif_path)
            self.data = self.dataset.read(1)

            if verbose:
                print(f"✓ Landmask chargé: {tif_path}")
                print(f"  Dimensions: {self.data.shape}")
                print(f"  Bounds: {self.dataset.bounds}")

            unique_values = np.unique(self.data)

            counts = {int(val): int(np.sum(self.data == val)) for val in unique_values}
            if verbose:
                print(f"  Valeurs uniques dans le raster: {unique_values}")
                print(f"  Répartition: {counts}")

            if 255 in unique_values:
                self.sea_value = 0
                self.land_value = 255
                if verbose:
                    print("  ✓ Convention détectée: 0=eau, 255=terre (GSHHS)")
            elif 100 in unique_values:
                self.sea_value = 0
                self.land_value = 100
                if verbose:
                    print("  ✓ Convention détectée: 0=eau, 100=terre (Zenodo)")
            elif len(unique_values) == 2 and 0 in unique_values and 1 in unique_values:
                count_0 = counts[0]
                count_1 = counts[1]
                if count_0 > count_1:
                    self.sea_value = 0
                    self.land_value = 1
                    if verbose:
                        print("  ✓ Convention détectée: 0=eau, 1=terre")
                else:
                    self.sea_value = 1
                    self.land_value = 0
                    if verbose:
                        print("  ✓ Convention détectée: 1=eau, 0=terre")
            else:
                self.sea_value = 1
                self.land_value = 0
                if verbose:
                    print("  Convention par défaut: 1=eau, 0=terre")

            if verbose:
                print(f"  → Valeur mer: {self.sea_value}, Valeur terre: {self.land_value}")

        except Exception as e:
            if verbose:
                print(f"✗ Erreur chargement landmask: {e}")
            self.dataset = None
            self.data = None

    def is_sea(self, lat, lon):
        """True si mer, False si terre (sécurité: hors limites/erreur => terre)."""
        if self.dataset is None:
            return True

        try:
            row, col = self.dataset.index(lon, lat)
            if row < 0 or row >= self.data.shape[0] or col < 0 or col >= self.data.shape[1]:
                return False
            value = self.data[row, col]
            return bool(value == self.sea_value)
        except Exception:
            return False

    def is_path_clear(self, lat1, lon1, lat2, lon2, n_samples=8):
        """Vérifie qu'un segment ne traverse pas la terre."""
        for i in range(n_samples + 1):
            a = i / n_samples
            lat = lat1 + (lat2 - lat1) * a
            lon = lon1 + (lon2 - lon1) * a
            if not self.is_sea(lat, lon):
                return False
        return True

    def close(self):
        if self.dataset:
            self.dataset.close()


def run_landmask_diagnostic(tif_path, test_positions):
    """Diagnostic optionnel (appel explicite)."""
    lm = LandMask(tif_path, verbose=True)
    print("\n" + "=" * 70)
    print("TESTS POSITIONS")
    print("=" * 70 + "\n")
    for lat, lon, name in test_positions:
        status = "MER" if lm.is_sea(lat, lon) else "TERRE"
        print(f"  {name}: ({lat:.2f}, {lon:.2f}) → {status}")
    return lm
