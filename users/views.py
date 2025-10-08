from django.shortcuts import redirect
from django.contrib.auth import login
from django.urls import reverse_lazy
from django.contrib.auth.models import Group
from django.views.generic import CreateView

from .forms import CustomUserCreationForm


class SignUpView(CreateView):
    """
    Vue pour l'inscription de nouveaux utilisateurs.
    """
    form_class = CustomUserCreationForm
    template_name = "users/signup.html"
    success_url = reverse_lazy("dashboard:dashboard")  # Rediriger vers le tableau de bord après inscription

    def form_valid(self, form):
        """
        Si le formulaire est valide, enregistre l'utilisateur,
        l'assigne au groupe 'Eleves', le connecte, puis redirige.
        """
        response = super().form_valid(form)
        students_group, created = Group.objects.get_or_create(name='Eleves')
        self.object.groups.add(students_group)
        login(self.request, self.object)
        return response
