# documents/forms.py

from django import forms
from django.core.exceptions import ValidationError
from .models import Document

# Limite de taille de fichier à 10 Mo
MAX_FILE_SIZE = 10 * 1024 * 1024 

class DocumentForm(forms.ModelForm):
    """
    Formulaire pour l'upload de documents avec validation personnalisée.
    """
    class Meta:
        model = Document
        fields = ['title', 'file']
        labels = {
            'title': 'Titre du document',
            'file': 'Fichier (PDF uniquement, 10Mo max)',
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ex: Contrôle de géométrie'}),
            'file': forms.FileInput(attrs={'class': 'file-input'}),
        }

    def clean_file(self):
        """
        Valide le fichier uploadé.
        - Vérifie que c'est bien un PDF.
        - Vérifie que la taille ne dépasse pas la limite.
        """
        file = self.cleaned_data.get('file', False)
        if not file:
            raise ValidationError("Aucun fichier sélectionné.")
        
        # Valider l'extension
        if not file.name.endswith('.pdf'):
            raise ValidationError("Le fichier doit être au format PDF.")
        
        # Valider la taille
        if file.size > MAX_FILE_SIZE:
            raise ValidationError(f"La taille du fichier ne doit pas dépasser {int(MAX_FILE_SIZE / 1024 / 1024)}Mo.")
            
        return file