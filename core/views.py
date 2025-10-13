from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.urls import reverse


class HomeView(TemplateView):
    """
    Affiche la page d'accueil pour les visiteurs non connectés.
    Si un utilisateur est déjà connecté, il est redirigé vers son tableau de bord.
    """
    template_name = "core/home.html"

    def get(self, request, *args, **kwargs):
        # Si l'utilisateur est connecté, on le redirige vers son tableau de bord.
        if request.user.is_authenticated:
            return redirect(reverse('dashboard:dashboard'))
        
        # Sinon, on affiche la page d'accueil normale pour les visiteurs.
        return super().get(request, *args, **kwargs)