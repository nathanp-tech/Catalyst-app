# documents/views.py

from django.views.generic import TemplateView
from django.views.generic.edit import CreateView, UpdateView
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse_lazy
from django.db import models
from django.db.models.functions import Cast
from django.utils.decorators import method_decorator
from .models import Document, Category
from .forms import DocumentFileUpdateForm, DocumentForm

def is_teacher(user):
    """Vérifie si l'utilisateur est dans le groupe 'Professeurs'."""
    return user.groups.filter(name='Professeurs').exists()

class DocumentUploadView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Vue dépréciée, remplacée par DocumentBrowseView et DocumentUpdateFileView.
    Conservez ou supprimez selon vos besoins.
    """
    model = Document
    form_class = DocumentForm
    template_name = 'documents/document_upload.html'
    success_url = reverse_lazy('dashboard:dashboard')  # Redirige vers le tableau de bord après succès

    def test_func(self):
        """Autorise l'accès uniquement aux professeurs."""
        return is_teacher(self.request.user)
    
    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        return super().form_valid(form)

@method_decorator(user_passes_test(is_teacher), name='dispatch')
class DocumentBrowseView(LoginRequiredMixin, TemplateView):
    """Affiche l'arborescence des catégories et des documents."""
    template_name = 'documents/document_browse.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # On trie les documents par leur titre en utilisant un tri naturel
        # en extrayant la partie numérique du titre.
        documents_sorted = Document.objects.annotate(
            numeric_part=Cast(models.functions.Substr('title', 3), models.IntegerField())
        ).order_by('numeric_part')
        
        context['categories'] = Category.objects.filter(parent__isnull=True).prefetch_related(models.Prefetch('children__children__documents', queryset=documents_sorted, to_attr='sorted_documents'), 'children__children__documents__solution').order_by('order', 'name')
        return context

class DocumentUpdateFileView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Vue pour uploader ou remplacer le fichier d'un document existant."""
    model = Document
    form_class = DocumentFileUpdateForm
    template_name = 'documents/document_update_file.html'
    success_url = reverse_lazy('documents:browse')

    def test_func(self):
        return is_teacher(self.request.user)

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        return super().form_valid(form)