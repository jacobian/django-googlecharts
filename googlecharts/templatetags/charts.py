import sys
import inspect
import functools
import colorsys

from django import template
from django.conf import settings
from django.utils.datastructures import SortedDict
from django.utils.encoding import smart_str
from django.utils.html import escape
from django.utils.safestring import mark_safe, SafeData

register = template.Library()

# Set this to the color for the inactive areas of an interactive chart
_chart_inactive_color = 'eeeeee'
_chart_color = '336699'

#
# Helper functions
#
extended_separator = ","

def encode_text(values):
    return extended_separator.join(str(v) for v in values)

def num2chars(n, value_range):
    if n is not None:
        return _num2chars[norm(n, value_range)]
    else:
        return '__'

_encoding_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-."
_num2chars = [a+b for a in _encoding_chars for b in _encoding_chars]

def encode_extended(values, value_range):
    """Encode data using Google's "extended" encoding for the most granularity."""
    return "".join(num2chars(v, value_range) for v in values)

@register.simple_tag
def sparkline(data, size="100x30", color=_chart_color):
    maxvalue = max(data)
    minvalue = min(data)
    datarange = (minvalue, maxvalue)
    encoded_data = encode_extended(data,datarange)

    return '<img src="http://chart.apis.google.com/chart?\
cht=lc&\
chs=100x30&\
chd=e:%s&\
chco=%s&\
chls=1,1,0&\
chm=o,990000,0,%s,4&\
chxt=r,x,y&\
chxs=0,990000,11,0,_|1,990000,1,0,_|2,990000,1,0,_&\
chxl=0:|%s|1:||2:||&\
chxp=0,%s\
    " alt="" />' % (encoded_data, color, len(data), data[-1], 100*(float(data[-1])/(maxvalue-minvalue)))

#
# {% chart %}
#

@register.tag
def chart(parser, token):
    bits = iter(token.split_contents())
    name = bits.next()
    varname = None
    saveas = None
    extends = None
    for bit in bits:
        if bit == "as":
            varname = bits.next()
        elif bit == "saveas":
            raise template.TemplateSyntaxError("Sorry, 'saveas' isn't implemented yet!")
            saveas = template.Variable(bits.next())
        elif bit == "extends":
            extends = template.Variable(bits.next())
        else:
            raise template.TemplateSyntaxError("Unknown argument to '%s': '%s'" % (name, bit))
    nodelist = parser.parse("end%s" % name)
    parser.delete_first_token()
    return ChartNode(nodelist, varname, saveas, extends)

class ChartNode(template.Node):

    def __init__(self, nodelist, varname, saveas, extends):
        self.nodelist = nodelist
        self.saveas = saveas
        self.varname = varname
        self.extends = extends

    def render(self, context):
        c = Chart()
        if self.extends:
            try:
                parent = self.extends.resolve(context)
            except template.VariableDoesNotExist:
                pass
            else:
                c = parent.clone()
                
        for node in self.nodelist:
            if isinstance(node, ChartDataNode):
                c.datasets.extend(node.resolve(context))
            elif isinstance(node, ChartOptionNode):
                node.update_chart(c, context)
            elif isinstance(node, AxisNode):
                c.axes.append(node.resolve(context))
        
        # Take any options that begin with '_' and add them to the context,
        # omitting the underscore.
        for o in c.options:
            if o.startswith('_'):
                context[o[1:]] = c.options[o]
        
        # Create some additional images showing only one of the colors,
        # replacing the others with grayed-out images
        if '_final_color_map' in c.options:
            for o in c.options['_final_color_map'].items():
                context["chart_%s_only" % o[1]] = c.img(color_override=o[0])

        if self.varname:
            context[self.varname] = c
            return ""
        else:
            return c.img()

class Chart(object):

    BASE = "http://chart.apis.google.com/chart"
    defaults = {
        "chs": "200x200",
        "cht": "lc"
    }

    def __init__(self):
        # Use a SortedDict for the options so they are added in a
        # deterministic manner; this eases things like dealing with cache keys 
        # or writing unit tests.
        self.options = SortedDict()
        self.datasets = []
        self.axes = []
        self.datarange = None
        self.alt = None

    def clone(self):
        clone = self.__class__()
        clone.options = self.options.copy()
        clone.datasets = self.datasets[:]
        clone.axes = self.axes[:]
        return clone

    def img(self, color_override = None):
        orig_colors = self.options.get('chco')
        # If color_override is set, replace the chco option with this color
        if color_override is not None:
            final_color = []
            for c in self.options['chco'].split(','):
                if c == color_override:
                    c = orig_colors.split(',')[0]
                else:
                    c = _chart_inactive_color
                final_color.append(c)
            self.options['chco'] = ','.join(final_color)
        url = self.url()
        if orig_colors:
            self.options['chco'] = orig_colors
        width, height = self.options["chs"].split("x")
        if self.alt:
            alt = '%s' % escape(self.alt)
        else:
            alt = ''
        s = mark_safe('<img src="%s" width="%s" height="%s" alt="%s" />' % (escape(url), width, height, alt))

        return s

    def url(self):
        if self.options.get('cht', None) == 't':
            self.datasets.append(self.options.pop("_mapdata"))

        # Figure out the chart's data range
        if not self.datarange:
            maxvalue = max(max(d) for d in self.datasets if d)
            minvalue = min(min(d) for d in self.datasets if d)
            self.datarange = (minvalue, maxvalue)
        
        # Encode data
        if "chds" in self.options or self.options.get('cht', None) == 'gom': 
            # text encoding if scaling provided, or for google-o-meter type
            data = "|".join(encode_text(d) for d in self.datasets)
            encoded_data = "t:%s" % data
        else: 
            # extended encoding otherwise
            data = extended_separator.join(encode_extended(d, self.datarange) for d in self.datasets)
            encoded_data = "e:%s" % data
        
        # Update defaults
        for k in self.defaults:
            if k not in self.options:
                self.options[k] = self.defaults[k]
        
        # Start to calculate the URL
        url = "%s?%s&chd=%s" % (self.BASE, urlencode(self.options), encoded_data)
        
        # Calculate axis options
        if self.axes:
            axis_options = SortedDict()
            axis_sides = []
            for i, axis in enumerate(self.axes):
                axis_sides.append(axis.side)
                for opt in axis.options:
                    try:
                        axis_options.setdefault(opt, []).append(axis.options[opt] % i)
                    except TypeError:
                        pass
        
            # Turn the option lists into strings
            axis_sides = smart_join(",", *axis_sides)
            for opt in axis_options:
                axis_options[opt] = smart_join("|", *axis_options[opt])
            
            url += "&chxt=%s&%s" % (axis_sides, urlencode(axis_options))
            
        return url


    def charts(self):
        res = []
        count = 1
        for o in self.options['_final_color_map'].items():
            res.append({  'id': count,
                          'color': o[0],
                          'label': o[1],
                          'img': self.img(color_override=o[0])
                       })
            count += 1
        return res
        
#
# {% chart-data %} and {% chart-grid-lines-data %}
#

@register.tag(name="chart-data")
def chart_data(parser, token):
    bits = iter(token.split_contents())
    name = bits.next()
    datasets = map(parser.compile_filter, bits)
    return ChartDataNode(datasets, "chart-data")


@register.tag("chart-grid-lines-data")
def chart_grid_lines_data(parser, token):
    """
    An alternative method for providing data, intended to allow
    for the creation of fake line series that will simulate a 
    grid-line drawn *on top* of the other data series. 
    
    Unfortunately, this is necessary because the tick marks and
    range markets supported by the API do not--as far I can tell--
    allow for the guides to be drawn on top of the data. 
    """
    bits = iter(token.split_contents())
    name = bits.next()
    data_obj = map(parser.compile_filter, bits)
    return ChartDataNode(data_obj, "chart-grid-lines-data")


class ChartDataNode(template.Node):
    def __init__(self, datasets, type):
        self.datasets = datasets
        self.type = type
        
    def resolve(self, context):
        resolved = []
        
        # If the data is provided by the {% chart-data %} tag ...
        if self.type == 'chart-data':
            for data in self.datasets:
                try:
                    data = data.resolve(context)
                except template.VariableDoesNotExist:
                    data = []
            
                # XXX need different ways of representing pre-encoded data, data with
                # different separators, etc.
                if isinstance(data, basestring):
                    data = filter(None, map(safefloat, data.split(",")))
                else:
                    # I don't understand why you would remove zero values, as this does?
                    # I'm going to comment it out and use my own version
                    # data = filter(None, map(safefloat, data))
                    data = map(safefloat, data)
                resolved.append(data)
        
        # If the data is provided by the {% chart-grid-lines-data %} tag ...
        elif self.type == 'chart-grid-lines-data':
            for data in self.datasets:
                data = data.resolve(context)
                
                # Since this variable can contain multiple lists,
                # We'll add an extra loop that doesn't exist above.
                for series in data:
                    
                    # Split the tuple
                    value_count, value = series
                    # Extend the series to the length of the count
                    series = [value] * value_count
                    
                    # Conduct the same filtering as above
                    if isinstance(data, basestring):
                        series = filter(None, map(safefloat, series.split(",")))
                    else:
                        series = map(safefloat, series)
                    
                    # And if there's anything there ...
                    if series:
                        # Add it to the final set
                        resolved.append(series)
                

        return resolved
        
    def render(self, context):
        return ""

#
# Chart options
#

class OptionNode(template.Node):
    def __init__(self, callback, args, multi=None):
        self.callback = callback
        self.args = args
        self.multi = multi

    def render(self, context):
        return ""

    def resolve_arguments(self, context):
        for arg in self.args:
            try:
                yield arg.resolve(context)
            except template.VariableDoesNotExist:
                yield None

    def update_options(self, options, context):
        data = self.callback(*self.resolve_arguments(context))
        if self.multi:
            for key in data:
                if key in options:
                    options[key] = options[key] + self.multi + data[key]
                else:
                    options[key] = data[key]
        else:
            options.update(data)

class ChartOptionNode(OptionNode):
    def update_chart(self, chart, context):
        self.update_options(chart.options, context)
    
class AxisOptionNode(OptionNode):
    pass

def option(tagname, multi=None, nodeclass=ChartOptionNode):
    """
    Decorator-helper to register a chart-foo option tag. The decorated function
    will be called at resolution time with the proper arity (determined from
    inspecting the decorated function). This callback should return a dictionary
    which will be used as arguments in the chart URL.
    """
    def decorator(func):
        # Figure out how to validate the args to the tag
        args, varargs, varkw, defaults = inspect.getargspec(func)
        max_args = min_args = 0
        if args:
            max_args = len(args)
        if defaults:
            min_args = max_args - len(defaults)
        unlimited = bool(varargs)
        
        def template_tag_callback(parser, token):
            bits = iter(token.split_contents())
            name = bits.next()
            args = map(template.Variable, bits)
            
            if not unlimited and len(args) < min_args:
                raise template.TemplateSyntaxError("Too few arguments to '%s'" % name)
            if not unlimited and len(args) > max_args:
                raise template.TemplateSyntaxError("Too many arguments to '%s'" % name)
            
            return nodeclass(func, args, multi)
        template_tag_callback.__name__ = func.__name__
        template_tag_callback.__doc__ = func.__doc__        
        register.tag(tagname, template_tag_callback)
        return func
        
    return decorator

@option("chart-type")
def chart_type(arg):
    """
    Set the chart type. Valid arguments are anything the chart API understands,
    or the following human-readable alternates:
        
        * 'line'
        * 'xy'
        * 'xy' / 'line-xy'
        * 'bar' / 'bar-grouped'
        * 'column' / 'column-grouped'
        * 'bar-stacked'
        * 'column-stacked'
        * 'pie'
        * 'pie-3d'
        * 'venn'
        * 'scatter'
        * 'map'
        
    """
    types = {
        'line':             'lc',
        'sparkline':        'ls',
        'xy':               'lxy',
        'line-xy':          'lxy',
        'bar':              'bhg',
        'column':           'bvg',
        'bar-stacked':      'bhs',
        'column-stacked':   'bvs',
        'bar-grouped':      'bhg',
        'column-grouped':   'bvg',
        'pie':              'p',
        'pie-3d':           'p3',
        'venn':             'v',
        'scatter':          's',
        'google-o-meter':   'gom',
        'map':              't',
    }
    return {"cht": types.get(arg, arg)}

@option("chart-data-scale", multi=",")
def chart_data_scale(*args):
    return {"chds": smart_join(",", *args)}

@option("chart-colors", multi=",")
def chart_colors(*args):
    return {"chco": smart_join(",", *args)}

@option("chart-bar-colors", multi="|")
def chart_bar_colors(*args):
    return {"chco": smart_join("|", *args)}
    
@option("chart-auto-colors")
def chart_auto_colors(color, item_label_list):
    '''Takes a starting color and a list of labels and creates the correct number of
    colors, storing the correspondance between the labels and colors for later use
    in the context.'''

    # Convert to RGB values between 0 and 1
    _r = float(int(color[0:2], 16)) / 255
    _g = float(int(color[2:4], 16)) / 255
    _b = float(int(color[4:6], 16)) / 255
    
    # Switch to HSV color space
    hsv = colorsys.rgb_to_hsv(_r, _g, _b)

    colors = []

    # For each label, compute a new color
    for index, color in enumerate(range(0, len(item_label_list))):

        if index == 0:
            # this is the first value, make it 100%
            s_value = hsv[1]
            v_value = hsv[2]
        elif index == len(item_label_list) - 1:
            #this is the last value, make it 20%
            s_value = hsv[1] * .2
            v_value = hsv[2] * 1.8
        else:
            # otherwise, do a calculation
            s_value = hsv[1] * (.8/(len(item_label_list)-1))
            v_value = hsv[2] * (1 + (.8/(len(item_label_list)-1)))

        if s_value >= 1:
            s_value = hsv[1]
        if v_value >= 1:
            v_value = hsv[2]

        # Convert back to rgb
        c_list = colorsys.hsv_to_rgb(hsv[0], s_value, v_value)


        # Turn a list of rgb values from 0 to 1 back to a value from 0 to 255,
        # and then to hex
        c_converted = ([ str(hex(int(c * 255)))[2:] for c in c_list])

        c_final = []

        # Zero-pad the hex numbers
        for c in c_converted:
            try:
                c = "%02d" % int(c)
            except ValueError, e:
                # Ignore, this is a hex letter (e.g. 'ff')
                pass
            c_final.append(c)
        colors.append(''.join(c_final))

    final_color_map = SortedDict()

    # Map our final color values to the label that will be associated with them
    for index, c in enumerate(colors):
        final_color_map[c] = item_label_list[index]

    # Values which begin with an underscore won't be passed on to Google but will
    # end up in the request context.
    return {"chco": ','.join(colors),
            '_final_color_map': final_color_map}

@option("chart-size")
def chart_size(arg1, arg2=None):
    if arg2:
        return {"chs": smart_join("x", arg1, arg2)}
    else:
        return {"chs": arg1}

@option("chart-background", multi="|")
def chart_background(color):
    return _solid("bg", color)

@option("chart-fill", multi="|")
def chart_fill(color):
    return _solid("c", color)
    
def _solid(type, color):
    return {"chf": "%s,s,%s" % (type, color)}

@option("chart-background-gradient", multi="|")
def chart_background_gradient(angle, *colors):
    return _fancy_background("bg", "lg", angle, colors)
    
@option("chart-fill-gradient", multi="|")
def chart_fill_gradient(angle, *colors):
    return _fancy_background("c", "lg", angle, colors)

@option("chart-background-stripes", multi="|")
def chart_background_stripes(angle, *colors):
    return _fancy_background("bg", "ls", angle, colors)
    
@option("chart-fill-stripes", multi="|")
def chart_fill_stripes(angle, *colors):
    return _fancy_background("c", "ls", angle, colors)
    
def _fancy_background(bgtype, fancytype, angle, colors):
    return {"chf": smart_join(",", bgtype, fancytype, angle, *colors)}

@option("chart-title")
def chart_title(title, fontsize=None, color="000000"):
    title = title.replace("\n", "|")
    if fontsize:
        return {"chtt":title, "chts":"%s,%s" % (color, fontsize)}
    else:
        return {"chtt": title}

@option("chart-legend", multi="|")
def chart_legend(*labels):
    return {"chdl": smart_join("|", *flatten(labels))}

@option("chart-pie-orientation")
def chart_pie_orientation(radians):
    return {"chp": radians}

@option("chart-labels", multi="|")
def chart_labels(*labels):
    return {"chl": smart_join("|", *flatten(labels))}

@option("chart-bar-width")
def chart_bar_width(width, barspace=None, groupspace=None):
    return {"chbh": smart_join(",", width, barspace, groupspace)}

@option("chart-line-style", multi="|")
def chart_line_style(thickness, line_length=None, space_length=None):
    return {"chls": smart_join(",", thickness, line_length, space_length)}

@option("chart-grid")
def chart_grid(xstep, ystep, line_length=None, space_length=None):
    return {"chg": smart_join(",", xstep, ystep, line_length, space_length)}

rangetypes = {
    "h": "r",
    "horiz": "r",
    "horizontal": "r",
    "v": "R",
    "vert": "R",
    "vertical": "R",
}

@option("chart-range-marker", multi="|")
def chart_range_marker(range_type, color, start, end):
    rt = rangetypes.get(range_type, range_type)
    return {"chm": smart_join(",", rt, color, "0", start, end)}

@option("chart-fill-area", multi="|")
def chart_fill_area(color, startindex=0, endindex=0):
    if startindex or endindex:
        filltype = "b"
    else:
        filltype = "B"
    return {"chm": smart_join(",", filltype, color, startindex, endindex, "0")}

marker_types = {
    'arrow': 'a',
    'cross': 'c',
    'diamond': 'd',
    'circle': 'o',
    'square': 's',
    'line': 'v',
    'full-line': 'V',
    'h-line': 'h',
    'horiz-line': 'h',
    'horizontal-line': 'h',
}

@option("chart-marker", multi="|")
def chart_marker(marker, color, dataset_index, data_point, size):
    marker = marker_types.get(marker, marker)
    return {"chm": smart_join(",", marker, color, dataset_index, data_point, size)}

@option("chart-grid-lines-style", multi="|")
def chart_grid_lines_style(iterable):
    """
    Set the style for fake grid lines.
    
    Provide an iterable yielding (color, dataset_index, size)
    """
    try:
        it = iter(iterable)
    except TypeError:
        return {}

    labels = []
    for m in it:
        try:
            color, dataset_index, size = m
        except ValueError:
            continue
        labels.append(smart_join(",", 'D', color, dataset_index, 0, size, 1))
    if labels:
        return {"chm": smart_join("|", *flatten(labels))}
    else:
        return {}

@option("chart-markers", multi="|")
def chart_markers(dataset_index, iterable):
    """
    Provide an iterable yielding (type, color, point, size)
    """
    try:
        it = iter(iterable)
    except TypeError:
        return {}

    markers = []
    for m in it:
        try:
            marker, color, data_point, size = m
        except ValueError:
            continue
        marker = marker_types.get(marker, marker)
        markers.append(smart_join(",", marker, color, dataset_index, data_point, size))

    return {"chm": smart_join("|", *flatten(markers))}


label_types = {
    'flag': 'f',
    'text': 't',
    'number': 'N',
}

@option("data-point-labels", multi="|")
def data_point_labels(dataset_index, iterable):
    """
    Adds data labels as described here: http://code.google.com/apis/chart/labels.html#data_point_labels

    You will need to provide an iterable yielding (label_type, label_contents, color, data_point, size, priority)

    And keep in mind that flags and text labels require a very different `label_contents` than a set of numbers.
    """
    try:
        it = iter(iterable)
    except TypeError:
        return {}

    labels = []
    for m in it:
        try:
            label_type, label_contents, color, data_point, size, priority = m
        except ValueError:
            continue
        label = label_types.get(label_type, label_type)
        labels.append(smart_join(",", label + label_contents, color, dataset_index, data_point, size, priority))
    return {"chm": smart_join("|", *flatten(labels))}

@option("chart-map-area")
def chart_map_area(where):
    return {'chtm': where}
    
@option("chart-map-data")
def chart_map_data(data):
    place_list = []
    value_list = []
    for (k, v) in data.items():
        place_list.append(k)
        value_list.append(v)
    return {
        "chld": smart_join("", *place_list),
        "_mapdata": value_list
    }

#
# {% axis %}
#
@register.tag
def axis(parser, token):
    bits = token.split_contents()

    if len(bits) == 2:
        # {% axis <side> %} ... {% endaxis %}
        name, side = bits
        nodelist = parser.parse("end%s" % name)
        parser.delete_first_token()
        return AxisNode(template.Variable(side), nodelist)

    elif len(bits) == 3:
        # {% axis <side> hide %}
        name, side = bits[0:2]
        if bits[2].lower() != "hide":
            raise template.TemplateSyntaxError("%s tag expected 'hide' as last argument" % name)
        return NoAxisNode(template.Variable(side))
    
    else:
        raise template.TemplateSyntaxError("axis tag takes one or two arguments")

class AxisNode(template.Node):
    
    sides = {
        'left': 'y',
        'right': 'r',
        'top': 't',
        'bottom': 'x',
    }
    
    def __init__(self, side, nodelist=None):
        self.side = side
        self.nodelist = nodelist
        
    def render(self, context):
        return ''
        
    def resolve(self, context):
        axis = self.get_axis(context)
        for node in self.nodelist:
            if isinstance(node, AxisOptionNode):
                node.update_options(axis.options, context)
                
        return axis
        
    def get_axis(self, context):
        try:
            side = self.side.resolve(context)
        except template.VariableDoesNotExist:
            return None
        side = self.sides.get(side, side)
        return Axis(side)
        
class NoAxisNode(AxisNode):
    def resolve(self, context):
        a = self.get_axis(context)
        a.options["chxs"] = "%s,000000,11,0,_"
        a.options["chxl"] = "%s:||"
        return a
        
class Axis(object):
    def __init__(self, side):
        self.side = side
        self.options = SortedDict()
        
# Axis options use %s placeholders for the axis index; this gets
# filled in by Chart.url()

@option("axis-labels", nodeclass=AxisOptionNode)
def axis_labels(*labels):
    return {"chxl": "%s:|" + smart_join("|", *flatten(labels))}
    
@option("axis-label-positions", nodeclass=AxisOptionNode)
def axis_label_position(*positions):
    return {"chxp": smart_join(",", "%s", *flatten(positions))}
    
@option("axis-range", nodeclass=AxisOptionNode)
def axis_range(start, end):
    return {"chxr": "%%s,%s,%s" % (start, end)}

alignments = {
    'left': -1,
    'right': 1,
    'center': 0,
}

@option("axis-style", nodeclass=AxisOptionNode)
def axis_style(color, font_size=None, alignment=None):
    alignment = alignments.get(alignment, alignment)
    return {"chxs": smart_join(",", "%s", color, font_size, alignment)}

@option("axis-tick-length", nodeclass=AxisOptionNode)
def axis_range(length):
    return {"chxtc": "%%s,%s" % (length)}


#
# "Metadata" nodes
#
class MetadataNode(ChartOptionNode):
    def update_chart(self, chart, context):
        self.callback(chart, *self.resolve_arguments(context))
        
@option("chart-data-range", nodeclass=MetadataNode)
def chart_data_range(chart, lower=None, upper=None):
    if lower and upper:
        try:
            map(float, (lower, upper))
        except ValueError:
            return
        chart.datarange = (lower, upper)
    elif lower == "auto":
        chart.datarange = None

@option("chart-alt", nodeclass=MetadataNode)
def chart_alt(chart, alt=None):
    chart.alt = alt
    
@option("chart-grid-lines", nodeclass=MetadataNode)
def chart_grid_lines(chart):
    """
    Indicates that you intended to provide fake grid line data.
    """
    chart.grid_lines = True

#
# Helper functions
#
extended_separator = ","

def encode_text(values):
    return extended_separator.join(str(v) for v in values)

def encode_extended(values, value_range):
    """Encode data using Google's "extended" encoding for the most granularity."""
    return "".join(num2chars(v, value_range) for v in values)

_encoding_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-."
_num2chars = [a+b for a in _encoding_chars for b in _encoding_chars]

def num2chars(n, value_range):
    if n is not None:
        return _num2chars[norm(n, value_range)]
    else:
        return '__'
    
def norm(n, value_range):
    minvalue, maxvalue = value_range
    if minvalue >= 0:
        return int(round(float(n) / maxvalue * 4095, 0))
    elif maxvalue <= 0:
        return 4095 - int(round(float(n) * 4095 / minvalue))
    else:
        return int(round((n - minvalue) * (float(4095) / (maxvalue - minvalue))))

def safefloat(n):
    try:
        return float(n)
    except (TypeError, ValueError):
        return None
        
def smart_join(sep, *args):
    return sep.join(smart_str(s, errors="ignore") for s in args if s is not None)
    
# I'm annoyed with the fact the urllib.urlencode doesn't allow specifying
# "safe" characters -- specifically ":", ",", and "|" since those characters
# make reading gchart URLs much easier.
from urllib import quote_plus

def urlencode(query, safe="/:,|"):
    '''Omit any options that begin with _; for internal use'''
    q = functools.partial(quote_plus, safe=safe)
    query = query.items() if hasattr(query, "items") else query
    qlist = ["%s=%s" % (q(k), q(v)) for (k,v) in query if not k.startswith('_')]
    return "&".join(qlist)
    
def flatten(iterator):
    for i in iterator:
        if hasattr(i, "__iter__"):
            for j in flatten(iter(i)):
                yield j
        else:
            yield i