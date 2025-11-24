import os
import math
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.transform import from_origin
from rasterio.enums import Resampling as ResamplingEnums

folder_path = r'D:\SIG\raster\2020'
raster_files = [
    'Daniel_Alomia_2020.tif',
    'Hermilio_2020.tif',
    'Jose_Crespo_2020.tif',
    'Luyando_2020.tif',
    'Mariano_2020.tif',
    'rupa_rupa_2020.tif'
]
output_path = os.path.join(folder_path, 'union_2020_mosaic.tif')

# 1. Obtener referencia CRS, resolución y origen
ref_path = os.path.join(folder_path, raster_files[0])
with rasterio.open(ref_path) as ref_src:
    ref_crs = ref_src.crs
    ref_transform = ref_src.transform
    ref_res_x = ref_transform.a
    ref_res_y = abs(ref_transform.e)
    ref_origin_x = ref_transform.c
    ref_origin_y = ref_transform.f

# 2. Calcular extensión unión de todos los rásteres (en ref_crs)
all_bounds = []
for fname in raster_files:
    path = os.path.join(folder_path, fname)
    with rasterio.open(path) as src:
        src_bounds = src.bounds
        src_crs = src.crs
        if src_crs != ref_crs:
            b = transform_bounds(src_crs, ref_crs, *src_bounds, densify_pts=21)
        else:
            b = (src_bounds.left, src_bounds.bottom, src_bounds.right, src_bounds.top)
        all_bounds.append(b)
minx = min(b[0] for b in all_bounds)
miny = min(b[1] for b in all_bounds)
maxx = max(b[2] for b in all_bounds)
maxy = max(b[3] for b in all_bounds)

# 3. Alinear la extensión a la grilla del ráster de referencia
def snap_to_grid(x, origin, res, mode='floor'):
    if mode == 'floor':
        return origin + math.floor((x - origin) / res) * res
    elif mode == 'ceil':
        return origin + math.ceil((x - origin) / res) * res

minx_aligned = snap_to_grid(minx, ref_origin_x, ref_res_x, 'floor')
maxx_aligned = snap_to_grid(maxx, ref_origin_x, ref_res_x, 'ceil')
top_aligned = snap_to_grid(maxy, ref_origin_y, ref_res_y, 'floor')
bottom_aligned = snap_to_grid(miny, ref_origin_y, ref_res_y, 'ceil')

width = int(round((maxx_aligned - minx_aligned) / ref_res_x))
height = int(round((top_aligned - bottom_aligned) / ref_res_y))
if width <= 0 or height <= 0:
    raise RuntimeError('Extensión unión inválida: dimensiones no positivas.')

mosaic_transform = from_origin(minx_aligned, top_aligned, ref_res_x, ref_res_y)

# 4. Inicializar mosaicos vacíos
mosaic_b1 = np.zeros((height, width), dtype=np.uint16)
mosaic_b2 = np.zeros((height, width), dtype=np.uint16)

# 5. Reproyectar cada ráster y combinar por máximo (fecha más tardía)
for fname in raster_files:
    path = os.path.join(folder_path, fname)
    with rasterio.open(path) as src:
        b1 = src.read(1)
        b2 = src.read(2)
        tmp_b1 = np.zeros((height, width), dtype=np.uint16)
        tmp_b2 = np.zeros((height, width), dtype=np.uint16)

        reproject(
            source=b1, destination=tmp_b1,
            src_transform=src.transform, src_crs=src.crs,
            dst_transform=mosaic_transform, dst_crs=ref_crs,
            resampling=Resampling.nearest,
            src_nodata=0, dst_nodata=0
        )
        reproject(
            source=b2, destination=tmp_b2,
            src_transform=src.transform, src_crs=src.crs,
            dst_transform=mosaic_transform, dst_crs=ref_crs,
            resampling=Resampling.nearest,
            src_nodata=0, dst_nodata=0
        )
        # Enmascarar: burn_date solo donde dNBR==1
        tmp_b2 = np.where(tmp_b1 == 1, tmp_b2, 0).astype(np.uint16)
        # Combinar por máximo
        mosaic_b1 = np.maximum(mosaic_b1, tmp_b1)
        mosaic_b2 = np.maximum(mosaic_b2, tmp_b2)

# 6. Enmascarar banda 2 por banda 1 por última vez
mosaic_b2 = np.where(mosaic_b1 == 1, mosaic_b2, 0).astype(np.uint16)

# 7. Guardar resultado con tiling y compresión LZW + predictor
profile = {
    'driver': 'GTiff',
    'height': height,
    'width': width,
    'count': 2,
    'dtype': rasterio.uint16,
    'crs': ref_crs,
    'transform': mosaic_transform,
    'nodata': 0,
    'tiled': True,
    'blockxsize': 512,
    'blockysize': 512,
    'compress': 'LZW',
    'predictor': 2,
    'BIGTIFF': 'IF_SAFER'
}
with rasterio.open(output_path, 'w', **profile) as dst:
    dst.write(mosaic_b1, 1)
    dst.write(mosaic_b2, 2)
print(f'\n✅ Mosaico raster creado: {output_path}\n')

# 8. Crear pirámides internas (overviews) con rasterio
with rasterio.open(output_path, 'r+') as dst:
    dst.build_overviews([2, 4, 8, 16, 32], ResamplingEnums.nearest)
    dst.update_tags(ns='rio_overview', resampling='nearest')
print('✅ Pirámides internas (overviews) creadas.\n')

# 9. Reportar área quemada total
pixel_area_ha = (ref_res_x * ref_res_y) / 10000.0
burned_pixels = int(np.count_nonzero(mosaic_b1 == 1))
burned_area_ha = burned_pixels * pixel_area_ha
print(f'Pixeles quemados: {burned_pixels}\nÁrea quemada aprox.: {burned_area_ha:.2f} ha\n')
