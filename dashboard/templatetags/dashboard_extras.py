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

@register.filter(name='render_chat_message')
def render_chat_message(content):
    """
    Affiche correctement le contenu d'un message de chat, qui peut être
    une chaîne ou une liste de dictionnaires (pour les messages avec images).
    """
    from django.utils.html import format_html, escape

    if isinstance(content, list):
        html_parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get('type') == 'text':
                    text = escape(part.get('text', ''))
                    html_parts.append(f'<div class="comment-text">{text}</div>')
                elif part.get('type') == 'image_url':
                    # Gère les deux formats d'URL possibles
                    url = part.get('url') or (part.get('image_url', {})).get('url')
                    if url:
                        html_parts.append(f'<img src="{escape(url)}" alt="Réponse de l\'élève sur le tableau blanc" style="max-width: 100%; border-radius: 8px; margin-top: 10px;">')
        return mark_safe("".join(html_parts))
    elif isinstance(content, str):
        # Si c'est une chaîne simple (ancien format ou message de l'IA), on l'affiche.
        return mark_safe(escape(content).replace('\n', '<br>'))
    return ""