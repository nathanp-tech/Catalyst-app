from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.urls import reverse


class HomeView(TemplateView):
    """
    Displays the homepage for unauthenticated visitors.
    If a user is already logged in, they are redirected to their dashboard.
    """
    template_name = "core/home.html"

    def get(self, request, *args, **kwargs):
        # If the user is authenticated, redirect to their dashboard.
        if request.user.is_authenticated:
            return redirect(reverse('dashboard:dashboard'))
        
        # Otherwise, show the normal homepage for visitors.
        return super().get(request, *args, **kwargs)