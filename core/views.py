from django.views.generic import TemplateView, UpdateView
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import AppConfig


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

class SettingsView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = AppConfig
    fields = ['active_model']
    template_name = "core/settings.html"
    success_url = reverse_lazy('settings')

    def test_func(self):
        return self.request.user.is_staff

    def get_object(self, queryset=None):
        obj, _ = AppConfig.objects.get_or_create(pk=1)
        return obj