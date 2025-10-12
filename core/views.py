from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.urls import reverse


class HomeView(TemplateView):
    """Vue pour afficher la page d'accueil."""
    template_name = "core/home.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(reverse('dashboard:dashboard'))
        return super().get(request, *args, **kwargs)