
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, box

# Rutas de entrada y salida
input_csv = r'D:\SIG\txt\FIRMS_2020.csv'                     # CSV con puntos
aoi_shp = r'D:\SIG\shapes\general\Daniel_Alomia_Robles.shp'              # AOI área de interés, distrito o provincia
output_points_shp = r'D:\SIG\shapes\2020\prueba2\Daniel_Alomia_Robles_puntos_FIRMS.shp'          # Puntos dentro del área de interés
output_squares_shp = r'D:\SIG\shapes\2020\prueba2\Daniel_Alomia_Robles_cuadrados_FIRMS.shp'      # Cuadrados recortados al área de interés

# --- Parte 1: generar puntos a partir del CSV y filtrar por AOI ---

# Leer CSV y AOI
df = pd.read_csv(input_csv)
aoi = gpd.read_file(aoi_shp)

# CONVERSIÓN de 'confidence'
df['confidence'] = df['confidence'].replace({
    'h': 80,
    'n': 55,
    'l': 30
})
df['confidence'] = pd.to_numeric(df['confidence'])

# Crear geometría de puntos (asumiendo columnas longitude y latitude)
geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')

# Reproyectar AOI a CRS de puntos si es necesario
if aoi.crs != gdf.crs:
    aoi = aoi.to_crs(gdf.crs)

# Filtrar puntos dentro del AOI (unir todos los polígonos del AOI)
aoi_union = aoi.geometry.union_all()
gdf_filtrado = gdf[gdf.within(aoi_union)]

# Guardar shapefile de puntos filtrados
gdf_filtrado.to_file(output_points_shp)
print(f"Shapefile filtrado de puntos guardado en: {output_points_shp}")

# --- Parte 2: generar cuadrados dinámicos y recortar con AOI ---

# Cargar shapefile de puntos filtrados
gdf_points = gpd.read_file(output_points_shp)
aoi = gpd.read_file(aoi_shp)  # Recargar AOI para seguir desde aquí

# Reproyectar ambos a EPSG:32718 (UTM Zona 18S Perú) para trabajar en metros
gdf_utm = gdf_points.to_crs('EPSG:32718')
aoi_utm = aoi.to_crs('EPSG:32718')

# Función para crear cuadrados dinámicos según instrumento
def create_dynamic_square(row):
    if row['instrument'] == 'MODIS':
        size = 1000
    elif row['instrument'] == 'VIIRS':
        size = 375
    else:
        size = 375
    half_size = size / 2
    point = row.geometry
    return box(point.x - half_size, point.y - half_size, point.x + half_size, point.y + half_size)

# Aplicar función para crear cuadrados
gdf_utm['geometry'] = gdf_utm.apply(create_dynamic_square, axis=1)

# Recortar cuadrados al AOI con overlay intersection
gdf_recortado = gpd.overlay(gdf_utm, aoi_utm, how='intersection')

# Guardar shapefile final de cuadrados recortados
gdf_recortado.to_file(output_squares_shp)
print(f'Shapefile de cuadrados recortados guardado en: {output_squares_shp}') # Esto va a assets en Google Earth Engine
