# documents/urls.py

from django.urls import path
from .views import DocumentBrowseView, DocumentUpdateFileView

app_name = 'documents'

urlpatterns = [
    path('browse/', DocumentBrowseView.as_view(), name='browse'),
    path('<int:pk>/upload/', DocumentUpdateFileView.as_view(), name='update-file'),
]