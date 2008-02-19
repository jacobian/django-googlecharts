#!/usr/bin/env python
"""
Render the examples into HTML, making a sort of documentation.
"""

from django.conf import settings
settings.configure(INSTALLED_APPS=["googlecharts"])

from math import sin
from django import template
from docutils.core import publish_parts
from lxml import etree
from unipath import FSPath as Path

def render_examples():
    data = {
        'data1' : [10, 20, 30],
        'data2' : [i**2 for i in range(20)],
        'data3' : [i**2 for i in range(20, 0, -1)],
        'data4' : [sin(i/5.0)*5 for i in range(100)],
        'venn' : [100, 80, 60, 30, 30, 30, 10],
    }
    examples = []
    source = Path(__file__).parent.child("examples.txt").read_file()
    published = publish_parts(source, writer_name="xml", settings_overrides={"xml_declaration": False})
    tree = etree.fromstring(published["whole"])
    for section in tree.xpath("//section"):
        title = section.find("title").text
        chart = section.find("literal_block").text
        t = template.Template("{% load charts %}" + chart)
        rendered = t.render(template.Context(data))
        examples.append({
            "title" : title,
            "template": chart,
            "image": rendered,
        })
    t = template.Template(EXAMPLE_TEMPLATE)
    return t.render(template.Context({"examples": examples, "data": data}))

EXAMPLE_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
  <title>Google Charts!</title>
  <style type="text/css" media="screen">
    th { font-size: 18px; text-align: left; border-top: 1px #ccc solid; padding-top: 4px; }
    table { margin-left: auto; margin-right: auto; }
  </style>
</head>
<body>
  <h2>Chart tag examples</h2>
  <table>
    <tbody>
      {% for example in examples %}
        <tr>
          <th colspan="2">{{ example.title }}</th>
        <tr>
          <td><pre>{{ example.template }}</pre></td>
          <td>{{ example.image|safe }}</td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""

if __name__ == '__main__':
    print render_examples()