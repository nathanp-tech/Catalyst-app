# documents/views.py

from django.views.generic.edit import CreateView
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.urls import reverse_lazy
from .models import Document
from .forms import DocumentForm

def is_teacher(user):
    """Vérifie si l'utilisateur est dans le groupe 'Professeurs'."""
    return user.groups.filter(name='Professeurs').exists()

class DocumentUploadView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Vue permettant aux professeurs d'uploader des documents PDF.
    L'accès est restreint au groupe 'Professeurs'.
    """
    model = Document
    form_class = DocumentForm
    template_name = 'documents/document_upload.html'
    success_url = reverse_lazy('dashboard:dashboard')  # Redirige vers le tableau de bord après succès

    def test_func(self):
        """Autorise l'accès uniquement aux professeurs."""
        return is_teacher(self.request.user)

    def form_valid(self, form):
        """Associe l'utilisateur actuel (le professeur) au document uploadé."""
        form.instance.uploaded_by = self.request.user
        return super().form_valid(form)