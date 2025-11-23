"""
Model exported as python.
Name : generar puntos de quema
Group : ambiental
With QGIS : 33000
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterRasterLayer
from qgis.core import QgsProcessingParameterFeatureSink
import processing


class GenerarPuntosDeQuema(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterNumber('distancia_minima', 'distancia minima', type=QgsProcessingParameterNumber.Double, defaultValue=None))
        self.addParameter(QgsProcessingParameterNumber('numero_de_puntos', 'numero de puntos', type=QgsProcessingParameterNumber.Integer, defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterLayer('raster', 'raster', defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('Quema', 'quema', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, supportsAppend=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(6, model_feedback)
        results = {}
        outputs = {}

        # Poligonizar (ráster a vectorial)
        alg_params = {
            'BAND': 1,
            'EIGHT_CONNECTEDNESS': False,
            'EXTRA': '',
            'FIELD': 'DN',
            'INPUT': parameters['raster'],
            'OUTPUT': 'TEMPORARY_OUTPUT',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['PoligonizarRsterAVectorial'] = processing.run('gdal:polygonize', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Extraer por atributo
        alg_params = {
            'FAIL_OUTPUT': None,
            'FIELD': 'DN',
            'INPUT': outputs['PoligonizarRsterAVectorial']['OUTPUT'],
            'OPERATOR': 0,  # =
            'OUTPUT': 'TEMPORARY_OUTPUT',
            'VALUE': '1',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtraerPorAtributo'] = processing.run('native:extractbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # Disolver
        alg_params = {
            'FIELD': ['1'],
            'INPUT': outputs['ExtraerPorAtributo']['OUTPUT'],
            'OUTPUT': 'TEMPORARY_OUTPUT',
            'SEPARATE_DISJOINT': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Disolver'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Puntos aleatorios en polígonos
        alg_params = {
            'INCLUDE_POLYGON_ATTRIBUTES': True,
            'INPUT': outputs['Disolver']['OUTPUT'],
            'MAX_TRIES_PER_POINT': 10,
            'MIN_DISTANCE': parameters['distancia_minima'],
            'MIN_DISTANCE_GLOBAL': 0,
            'OUTPUT': 'TEMPORARY_OUTPUT',
            'POINTS_NUMBER': parameters['numero_de_puntos'],
            'SEED': None,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['PuntosAleatoriosEnPolgonos'] = processing.run('native:randompointsinpolygons', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # Muestra de valores ráster
        alg_params = {
            'COLUMN_PREFIX': 'SAMPLE_',
            'INPUT': outputs['PuntosAleatoriosEnPolgonos']['OUTPUT'],
            'OUTPUT': 'TEMPORARY_OUTPUT',
            'RASTERCOPY': parameters['raster'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['MuestraDeValoresRster'] = processing.run('native:rastersampling', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # Calculadora de campos
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'fecha',
            'FIELD_PRECISION': 3,
            'FIELD_TYPE': 3,  # Fecha
            'FORMULA': "to_date('1970-01-01') + to_interval(SAMPLE_2 || ' days')",
            'INPUT': outputs['MuestraDeValoresRster']['OUTPUT'],
            'OUTPUT': parameters['Quema']
        }
        outputs['CalculadoraDeCampos'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Quema'] = outputs['CalculadoraDeCampos']['OUTPUT']
        return results

    def name(self):
        return 'generar puntos de quema'

    def displayName(self):
        return 'generar puntos de quema'

    def group(self):
        return 'ambiental'

    def groupId(self):
        return 'ambiental'

    def createInstance(self):
        return GenerarPuntosDeQuema()
