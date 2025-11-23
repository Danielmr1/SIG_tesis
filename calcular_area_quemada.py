import rasterio
import numpy as np

# Ruta al raster
raster_path = r'D:\SIG\raster\permisivo.tif'

# Abrir raster
with rasterio.open(raster_path) as src:
    raster = src.read(1)  # Leer banda 1
    transform = src.transform
    crs = src.crs
    
    # Verificar el valor de NoData
    nodata_value = src.nodata
    if nodata_value is not None:
        # Crear una máscara para los píxeles NoData
        raster = np.ma.masked_equal(raster, nodata_value)
    
    # Calcular el tamaño del píxel en metros cuadrados
    pixel_area = abs(transform.a * transform.e)  # tamaño píxel en m² (a y e definen escala)

# Conteo de píxeles con valor 1 (quemado)
burned_pixels = np.sum(raster == 1)

# Calcular área quemada en m²
burned_area_m2 = burned_pixels * pixel_area

# Convertir a hectáreas
burned_area_ha = burned_area_m2 / 10000

print(f"Área quemada: {burned_area_m2:.2f} m²")
print(f"Área quemada: {burned_area_ha:.2f} ha")
