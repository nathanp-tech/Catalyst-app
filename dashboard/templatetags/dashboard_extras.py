from django import template
import json
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='multiply')
def multiply(value, arg):
    """Multiplie la valeur par l'argument."""
    try:
        return value * arg
    except (ValueError, TypeError):
        # En cas d'erreur, ne rien retourner pour ne pas casser le template
        return ''

@register.filter(name='div')
def div(value, arg):
    """Divise la valeur par l'argument."""
    try:
        return int(value) / int(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return None

@register.filter(name='jsonify')
def jsonify(data):
    """Convertit un objet Python en chaîne JSON sécurisée pour HTML."""
    return mark_safe(json.dumps(data))