// Cargar el shapefile de FIRMS con cuadrados ya cortados, todos dentro del área de estudio
var fireAreas = ee.FeatureCollection('projects/generar-contorno/assets/Jose_Crespo_cuadrados_FIRMS');

// Filtro para valores 'confidence' numéricos mayores o iguales a 55
var filteredFireAreas = fireAreas.filter(ee.Filter.gte('confidence', 55));

Map.centerObject(filteredFireAreas, 9);
Map.addLayer(filteredFireAreas, {color: 'white', fillColor: '00000000'}, 'Filtered Fire Areas');

// Función para enmascarar nubes en Sentinel-2
var maskClouds = function(image) {
  var qa = image.select('QA60');
  var cloudBitMask = ee.Number(1).leftShift(10);
  var cirrusBitMask = ee.Number(1).leftShift(11);
  var mask = qa.bitwiseAnd(cloudBitMask).eq(0).and(qa.bitwiseAnd(cirrusBitMask).eq(0));
  return image.updateMask(mask).divide(10000);
};

// Función para calcular dNBR y agregar banda con fecha de detección limitada al área quemada
var calculateDeltaNBR = function(feature) {
  var acqDate = ee.Date(feature.get('acq_date'));

  var pre_fire_start = acqDate.advance(-60, 'day');
  var pre_fire_end = acqDate.advance(-1, 'day');

  var post_fire_start = acqDate.advance(1, 'day');
  var post_fire_end = acqDate.advance(60, 'day');

  var pre_fire_image = ee.ImageCollection('COPERNICUS/S2')
    .filterBounds(feature.geometry())
    .filterDate(pre_fire_start, pre_fire_end)
    .map(maskClouds)
    .median();

  var post_fire_image = ee.ImageCollection('COPERNICUS/S2')
    .filterBounds(feature.geometry())
    .filterDate(post_fire_start, post_fire_end)
    .map(maskClouds)
    .median();

  var nbr_pre = pre_fire_image.normalizedDifference(['B8', 'B12']).rename('NBR_pre');
  var nbr_post = post_fire_image.normalizedDifference(['B8', 'B12']).rename('NBR_post');

  var delta_nbr = nbr_pre.subtract(nbr_post).rename('dNBR');

  var threshold = 0.27;
  var burned_area_mask_int16 = delta_nbr.gte(threshold).toInt16().clip(feature.geometry());

  var baseDate = ee.Date('1970-01-01');
  var date_band = ee.Image.constant(acqDate.difference(baseDate, 'day')).rename('burn_date').toInt16();

  // Limitar valores de fecha solo al área quemada
  var date_band_masked = date_band.updateMask(burned_area_mask_int16);

  var burned_mask_with_date = burned_area_mask_int16.addBands(date_band_masked);

  return burned_mask_with_date.set({
    'system:index': feature.get('system:index'),
    'acq_date': feature.get('acq_date')
  });
};

// Obtener lista de features filtrados
var fireAreasList = filteredFireAreas.toList(filteredFireAreas.size());

// OPCION 1: Procesar solo las primeras 10 áreas para visualizar
var numAreasToProcessViz = 10;

var burnedMasks = ee.List.sequence(0, numAreasToProcessViz - 1).map(function(index) {
  var feature = ee.Feature(fireAreasList.get(index));
  return calculateDeltaNBR(feature);
});

var burnedCollection = ee.ImageCollection.fromImages(burnedMasks);
var burnedMosaicRGB = burnedCollection.mosaic();

// Reproyectar mascara de 10 áreas para exportación y visualización
var targetCRS = 'EPSG:32718';
var scale = 20;

var burnedMosaicRGB_utm = burnedMosaicRGB.reproject({
  crs: targetCRS,
  scale: scale
});

// Visualizar SOLO la banda 'dNBR' para evitar error de paleta con multibanda
Map.addLayer(burnedMosaicRGB_utm.select('dNBR'), {palette: ['black', 'red'], min: 0, max: 1, opacity: 0.8}, 'Burned Areas (10)');

var centerPoints = ee.List.sequence(0, numAreasToProcessViz - 1).map(function(index) {
  var feature = ee.Feature(fireAreasList.get(index));
  return feature.setGeometry(feature.geometry().centroid());
});

var centerCollection = ee.FeatureCollection(centerPoints);
Map.addLayer(centerCollection, {color: 'yellow', pointSize: 10}, 'Area centers');

print('Areas visualized: ' + numAreasToProcessViz);

// OPCION 2: Procesar TODAS las áreas filtradas para exportar
var totalAreas = filteredFireAreas.size().getInfo();
print('Procesando todas las áreas filtradas para exportar: ' + totalAreas);

var allBurnedMasks = ee.List.sequence(0, totalAreas - 1).map(function(index) {
  var feature = ee.Feature(fireAreasList.get(index));
  return calculateDeltaNBR(feature);
});

var allBurnedCollection = ee.ImageCollection.fromImages(allBurnedMasks);
var allBurnedMosaic = allBurnedCollection.mosaic();

// Reproyectar el mosaico total antes de exportar
var allBurnedMosaic_utm = allBurnedMosaic.reproject({
  crs: targetCRS,
  scale: scale
});

print('Total areas processed: ' + totalAreas);

// EXPORTAR COMO RASTER GeoTIFF a Google Drive
Export.image.toDrive({
  image: allBurnedMosaic_utm,
  description: 'burned_areas_all_filtered_FIRMS_UTM',
  scale: scale,
  region: filteredFireAreas.geometry(),
  fileFormat: 'GeoTIFF',
  maxPixels: 1e13
});

print('Exportacion iniciada: burned_areas_all_filtered_FIRMS_UTM.tif');

// TAMBIÉN exportar las 10 áreas visualizadas
Export.image.toDrive({
  image: burnedMosaicRGB_utm,
  description: 'burned_areas_10_filtered_FIRMS_visualization_UTM',
  scale: scale,
  region: filteredFireAreas.geometry(),
  fileFormat: 'GeoTIFF',
  maxPixels: 1e13
});

print('Exportacion iniciada: burned_areas_10_filtered_FIRMS_visualization_UTM.tif');

// EXPORTAR como ImageCollection Asset a tu proyecto
Export.image.toAsset({
  image: allBurnedMosaic_utm,
  description: 'burned_areas_all_filtered_asset_UTM',
  assetId: 'projects/generar-contorno/assets/burned_areas_filtered_FIRMS_UTM',
  scale: scale,
  region: filteredFireAreas.geometry(),
  maxPixels: 1e13
});

print('Exportacion a Asset iniciada: burned_areas_filtered_FIRMS_UTM');
