from django.views.generic import TemplateView


class HomeView(TemplateView):
    """Vue pour afficher la page d'accueil."""
    template_name = "core/home.html"