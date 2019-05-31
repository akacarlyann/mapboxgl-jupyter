import codecs
import json
import os

from IPython.core.display import HTML, display

import numpy
import requests

from mapboxgl.errors import TokenError, LegendError
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
        )

        # add global map options
        options.update(map_options)

        if self.label_property is None:
            options.update(labelProperty=None)
        else:
            options.update(labelProperty='{' + self.label_property + '}')

        options.update(
            labelColor=self.label_color,
            labelSize=self.label_size,
            labelHaloColor=self.label_halo_color,
            labelHaloWidth=self.label_halo_width,
            highlightColor=self.highlight_color,
        )

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
                 highlight_color='black',
                 *args, 
                 **kwargs):
        
        super(CircleLayer, self).__init__(data, *args, **kwargs)

        self.template = 'circle_layer'
        self.check_vector_template()

        self.color_property = color_property
        self.color_stops = color_stops
        self.radius = radius
        self.stroke_color = stroke_color
        self.stroke_width = stroke_width
        self.color_function_type = color_function_type
        self.color_default = color_default
        self.legend_key_shape = 'circle'
        self.highlight_color = highlight_color

    def add_unique_layer_variables(self, options):
        """Update map template variables specific to circle visual"""
        options.update(dict(
            geojson_data=json.dumps(self.data, ensure_ascii=False),
            colorProperty=self.color_property,
            colorType=self.color_function_type,
            colorStops=self.color_stops,
            strokeWidth=self.stroke_width,
            strokeColor=self.stroke_color,
            radius=self.radius,
            defaultColor=self.color_default,
            highlightColor=self.highlight_color,
            maxzoom=self.max_zoom,
            minzoom=self.min_zoom,
            belowLayer=self.below_layer
        ))

        if self.vector_source:
            options.update(vectorColorStops=self.generate_vector_color_map())


# class GraduatedCircleLayer(MapLayer):

#     def __init__(self, *args, **kwargs):
#         self.below_layer = below_layer


# class HeatmapLayer(MapLayer):

#     def __init__(self, *args, **kwargs):
#         self.below_layer = below_layer


# class ClusteredCircleLayer(MapLayer):

#     def __init__(self, *args, **kwargs):
#         self.below_layer = below_layer


# class ChoroplethLayer(MapLayer):

#     def __init__(self, *args, **kwargs):
#         self.below_layer = below_layer


# class ImageLayer(MapLayer):

#     def __init__(self, *args, **kwargs):
#         self.below_layer = below_layer


# class RasterTilesLayer(MapLayer):

#     def __init__(self, *args, **kwargs):
#         self.below_layer = below_layer


# class LinestringLayer(MapLayer):

#     def __init__(self, *args, **kwargs):
#         self.below_layer = below_layer

