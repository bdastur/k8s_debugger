#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
import jinja2

"""
Render Jinja2 templates.
"""



def renderJ2TemplateFile(templateFile, searchPath, **renderObj):
    """
    Render a jinja2 template.

    @params:
      templateFile: str - Name of the template file
      searchPath: str   - Path to the template directory
      renderObj: dict - Object to substitute the template variables.

    @returns:
      renderedData: str - Rendered string.
    """
    templateLoader = jinja2.FileSystemLoader(searchpath=searchPath)
    env = jinja2.Environment(
        loader=templateLoader, trim_blocks=True, lstrip_blocks=True)
    try:
        template = env.get_template(templateFile)
    except jinja2.exceptions.TemplateNotFound as err:
        print("Template %s/%s not found" % (searchPath, templateFile))
        return None

    renderedData = template.render(renderObj)

    return renderedData


def renderJ2TemplateString(templateString, **renderObj):
    """
    Render a templatized string 

    @params:
      templateString: str - A templated string (multiline)
      renderObj: dict - Object to substitute the template variables.

    @returns:
      renderedData: str - Rendered String.
    """
    env = jinja2.Environment(loader=jinja2.BaseLoader,
                             trim_blocks=True, lstrip_blocks=True)

    template = env.from_string(templateString)
    return template.render(renderObj)

