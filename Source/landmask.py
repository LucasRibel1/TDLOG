import rasterio
import numpy as np


class LandMask:
    """Gestionnaire du masque terre/mer avec détection automatique."""

    def __init__(self, tif_path="landmask.tif"):
        """Charge le fichier landmask."""
        try:
            self.dataset = rasterio.open(tif_path)
            self.data = self.dataset.read(1)
            print(f"✓ Landmask chargé: {tif_path}")
            print(f"  Dimensions: {self.data.shape}")
            print(f"  Bounds: {self.dataset.bounds}")

            # DIAGNOSTIC : Détecter la convention
            unique_values = np.unique(self.data)
            print(f"  Valeurs uniques dans le raster: {unique_values}")

            # Compter occurrences
            counts = {val: np.sum(self.data == val) for val in unique_values}
            print(f"  Répartition: {counts}")

            # Déterminer convention
            # GSHHS : généralement 255=terre, 0=eau OU 1=terre, 0=eau
            # Zenodo : 100=terre, 0=eau
            # Standard : 1=mer, 0=terre

            if 255 in unique_values:
                self.sea_value = 0
                self.land_value = 255
                print(f"  ✓ Convention détectée: 0=eau, 255=terre (GSHHS)")
            elif 100 in unique_values:
                self.sea_value = 0
                self.land_value = 100
                print(f"  ✓ Convention détectée: 0=eau, 100=terre (Zenodo)")
            elif len(unique_values) == 2 and 0 in unique_values and 1 in unique_values:
                # Déterminer qui est qui par proportion
                # Généralement plus d'eau que de terre sur Terre
                count_0 = counts[0]
                count_1 = counts[1]

                if count_0 > count_1:
                    # Plus de 0 → probablement 0=eau
                    self.sea_value = 0
                    self.land_value = 1
                    print(f"  ✓ Convention détectée: 0=eau, 1=terre (plus de 0)")
                else:
                    # Plus de 1 → probablement 1=eau
                    self.sea_value = 1
                    self.land_value = 0
                    print(f"  ✓ Convention détectée: 1=eau, 0=terre (plus de 1)")
            else:
                # Par défaut
                self.sea_value = 1
                self.land_value = 0
                print(f"  Convention par défaut: 1=eau, 0=terre")

            print(f"  → Valeur mer: {self.sea_value}, Valeur terre: {self.land_value}")

        except Exception as e:
            print(f"✗ Erreur chargement landmask: {e}")
            self.dataset = None
            self.data = None
            self.sea_value = None
            self.land_value = None

    def is_sea(self, lat, lon):
        """
        Vérifie si une position est en mer.

        Returns:
            True si mer, False si terre
        """
        if self.dataset is None:
            return True  # Pas de landmask = tout en mer

        try:
            # Convertir coordonnées GPS en indices raster
            row, col = self.dataset.index(lon, lat)

            # Vérifier limites
            if row < 0 or row >= self.data.shape[0] or col < 0 or col >= self.data.shape[1]:
                print(f"  Hors limites: ({lat:.2f}, {lon:.2f})")
                return False  # Hors limites = terre (sécurité)

            # Lire valeur
            value = self.data[row, col]
            is_water = (value == self.sea_value)

            return is_water

        except Exception as e:
            print(f"  ✗ Erreur is_sea({lat}, {lon}): {e}")
            return False  # Erreur = terre (sécurité)

    def is_path_clear(self, lat1, lon1, lat2, lon2, n_samples=5):
        """
        Vérifie qu'un segment ne traverse pas la terre.

        Returns:
            True si le chemin est libre (mer uniquement)
        """
        for i in range(n_samples + 1):
            alpha = i / n_samples
            lat = lat1 + (lat2 - lat1) * alpha
            lon = lon1 + (lon2 - lon1) * alpha

            if not self.is_sea(lat, lon):
                return False

        return True

    def test_position(self, lat, lon, name="Point"):
        """Test et affiche résultat pour une position."""
        result = self.is_sea(lat, lon)
        status = "MER" if result else "TERRE"
        print(f"  {name}: ({lat:.2f}°N, {lon:.2f}°W) → {status}")

        # Afficher valeur du pixel
        if self.dataset:
            try:
                row, col = self.dataset.index(lon, lat)
                if 0 <= row < self.data.shape[0] and 0 <= col < self.data.shape[1]:
                    pixel_value = self.data[row, col]
                    print(f"    Valeur pixel: {pixel_value}")
            except:
                pass

        return result

    def close(self):
        """Fermer le dataset."""
        if self.dataset:
            self.dataset.close()


# Initialiser landmask avec diagnostic
print("\n" + "="*70)
print("CHARGEMENT LANDMASK")
print("="*70 + "\n")

landmask = LandMask("gshhs_land_water_mask_3km_i.tif")

# TESTS DE POSITIONS
print("\n" + "="*70)
print("TESTS POSITIONS")
print("="*70 + "\n")

# Positions test
test_positions = [
    (38.71, -9.14, "Lisbonne (port)"),
    (38.60, -9.50, "Large Lisbonne"),
    (38.50, -9.70, "Large Lisbonne (30km)"),
    (38.00, -10.00, "Pleine mer"),
    (40.00, -9.00, "Portugal centre"),
    (33.59, -7.62, "Casablanca (port)"),
    (33.50, -7.80, "Large Casablanca"),
]

for lat, lon, name in test_positions:
    landmask.test_position(lat, lon, name)

print("\n" + "="*70)
