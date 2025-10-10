from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.filter(name='div')
def div(value, arg):
    """
    Divides the value by the argument.
    """
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return None

@register.filter(name='jsonify')
def jsonify(obj):
    return mark_safe(json.dumps(obj))