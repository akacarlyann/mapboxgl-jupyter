import codecs
import json
import os

from IPython.core.display import HTML, display

import numpy

from mapboxgl.errors import TokenError, LegendError
from mapboxgl.utils import color_map, numeric_map, img_encode, geojson_to_dict_list
from mapboxgl import templates

from mapboxgl.layers import *

GL_JS_VERSION = 'v0.53.0'


class MapViz(object):

    def __init__(self,
                 access_token=None,
                 center=(0, 0),
                 div_id='map',
                 height='500px',
                 style='mapbox://styles/mapbox/light-v10?optimize=true',
                 width='100%',
                 zoom=0,
                 pitch=0,
                 bearing=0,
                 box_zoom_on=True,
                 double_click_zoom_on=True,
                 scroll_zoom_on=True,
                 touch_zoom_on=True,
                 legend=False,
                 scale=False,
                 add_snapshot_links=False,
                 popup_open_action='hover'):
        """
        Construct a MapViz object

        :param access_token: Mapbox GL JS access token.
        :param center: map center point
        :param style: url to mapbox style or stylesheet as a Python dictionary in JSON format
        :param div_id: The HTML div id of the map container in the viz
        :param width: The CSS width of the HTML div id in % or pixels.
        :param height: The CSS height of the HTML map div in % or pixels.
        :param zoom: starting zoom level for map
        :param pitch: starting pitch (in degrees) for map
        :param bearing: starting bearing (in degrees) for map
        :param box_zoom_on: boolean indicating if map can be zoomed to a region by dragging a bounding box
        :param double_click_zoom_on: boolean indicating if map can be zoomed with double-click
        :param scroll_zoom_on: boolean indicating if map can be zoomed with the scroll wheel
        :param touch_zoom_on: boolean indicating if map can be zoomed with two-finger touch gestures
        :param popup_open_action: controls behavior of opening and closing feature popups; one of 'hover' or 'click'
        :param legend: boolean for whether to show legend on map
        :param scale: add map control showing current scale of map
        :param add_snapshot_links: boolean switch for adding buttons to download screen captures of map or legend

        """
        if access_token is None:
            access_token = os.environ.get('MAPBOX_ACCESS_TOKEN', '')
        if access_token.startswith('sk'):
            raise TokenError('Mapbox access token must be public (pk), not secret (sk). ' \
                             'Please sign up at https://www.mapbox.com/signup/ to get a public token. ' \
                             'If you already have an account, you can retreive your token at https://www.mapbox.com/account/.')
        self.access_token = access_token

        self.template = 'map'

        self.div_id = div_id
        self.width = width
        self.height = height
        self.style = style
        self.center = center
        self.zoom = zoom
        self.pitch = pitch
        self.bearing = bearing
        self.box_zoom_on = box_zoom_on
        self.double_click_zoom_on = double_click_zoom_on
        self.scroll_zoom_on = scroll_zoom_on
        self.touch_zoom_on = touch_zoom_on
        self.popup_open_action = popup_open_action

        # legend configuration
        self.legend = False
        self.legend_gradient = False
        
        # export "snapshot" configuration
        self.add_snapshot_links = False

        # scale configuration
        self.scale = False

        # layers configuration
        self.layers = {}
        self.layer_id_counter = 0

    def as_iframe(self, html_data):
        """Build the HTML representation for the mapviz."""

        srcdoc = html_data.replace('"', "'")
        return ('<iframe id="{div_id}", srcdoc="{srcdoc}" style="width: {width}; '
                'height: {height};"></iframe>'.format(
                    div_id=self.div_id,
                    srcdoc=srcdoc,
                    width=self.width,
                    height=self.height))

    def show(self, **kwargs):
        """display map in iframe in Jupyter cell"""
        # Load the HTML iframe
        html = self.create_html(**kwargs)
        map_html = self.as_iframe(html)

        # Display the iframe in the current jupyter notebook view
        display(HTML(map_html))

    def create_html(self, filename=None):
        """Create a circle visual from a geojson data source"""
        
        if isinstance(self.style, str):
            style = "'{}'".format(self.style)
        else:
            style = self.style
        
        options = dict(
            gl_js_version=GL_JS_VERSION,
            accessToken=self.access_token,
            div_id=self.div_id,
            style=style,
            center=list(self.center),
            zoom=self.zoom,
            pitch=self.pitch, 
            bearing=self.bearing,
            boxZoomOn=json.dumps(self.box_zoom_on),
            doubleClickZoomOn=json.dumps(self.double_click_zoom_on),
            scrollZoomOn=json.dumps(self.scroll_zoom_on),
            touchZoomOn=json.dumps(self.touch_zoom_on),
            popupOpensOnHover=self.popup_open_action=='hover',
            showScale=self.scale,
            includeSnapshotLinks=self.add_snapshot_links,
            preserveDrawingBuffer=json.dumps(False),
            showLegend=self.legend,
            legendGradient=json.dumps(False),
            legendKeyBordersOn=json.dumps(False),
            layersHtml=''
        )

        if self.add_snapshot_links:
            options.update(dict(
                includeSnapshotLinks=self.add_snapshot_links,
                preserveDrawingBuffer=json.dumps(self.add_snapshot_links),
            ))

        if self.scale:
            options.update(dict(
                showScale=self.scale,
                scaleUnits=self.scale_unit_system,
                scaleBorderColor=self.scale_border_color,
                scalePosition=self.scale_position,
                scaleFillColor=self.scale_background_color,
                scaleTextColor=self.scale_text_color,
        ))

        if self.legend:

            if all([self.legend, self.legend_gradient, self.legend_function == 'radius']):
                raise LegendError(' '.join(['Gradient legend format not compatible with a variable radius legend.',
                                            'Please either change `legend_gradient` to False or `legend_function` to "color".']))

            options.update(
                showLegend=self.legend,
                legendLayout=self.legend_layout,
                legendFunction=self.legend_function,
                legendStyle=self.legend_style, # reserve for custom CSS
                legendGradient=json.dumps(self.legend_gradient),
                legendFill=self.legend_fill,
                legendHeaderFill=self.legend_header_fill,
                legendTextColor=self.legend_text_color,
                legendNumericPrecision=json.dumps(self.legend_text_numeric_precision),
                legendTitleHaloColor=self.legend_title_halo_color,
                legendKeyShape=self.legend_key_shape,
                legendKeyBordersOn=json.dumps(self.legend_key_borders_on)
            )

        # build html from template(s)
        rendered_html = ''
        for layer_id, layer in self.layers.items():
            rendered_html = rendered_html + '\n' + layer.create_layer_html(options)

        options.update(layersHtml=rendered_html)

        html = templates.format(self.template, **options)

        if filename:

            with codecs.open(filename, 'w', 'utf-8-sig') as f:
                f.write(html)
            return None
        else:
            return html

    def add_legend(self, map_legend_object=None):
        """
        add MapLegend object
        """
        if isinstance(map_legend_object, MapLegend):
            self.legend = True
            self.legend_layout = map_legend_object.legend_layout
            self.legend_function = map_legend_object.legend_function
            self.legend_style = map_legend_object.legend_style
            self.legend_gradient = map_legend_object.legend_gradient
            self.legend_fill = map_legend_object.legend_fill
            self.legend_header_fill = map_legend_object.legend_header_fill
            self.legend_text_color = map_legend_object.legend_text_color
            self.legend_text_numeric_precision = map_legend_object.legend_text_numeric_precision
            self.legend_title_halo_color = map_legend_object.legend_title_halo_color
            if not self.legend_key_shape:
                self.legend_key_shape = map_legend_object.legend_key_shape
            self.legend_key_borders_on = map_legend_object.legend_key_borders_on

        else:
            raise TypeError('<map_legend_object> must be instance of <MapLegend>.')

    def add_map_scale(self, map_scale_object=None):
        """
        add MapScale object
        """
        if isinstance(map_scale_object, MapScale):
            self.scale = True
            self.scale_unit_system = map_scale_object.scale_unit_system
            self.scale_position = map_scale_object.scale_position
            self.scale_border_color = map_scale_object.scale_border_color
            self.scale_background_color = map_scale_object.scale_background_color
            self.scale_text_color = map_scale_object.scale_text_color
        elif map_scale_object is None:
            self.scale = True
            map_scale_object = MapScale()
            self.scale_unit_system = map_scale_object.scale_unit_system
            self.scale_position = map_scale_object.scale_position
            self.scale_border_color = map_scale_object.scale_border_color
            self.scale_background_color = map_scale_object.scale_background_color
            self.scale_text_color = map_scale_object.scale_text_color
        else:
            raise TypeError('<map_scale_object> must be instance of <MapScale>.')

    def add_map_snapshot(self, map_snapshot_object=None):
        """
        add 'snapshot' or screen capture menu
        """
        if isinstance(map_snapshot_object, MapScale):
            self.add_snapshot_links = True
            self.snapshot_position = map_snapshot_object.snapshot_position
            self.snapshot_border_color = map_snapshot_object.snapshot_border_color
            self.snapshot_background_color = map_snapshot_object.snapshot_background_color
            self.snapshot_text_color = map_snapshot_object.snapshot_text_color
        elif map_snapshot_object is None:
            self.add_snapshot_links = True
            map_snapshot_object = MapSnapshot()
            self.snapshot_position = map_snapshot_object.snapshot_position
            self.snapshot_border_color = map_snapshot_object.snapshot_border_color
            self.snapshot_background_color = map_snapshot_object.snapshot_background_color
            self.snapshot_text_color = map_snapshot_object.snapshot_text_color
        else:
            raise TypeError('<map_snapshot_object> must be instance of <MapSnapshot>.')

    def remove_map_scale(self):
        """
        remove or hide map's scale bar
        """
        self.scale = False

    def remove_map_snapshot(self):
        """
        remove or hide map's snapshot menu
        """
        self.add_snapshot_links = False

    def remove_legend(self):
        """
        remove or hide map's legend
        """
        self.legend = False

    def add_layer(self, layer_object):
        """
        add MapLayer instance to MapViz
        """
        # layer_object.layer_id = self.layer_id_counter
        # self.layer_id_counter += 1

        if layer_object.layer_id is None:
            if len(self.layers.keys()) > 0:
                layer_object.layer_id = max(self.layers.keys()) + 1
            else:
                layer_object.layer_id = 0

        i = len(self.layers)
        self.layers.update({i: layer_object})

    def remove_layer(self, layer_object):
        """
        remove MapLayer instance from MapViz
        """
        self.layers = {k: v for k, v in self.layers.items() if v != layer_object}

        # self.layers.pop(layer_object)
        # layer.show_legend = False


class MapScale(object):
    """
    map scale bar configuration
    """

    def __init__(self,
                 scale=False,
                 scale_unit_system='metric',
                 scale_position='bottom-left',
                 scale_border_color='#6e6e6e', 
                 scale_background_color='white',
                 scale_text_color='#131516'):
        """
        :param scale: add map control showing current scale of map
        :param scale_unit_system: choose units for scale display (metric, nautical or imperial)
        :param scale_position: location of the scale annotation
        :param scale_border_color: border color of the scale annotation
        :param scale_background_color: fill color of the scale annotation
        :param scale_text_color: text color the scale annotation
        """
        self.scale = scale
        self.scale_unit_system = scale_unit_system
        self.scale_position = scale_position
        self.scale_border_color = scale_border_color
        self.scale_background_color = scale_background_color
        self.scale_text_color = scale_text_color


class MapSnapshot(object):
    """
    map control menu for exporting screen capture of map and legend
    """
    
    def __init__(self, 
                 add_snapshot_links=False,
                 snapshot_position=None,
                 snapshot_border_color='#6e6e6e',
                 snapshot_background_color='#fff',
                 snapshot_text_color='#131516'):

        """
        :param add_snapshot_links: boolean switch for adding buttons to download 
                                   screen captures of map or legend
        :param snapshot_position: snapshot_position
        :param snapshot_border_color: snapshot_border_color
        :param snapshot_background_color: snapshot_background_color
        :param snapshot_text_color: snapshot_text_color
        """
        self.add_snapshot_links = add_snapshot_links
        self.snapshot_position = snapshot_position
        self.snapshot_border_color = snapshot_border_color
        self.snapshot_background_color = snapshot_background_color
        self.snapshot_text_color = snapshot_text_color


class MapLegend(object):
    """
    map legend configuration object
    """

    def __init__(self,
                 legend_layout='vertical',
                 legend_function='color',
                 legend_gradient=False,
                 legend_style='',
                 legend_fill='white',
                 legend_header_fill='white',
                 legend_text_color='#6e6e6e',
                 legend_text_numeric_precision=None,
                 legend_title_halo_color='white',
                 legend_key_shape='square',
                 legend_key_borders_on=True):
        """
        :param legend_layout: determines if horizontal or vertical legend used
        :param legend_function: controls whether legend is color or radius-based
        :param legend_style: reserved for future custom CSS loader
        :param legend_gradient: boolean to determine if legend keys are discrete or gradient
        :param legend_fill: string background color for legend, default is white
        :param legend_header_fill: string background color for legend header (in vertical layout), default is #eee
        :param legend_text_color: string color for legend text default is #6e6e6e
        :param legend_text_numeric_precision: decimal precision for numeric legend values
        :param legend_title_halo_color: color of legend title text halo
        :param legend_key_shape: shape of the legend item keys, default varies by viz type; one of square, contiguous_bar, rounded-square, circle, line
        :param legend_key_borders_on: boolean for whether to show/hide legend key borders
        """

        self.legend_layout = legend_layout
        self.legend_function = legend_function
        self.legend_style = legend_style
        self.legend_gradient = legend_gradient
        self.legend_fill = legend_fill
        self.legend_header_fill = legend_header_fill
        self.legend_text_color = legend_text_color
        self.legend_text_numeric_precision = legend_text_numeric_precision
        self.legend_title_halo_color = legend_title_halo_color
        self.legend_key_shape = legend_key_shape
        self.legend_key_borders_on = legend_key_borders_on


class CircleViz(MapViz):
    """ Create a circle map """

    def __init__(self,
                 data,
                 vector_url=None,
                 vector_layer_name=None,
                 vector_join_property=None,
                 data_join_property=None,
                 disable_data_join=False,
                 radius=1,
                 color_property=None,
                 color_stops=None,
                 color_default='grey',
                 color_function_type='interpolate',
                 stroke_color='grey',
                 stroke_width=0.1,
                 legend_key_shape='circle',
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
                 popup_open_action='hover',
                 *args,
                 **kwargs):
        """
        Construct a Mapviz object with CircleLayer visualization

        :param color_property: property to determine circle color
        :param color_stops: property to determine circle color
        :param color_default: property to determine default circle color if match lookup fails
        :param color_function_type: property to determine `type` used by Mapbox to assign color
        :param radius: radius of circle
        :param stroke_color: color of circle stroke outline
        :param stroke_width: with of circle stroke outline
        :param highlight_color: color for feature selection, hover, or highlight
        :param below_layer: render this layer below "below_layer"
        """
        super(CircleViz, self).__init__(*args, **kwargs)

        layer = CircleLayer(data,
                            vector_url=vector_url,
                            vector_layer_name=vector_layer_name,
                            vector_join_property=vector_join_property,
                            data_join_property=data_join_property,
                            disable_data_join=disable_data_join,
                            color_property=color_property,
                            color_stops=color_stops,
                            radius=radius,
                            stroke_color=stroke_color,
                            stroke_width=stroke_width,
                            color_function_type=color_function_type,
                            color_default=color_default,
                            legend_key_shape=legend_key_shape,
                            highlight_color=highlight_color,
                            below_layer=below_layer,
                            opacity=opacity,
                            label_property=label_property,
                            label_size=label_size,
                            label_color=label_color,
                            label_halo_color=label_halo_color,
                            label_halo_width=label_halo_width,
                            min_zoom=min_zoom,
                            max_zoom=max_zoom,
                            layer_id=layer_id,
                            popup_open_action=popup_open_action)

        self.add_layer(layer)


class GraduatedCircleViz(MapViz):
    """Create a graduated circle map"""

    def __init__(self,
                 data,
                 vector_url=None,
                 vector_layer_name=None,
                 vector_join_property=None,
                 data_join_property=None,
                 disable_data_join=False,
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
                 popup_open_action='hover',
                 *args,
                 **kwargs):
        """Construct a Mapviz object

        :param color_property: property to determine circle color
        :param color_stops: property to determine circle color
        :param color_default: property to determine default circle color if match lookup fails
        :param color_function_type: property to determine `type` used by Mapbox to assign color
        :param radius_property: property to determine circle radius
        :param radius_stops: property to determine circle radius
        :param radius_default: property to determine default circle radius if match lookup fails
        :param radius_function_type: property to determine `type` used by Mapbox to assign radius size
        :param stroke_color: color of circle stroke outline
        :param stroke_width: with of circle stroke outline
        :param highlight_color: color for feature selection, hover, or highlight

        """
        super(GraduatedCircleViz, self).__init__(*args, **kwargs)

        layer = GraduatedCircleLayer(data,
                                     vector_url=vector_url,
                                     vector_layer_name=vector_layer_name,
                                     vector_join_property=vector_join_property,
                                     data_join_property=data_join_property,
                                     disable_data_join=disable_data_join,
                                     color_property=color_property,
                                     color_stops=color_stops,
                                     color_function_type=color_function_type,
                                     color_default=color_default,
                                     radius_property=radius_property,
                                     radius_stops=radius_stops,
                                     radius_function_type=radius_function_type,
                                     radius_default=radius_default,
                                     stroke_color=stroke_color,
                                     stroke_width=stroke_width,
                                     legend_key_shape=legend_key_shape,
                                     highlight_color=highlight_color,
                                     below_layer=below_layer,
                                     opacity=opacity,
                                     label_property=label_property,
                                     label_size=label_size,
                                     label_color=label_color,
                                     label_halo_color=label_halo_color,
                                     label_halo_width=label_halo_width,
                                     min_zoom=min_zoom,
                                     max_zoom=max_zoom,
                                     layer_id=layer_id,
                                     popup_open_action=popup_open_action)

        self.add_layer(layer)


class HeatmapViz(MapViz):
    """Create a heatmap viz"""

    def __init__(self,
                 data,
                 vector_url=None,
                 vector_layer_name=None,
                 vector_join_property=None,
                 data_join_property=None,
                 disable_data_join=False,
                 below_layer='waterway-label',
                 opacity=1,
                 min_zoom=0,
                 max_zoom=24,
                 layer_id=None,
                 weight_property=None,
                 weight_stops=None,
                 color_stops=None,
                 radius_stops=None,
                 intensity_stops=None,
                 *args,
                 **kwargs):
        """Construct a Mapviz object

        :param weight_property: property to determine heatmap weight. EX. "population"
        :param weight_stops: stops to determine heatmap weight.  EX. [[10, 0], [100, 1]]
        :param color_stops: stops to determine heatmap color.  EX. [[0, "red"], [0.5, "blue"], [1, "green"]]
        :param radius_stops: stops to determine heatmap radius based on zoom.  EX: [[0, 1], [12, 30]]
        :param intensity_stops: stops to determine the heatmap intensity based on zoom. EX: [[0, 0.1], [20, 5]]
        
        """
        super(HeatmapViz, self).__init__(*args, **kwargs)

        layer = HeatmapLayer(data,
                             vector_url=vector_url,
                             vector_layer_name=vector_layer_name,
                             vector_join_property=vector_join_property,
                             data_join_property=data_join_property,
                             disable_data_join=disable_data_join,
                             weight_property=weight_property,
                             weight_stops=weight_stops,
                             color_stops=color_stops,
                             radius_stops=radius_stops,
                             intensity_stops=intensity_stops,
                             below_layer=below_layer,
                             opacity=opacity,
                             min_zoom=min_zoom,
                             max_zoom=max_zoom,
                             layer_id=layer_id)

        self.add_layer(layer)


class ClusteredCircleViz(MapViz):
    """Create a clustered circle map (geojson only)"""

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
                 highlight_color='black',
                 *args,
                 **kwargs):
        """Construct a Mapviz object 

        :param color_property: property to determine circle color
        :param color_stops: property to determine circle color
        :param radius_property: property to determine circle radius
        :param radius_stops: property to determine circle radius
        :param stroke_color: color of circle stroke outline
        :param stroke_width: with of circle stroke outline
        :param radius_default: radius of circles not contained in a cluster
        :param color_default: color of circles not contained in a cluster
        :param highlight_color: color for feature selection, hover, or highlight

        """
        super(ClusteredCircleViz, self).__init__(data, *args, **kwargs)

        self.template = 'clustered_circle'
        self.color_stops = color_stops
        self.radius_stops = radius_stops
        self.clusterRadius = cluster_radius
        self.clusterMaxZoom = cluster_maxzoom
        self.radius_default = radius_default
        self.color_default = color_default
        self.stroke_color = stroke_color
        self.stroke_width = stroke_width
        self.color_default = color_default
        self.legend_key_shape = legend_key_shape
        self.highlight_color = highlight_color

    def add_unique_template_variables(self, options):
        """Update map template variables specific to a clustered circle visual"""
        options.update(dict(
            colorStops=self.color_stops,
            colorDefault=self.color_default,
            radiusStops=self.radius_stops,
            clusterRadius=self.clusterRadius,
            clusterMaxZoom=self.clusterMaxZoom,
            strokeWidth=self.stroke_width,
            strokeColor=self.stroke_color,
            radiusDefault=self.radius_default,
            highlightColor=self.highlight_color
        ))


class ChoroplethViz(MapViz):
    """Create a choropleth viz"""

    def __init__(self,
                 data,
                 color_property=None,
                 color_stops=None,
                 color_default='grey',
                 color_function_type='interpolate',
                 line_color='white',
                 line_stroke='solid',
                 line_width=1,
                 height_property=None,      
                 height_stops=None,
                 height_default=0.0,
                 height_function_type='interpolate',
                 legend_key_shape='rounded-square',
                 highlight_color='black',
                 *args,
                 **kwargs):
        """Construct a Mapviz object

        :param data: can be either GeoJSON (containing polygon features) or JSON for data-join technique with vector polygons
        :param vector_url: optional property to define vector polygon source
        :param vector_layer_name: property to define target layer of vector source
        :param vector_join_property: property to aid in determining color for styling vector polygons
        :param data_join_property: property to join json data to vector features
        :param color_property: property to determine polygon color
        :param color_stops: property to determine polygon color
        :param color_default: property to determine default polygon color if match lookup fails
        :param color_function_type: property to determine `type` used by Mapbox to assign color
        :param line_color: property to determine choropleth line color
        :param line_stroke: property to determine choropleth line stroke (solid, dashed, dotted, dash dot)
        :param line_width: property to determine choropleth line width
        :param height_property: feature property for determining polygon height in 3D extruded choropleth map
        :param height_stops: property for determining 3D extrusion height
        :param height_default: default height for 3D extruded polygons
        :param height_function_type: property to determine `type` used by Mapbox to assign height
        :param highlight_color: color for feature selection, hover, or highlight
        """
        super(ChoroplethViz, self).__init__(data, *args, **kwargs)
        
        self.template = 'choropleth'
        self.check_vector_template()

        self.color_property = color_property
        self.color_stops = color_stops
        self.color_default = color_default
        self.color_function_type = color_function_type
        self.line_color = line_color
        self.line_stroke = line_stroke
        self.line_width = line_width
        self.height_property = height_property
        self.height_stops = height_stops
        self.height_default = height_default
        self.height_function_type = height_function_type
        self.legend_key_shape = legend_key_shape
        self.highlight_color = highlight_color

    def add_unique_template_variables(self, options):
        """Update map template variables specific to heatmap visual"""

        # set line stroke dash interval based on line_stroke property
        if self.line_stroke in ["dashed", "--"]:
            self.line_dash_array = [6, 4]
        elif self.line_stroke in ["dotted", ":"]:
            self.line_dash_array = [0.5, 4]
        elif self.line_stroke in ["dash dot", "-."]:
            self.line_dash_array = [6, 4, 0.5, 4]
        elif self.line_stroke in ["solid", "-"]:
            self.line_dash_array = [1, 0]
        else:
            # default to solid line
            self.line_dash_array = [1, 0]

        # check if choropleth map should include 3-D extrusion
        self.extrude = all([bool(self.height_property), bool(self.height_stops)])

        # common variables for vector and geojson-based choropleths
        options.update(dict(
            colorStops=self.color_stops,
            colorProperty=self.color_property,
            colorType=self.color_function_type,
            defaultColor=self.color_default,
            lineColor=self.line_color,
            lineDashArray=self.line_dash_array,
            lineStroke=self.line_stroke,
            lineWidth=self.line_width,
            extrudeChoropleth=self.extrude,
            highlightColor=self.highlight_color
        ))
        if self.extrude:
            options.update(dict(
                heightType=self.height_function_type,
                heightProperty=self.height_property,
                heightStops=self.height_stops,
                defaultHeight=self.height_default,
            ))

        # vector-based choropleth map variables
        if self.vector_source:
            options.update(vectorColorStops=self.generate_vector_color_map())
            
            if self.extrude:
                options.update(vectorHeightStops=self.generate_vector_numeric_map('height'))

        # geojson-based choropleth map variables
        else:
            options.update(geojson_data=json.dumps(self.data, ensure_ascii=False))


class ImageViz(MapViz):
    """Create a image viz"""

    def __init__(self,
                 image,
                 coordinates,
                 legend=False,
                 *args,
                 **kwargs):
        """Construct a Mapviz object

        :param coordinates: property to determine image coordinates (UL, UR, LR, LL).
            EX. [[-80.425, 46.437], [-71.516, 46.437], [-71.516, 37.936], [-80.425, 37.936]]
        :param image: url, local path or a numpy ndarray
        :param legend: default setting is to hide heatmap legend

        """
        super(ImageViz, self).__init__(None, *args, **kwargs)

        if type(image) is numpy.ndarray:
            image = img_encode(image)

        self.template = 'image'
        self.image = image
        self.coordinates = coordinates

    def add_unique_template_variables(self, options):
        """Update map template variables specific to image visual"""
        options.update(dict(
            image=self.image,
            coordinates=self.coordinates))


class RasterTilesViz(MapViz):
    """Create a rastertiles map"""

    def __init__(self,
                 tiles_url,
                 tiles_size=256,
                 tiles_bounds=None,
                 tiles_minzoom=0,
                 tiles_maxzoom=22,
                 legend=False,
                 *args,
                 **kwargs):
        """Construct a Mapviz object

        :param tiles_url: property to determine tiles url endpoint
        :param tiles_size: property to determine displayed tiles size
        :param tiles_bounds: property to determine the tiles endpoint bounds
        :param tiles_minzoom: property to determine the tiles endpoint min zoom
        :param tiles_max: property to determine the tiles endpoint max zoom
        :param legend: default setting is to hide heatmap legend

        """
        super(RasterTilesViz, self).__init__(None, *args, **kwargs)

        self.template = 'raster'
        self.tiles_url = tiles_url
        self.tiles_size = tiles_size
        self.tiles_bounds = tiles_bounds
        self.tiles_minzoom = tiles_minzoom
        self.tiles_maxzoom = tiles_maxzoom

    def add_unique_template_variables(self, options):
        """Update map template variables specific to a raster visual"""
        options.update(dict(
            tiles_url=self.tiles_url,
            tiles_size=self.tiles_size,
            tiles_minzoom=self.tiles_minzoom,
            tiles_maxzoom=self.tiles_maxzoom,
            tiles_bounds=self.tiles_bounds if self.tiles_bounds else 'undefined'))


class LinestringViz(MapViz):
    """Create a linestring viz"""

    def __init__(self,
                 data,
                 color_property=None,
                 color_stops=None,
                 color_default='grey',
                 color_function_type='interpolate',
                 line_stroke='solid',
                 line_width_property=None,
                 line_width_stops=None,
                 line_width_default=1,
                 line_width_function_type='interpolate',
                 legend_key_shape='line',
                 highlight_color='black',
                 *args,
                 **kwargs):
        """Construct a Mapviz object

        :param data: can be either GeoJSON (containing polygon features) or JSON for data-join technique with vector polygons
        :param vector_url: optional property to define vector linestring source
        :param vector_layer_name: property to define target layer of vector source
        :param vector_join_property: property to aid in determining color for styling vector lines
        :param data_join_property: property to join json data to vector features
        :param color_property: property to determine line color
        :param color_stops: property to determine line color
        :param color_default: property to determine default line color if match lookup fails
        :param color_function_type: property to determine `type` used by Mapbox to assign color
        :param line_stroke: property to determine line stroke (solid, dashed, dotted, dash dot)
        :param line_width_property: property to determine line width
        :param line_width_stops: property to determine line width
        :param line_width_default: property to determine default line width if match lookup fails
        :param line_width_function_type: property to determine `type` used by Mapbox to assign line width
        :param highlight_color: color for feature selection, hover, or highlight
        """
        super(LinestringViz, self).__init__(data, *args, **kwargs)
        
        self.template = 'linestring'
        self.check_vector_template()

        self.color_property = color_property
        self.color_stops = color_stops
        self.color_default = color_default
        self.color_function_type = color_function_type
        self.line_stroke = line_stroke
        self.line_width_property = line_width_property
        self.line_width_stops = line_width_stops
        self.line_width_default = line_width_default
        self.line_width_function_type = line_width_function_type
        self.legend_key_shape = legend_key_shape
        self.highlight_color = highlight_color

    def add_unique_template_variables(self, options):
        """Update map template variables specific to linestring visual"""

        # set line stroke dash interval based on line_stroke property
        if self.line_stroke in ["dashed", "--"]:
            self.line_dash_array = [6, 4]
        elif self.line_stroke in ["dotted", ":"]:
            self.line_dash_array = [0.5, 4]
        elif self.line_stroke in ["dash dot", "-."]:
            self.line_dash_array = [6, 4, 0.5, 4]
        elif self.line_stroke in ["solid", "-"]:
            self.line_dash_array = [1, 0]
        else:
            # default to solid line
            self.line_dash_array = [1, 0]

        # common variables for vector and geojson-based linestring maps
        options.update(dict(
            colorStops=self.color_stops,
            colorProperty=self.color_property,
            colorType=self.color_function_type,
            defaultColor=self.color_default,
            lineColor=self.color_default,
            lineDashArray=self.line_dash_array,
            lineStroke=self.line_stroke,
            widthStops=self.line_width_stops,
            widthProperty=self.line_width_property,
            widthType=self.line_width_function_type,
            defaultWidth=self.line_width_default,
            highlightColor=self.highlight_color
        ))

        # vector-based linestring map variables
        if self.vector_source:
            options.update(dict(
                vectorColorStops=[[0, self.color_default]],
                vectorWidthStops=[[0, self.line_width_default]],
            ))

            if self.color_property:
                options.update(vectorColorStops=self.generate_vector_color_map())
        
            if self.line_width_property:
                options.update(vectorWidthStops=self.generate_vector_numeric_map('line_width'))

        # geojson-based linestring map variables
        else:
            options.update(geojson_data=json.dumps(self.data, ensure_ascii=False))

