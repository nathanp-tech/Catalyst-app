# /dashboard/templatags/dashboard_extras.py

from django import template
import json

register = template.Library()

@register.filter(name='jsonify')
def jsonify(data):
    """
    Transforme un objet Python (comme un dictionnaire ou une liste)
    en une chaîne de caractères au format JSON, utilisable en toute sécurité dans le HTML/JS.
    """
    return json.dumps(data)