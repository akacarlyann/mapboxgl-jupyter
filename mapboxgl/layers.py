import codecs
import json
import os

from IPython.core.display import HTML, display

import numpy
import requests

from mapboxgl.errors import LegendError
from mapboxgl.utils import color_map, numeric_map, img_encode, geojson_to_dict_list
from mapboxgl import templates


class VectorMixin(object):

    def generate_vector_color_map(self):
        """Generate color stops array for use with match expression in mapbox template"""
        vector_stops = []

        # if join data specified as filename or URL, parse JSON to list of Python dicts
        if type(self.data) == str:
            self.data = geojson_to_dict_list(self.data)

        # loop through features in self.data to create join-data map
        for row in self.data:
            
            # print(row)

            # map color to JSON feature using color_property
            color = color_map(row[self.color_property], self.color_stops, self.color_default)

            # link to vector feature using data_join_property (from JSON object)
            vector_stops.append([row[self.data_join_property], color])

        return vector_stops

    def generate_vector_numeric_map(self, numeric_property):
        """Generate stops array for use with match expression in mapbox template"""
        vector_stops = []
        
        function_type = getattr(self, '{}_function_type'.format(numeric_property))
        lookup_property = getattr(self, '{}_property'.format(numeric_property))
        numeric_stops = getattr(self, '{}_stops'.format(numeric_property))
        default = getattr(self, '{}_default'.format(numeric_property))

        if function_type == 'match':
            match_width = numeric_stops

        # if join data specified as filename or URL, parse JSON to list of Python dicts
        if type(self.data) == str:
            self.data = geojson_to_dict_list(self.data)

        for row in self.data:

            # map value to JSON feature using the numeric property
            value = numeric_map(row[lookup_property], numeric_stops, default)
            
            # link to vector feature using data_join_property (from JSON object)
            vector_stops.append([row[self.data_join_property], value])

        return vector_stops

    def check_vector_template(self):
        """Determines if features are defined as vector source based on MapViz arguments."""

        if self.vector_url is not None and self.vector_layer_name is not None:
            self.template = 'vector_' + self.template
            self.vector_source = True
        else:
            self.vector_source = False


class MapLayer(object):
    """
    base map layer object
    """
    def __init__(self, 
                 data,
                 vector_url=None,
                 vector_layer_name=None,
                 vector_join_property=None,
                 data_join_property=None,
                 disable_data_join=False,
                 below_layer='waterway-label',
                 opacity=1,
                 label_property=None,
                 label_size=8,
                 label_color='#131516',
                 label_halo_color='white',
                 label_halo_width=1,
                 highlight_color='black',
                 min_zoom=0,
                 max_zoom=24,
                 layer_id=None,
                 popup_open_action='hover'):
        """
        :param data: GeoJSON Feature Collection
        :param vector_url: optional property to define vector data source
        :param vector_layer_name: property to define target layer of vector source
        :param vector_join_property: property to aid in determining color for styling vector layer
        :param data_join_property: property to join json data to vector features
        :param disable_data_join: property to switch off default data-join technique using vector layer and JSON join-data; 
                                  also determines if a layer filter based on joined data is applied to features in vector layer
        :param below_layer: render this layer below "below_layer"
        :param opacity: opacity of map data layer
        :param label_property: property to use for marker label
        :param label_size: size of label text
        :param label_color: color of label text
        :param label_halo_color: color of label text halo
        :param label_halo_width: width of label text halo
        :param min_zoom: min zoom for layer visibility
        :param max_zoom: max zoom for layer visibility
        :param popup_open_action: controls behavior of opening and closing feature popups; one of 'hover' or 'click'
        """

        self.data = data
        
        self.vector_url = vector_url
        self.vector_layer_name = vector_layer_name
        self.vector_join_property = vector_join_property
        self.data_join_property = data_join_property
        self.disable_data_join = disable_data_join

        self.template = 'layer'
        try:
            self.check_vector_template()
        except AttributeError:
            self.vector_source = False

        self.below_layer = below_layer
        self.opacity = opacity
        self.label_property = label_property
        self.label_color = label_color
        self.label_size = label_size
        self.label_halo_color = label_halo_color
        self.label_halo_width = label_halo_width
        self.highlight_color = highlight_color
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom

        self.layer_id = layer_id
        self.popup_open_action = popup_open_action

    def create_layer_html(self, map_options):

        # layer info
        options = dict(
            geojson_data=json.dumps(self.data, ensure_ascii=False),
            belowLayer=self.below_layer,
            opacity=self.opacity,
            layerId=self.layer_id,
            template=self.template,
            minzoom=self.min_zoom,
            maxzoom=self.max_zoom,
            popupOpensOnHover=self.popup_open_action=='hover',
            labelColor=self.label_color,
            labelSize=self.label_size,
            labelHaloColor=self.label_halo_color,
            labelHaloWidth=self.label_halo_width,
            highlightColor=self.highlight_color)

        # add global map options
        options.update(map_options)

        if self.label_property is None:
            options.update(labelProperty=None)
        else:
            options.update(labelProperty='{' + self.label_property + '}')

        # vector layer support
        if self.vector_source:
            options.update(
                vectorUrl=self.vector_url,
                vectorLayer=self.vector_layer_name,
                vectorJoinDataProperty=self.vector_join_property,
                joinData=json.dumps(False),
                dataJoinProperty=self.data_join_property,
                enableDataJoin=not self.disable_data_join
            )
            data = geojson_to_dict_list(self.data)
            if bool(data):
                options.update(joinData=json.dumps(data, ensure_ascii=False))

        self.add_unique_layer_variables(options)

        return templates.format(self.template, **options)

    def add_unique_layer_variables(self, options):
        pass


class CircleLayer(VectorMixin, MapLayer):

    def __init__(self, 
                 data,
                 radius=1,
                 color_property=None,
                 color_stops=None,
                 color_default='grey',
                 color_function_type='interpolate',
                 stroke_color='grey',
                 stroke_width=0.1,
                 legend_key_shape='circle',
                 *args, 
                 **kwargs):
        
        super(CircleLayer, self).__init__(data, *args, **kwargs)

        self.template = 'circle_layer'
        self.color_property = color_property
        self.color_stops = color_stops
        self.radius = radius
        self.stroke_color = stroke_color
        self.stroke_width = stroke_width
        self.color_function_type = color_function_type
        self.color_default = color_default
        self.legend_key_shape = 'circle'

    def add_unique_layer_variables(self, options):
        """Update map template variables specific to circle visual"""
        options.update(dict(
            colorProperty=self.color_property,
            colorType=self.color_function_type,
            colorStops=self.color_stops,
            strokeWidth=self.stroke_width,
            strokeColor=self.stroke_color,
            radius=self.radius,
            defaultColor=self.color_default,
        ))
        if self.vector_source:
            options.update(vectorColorStops=self.generate_vector_color_map())


class GraduatedCircleLayer(MapLayer):

    def __init__(self,
                 data,
                 color_property=None,
                 color_stops=None,
                 color_default='grey',
                 color_function_type='interpolate',
                 stroke_color='grey',
                 stroke_width=0.1,
                 radius_property=None,
                 radius_stops=None,
                 radius_default=2,
                 radius_function_type='interpolate',
                 legend_key_shape='circle',
                 *args,
                 **kwargs):
        """
        Construct a GraduatedCircleLayer object

        :param data: GeoJSON Feature Collection
        :param color_default: property to determine default circle color if match lookup fails
        :param color_function_type: property to determine `type` used by Mapbox to assign color
        :param color_property: property to determine circle color
        :param color_stops: property to determine circle color
        :param radius_default: property to determine default circle radius if match lookup fails
        :param radius_function_type: property to determine `type` used by Mapbox to assign radius size
        :param radius_property: property to determine circle radius
        :param radius_stops: property to determine circle radius
        :param stroke_color: color of circle stroke outline
        :param stroke_width: with of circle stroke outline
        """
        super(GraduatedCircleLayer, self).__init__(data, *args, **kwargs)

        self.template = 'graduated_circle_layer'
        self.color_default = color_default
        self.color_function_type = color_function_type
        self.color_property = color_property
        self.color_stops = color_stops
        self.legend_key_shape = legend_key_shape
        self.radius_property = radius_property
        self.radius_stops = radius_stops
        self.radius_default = radius_default
        self.radius_function_type = radius_function_type
        self.stroke_color = stroke_color
        self.stroke_width = stroke_width

    def add_unique_layer_variables(self, options):
        """
        Update map template variables specific to graduated circle visual
        """
        options.update(dict(
            colorProperty=self.color_property,
            colorStops=self.color_stops,
            colorType=self.color_function_type,
            radiusType=self.radius_function_type,
            defaultColor=self.color_default,
            defaultRadius=self.radius_default,
            radiusProperty=self.radius_property,
            radiusStops=self.radius_stops,
            strokeWidth=self.stroke_width,
            strokeColor=self.stroke_color,
        ))
        if self.vector_source:
            options.update(dict(
                vectorColorStops=self.generate_vector_color_map(),
                vectorRadiusStops=self.generate_vector_numeric_map('radius')))


class HeatmapLayer(MapLayer):

    def __init__(self,
                 data,
                 weight_property=None,
                 weight_stops=None,
                 color_stops=None,
                 radius_stops=None,
                 intensity_stops=None, 
                 *args, 
                 **kwargs):

        super(HeatmapLayer, self).__init__(data, *args, **kwargs)

        self.template = 'heatmap_layer'
        self.weight_property = weight_property
        self.weight_stops = weight_stops

        # Make the first color stop in a heatmap have opacity 0 for good visual effect
        if color_stops:
            self.color_stops = [[0.00001, 'rgba(0,0,0,0)']] + color_stops

        self.radius_stops = radius_stops
        self.intensity_stops = intensity_stops

    def add_unique_layer_variables(self, options):
        """
        Update map template variables specific to heatmap visual
        """
        options.update(dict(
            weightProperty=self.weight_property,
            weightStops=self.weight_stops,
            colorStops=self.color_stops,
            radiusStops=self.radius_stops,
            intensityStops=self.intensity_stops,
        ))
        if self.vector_source:
            options.update(dict(
                vectorWeightStops=self.generate_vector_numeric_map('weight')))

    def generate_vector_numeric_map(self, numeric_property):
        """Generate stops array for use with match expression in mapbox template"""
        vector_stops = []
        
        lookup_property = getattr(self, '{}_property'.format(numeric_property))
        numeric_stops = getattr(self, '{}_stops'.format(numeric_property))

        # if join data specified as filename or URL, parse JSON to list of Python dicts
        if type(self.data) == str:
            self.data = geojson_to_dict_list(self.data)

        for row in self.data:

            # map value to JSON feature using the numeric property
            value = numeric_map(row[lookup_property], numeric_stops, 0)
            
            # link to vector feature using data_join_property (from JSON object)
            vector_stops.append([row[self.data_join_property], value])

        return vector_stops


class ClusteredCircleLayer(MapLayer):

    def __init__(self, 
                 data,
                 color_stops=None,
                 radius_stops=None,
                 cluster_radius=30,
                 cluster_maxzoom=14,
                 radius_default=2,
                 color_default='black',
                 stroke_color='grey',
                 stroke_width=0.1,
                 legend_key_shape='circle',
                 *args,
                 **kwargs):
       
        super(ClusteredCircleLayer, self).__init__(data, *args, **kwargs)

        self.template = 'clustered_circle_layer'

        self.color_stops = color_stops
        self.radius_stops = radius_stops
        self.cluster_radius = cluster_radius
        self.cluster_maxzoom = cluster_maxzoom
        self.radius_default = radius_default
        self.color_default = color_default
        self.stroke_color = stroke_color
        self.stroke_width = stroke_width
        self.legend_key_shape = legend_key_shape

    def add_unique_layer_variables(self, options):
        """Update map template variables specific to a clustered circle visual"""
        options.update(dict(
            colorStops=self.color_stops,
            colorDefault=self.color_default,
            radiusStops=self.radius_stops,
            clusterRadius=self.cluster_radius,
            clusterMaxZoom=self.cluster_maxzoom,
            strokeWidth=self.stroke_width,
            strokeColor=self.stroke_color,
            radiusDefault=self.radius_default,
        ))


# class ChoroplethLayer(MapLayer):

#     def __init__(self, *args, **kwargs):
#         self.below_layer = below_layer


class ImageLayer(MapLayer):

    def __init__(self, 
                 image,
                 coordinates,
                 legend=False,
                 *args, 
                 **kwargs):

        super(ImageLayer, self).__init__(None, *args, **kwargs)

        self.template = 'image_layer'
        if type(image) is numpy.ndarray:
            image = img_encode(image)
        self.image = image
        self.coordinates = coordinates
        self.legend = legend

    def add_unique_layer_variables(self, options):
        """Update map template variables specific to image visual"""
        options.update(dict(
            image=self.image,
            coordinates=self.coordinates))


# class RasterTilesLayer(MapLayer):

#     def __init__(self, *args, **kwargs):
#         self.below_layer = below_layer


# class LinestringLayer(MapLayer):

#     def __init__(self, *args, **kwargs):
#         self.below_layer = below_layer

