# documents/views.py

from django.views.generic import TemplateView, View
from django.views.generic.edit import CreateView, UpdateView
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.db import models
from django.db.models.functions import Cast
from django.utils.decorators import method_decorator
from .models import Document, Category
from .forms import DocumentFileUpdateForm, DocumentForm

def is_teacher(user):
    """Checks if the user is in the 'Professeurs' group."""
    return user.groups.filter(name='Professeurs').exists()

class DocumentUploadView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Deprecated view, replaced by DocumentBrowseView and DocumentUpdateFileView.
    Keep or delete as needed.
    """
    model = Document
    form_class = DocumentForm
    template_name = 'documents/document_upload.html'
    success_url = reverse_lazy('dashboard:dashboard')  # Redirects to the dashboard on success

    def test_func(self):
        """Allows access only to teachers."""
        return is_teacher(self.request.user)
    
    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        return super().form_valid(form)

@method_decorator(user_passes_test(is_teacher), name='dispatch')
class DocumentClearFileView(LoginRequiredMixin, View):
    """
    Deletes the file associated with a document to allow a new upload.
    """
    def post(self, request, pk):
        doc = get_object_or_404(Document, pk=pk)
        
        # Delete the physical file from storage
        if doc.file:
            doc.file.delete(save=False) # Do not save the model right away

        doc.file = None
        doc.save()
        return redirect('documents:browse')

@method_decorator(user_passes_test(is_teacher), name='dispatch')
class DocumentBrowseView(LoginRequiredMixin, TemplateView):
    """Displays the category and document tree."""
    template_name = 'documents/document_browse.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # We sort documents by their title using a natural sort
        # by extracting the numeric part of the title.
        documents_sorted = Document.objects.annotate(
            numeric_part=Cast(models.functions.Substr('title', 3), models.IntegerField())
        ).order_by('numeric_part')
        
        context['categories'] = Category.objects.filter(parent__isnull=True).prefetch_related(models.Prefetch('children__children__documents', queryset=documents_sorted, to_attr='sorted_documents'), 'children__children__documents__solution').order_by('order', 'name')
        return context

class DocumentUpdateFileView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View to upload or replace the file of an existing document."""
    model = Document
    form_class = DocumentFileUpdateForm
    template_name = 'documents/document_update_file.html'
    success_url = reverse_lazy('documents:browse')

    def test_func(self):
        return is_teacher(self.request.user)

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        return super().form_valid(form)