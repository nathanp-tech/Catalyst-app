# documents/forms.py

from django import forms
from django.core.exceptions import ValidationError
from .models import Document

# File size limit to 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024 

class DocumentForm(forms.ModelForm):
    """
    Form for uploading documents with custom validation.
    """
    class Meta:
        model = Document
        fields = ['title', 'file']
        labels = {
            'title': 'Document Title',
            'file': 'File (PDF only, 10MB max)',
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'E.g., Geometry Test'}),
            'file': forms.FileInput(attrs={'class': 'file-input'}),
        }

    def clean_file(self):
        """
        Validates the uploaded file.
        - Checks that it is a PDF.
        - Checks that the size does not exceed the limit.
        """
        file = self.cleaned_data.get('file', False)
        if not file:
            raise ValidationError("No file selected.")
        
        # Validate the extension
        if not file.name.endswith('.pdf'):
            raise ValidationError("The file must be in PDF format.")
        
        # Validate the size
        if file.size > MAX_FILE_SIZE:
            raise ValidationError(f"The file size should not exceed {int(MAX_FILE_SIZE / 1024 / 1024)}MB.")
            
        return file


class DocumentFileUpdateForm(forms.ModelForm):
    """
    Simplified form to update only the file of a document.
    """
    class Meta:
        model = Document
        fields = ['file']
        labels = {
            'file': 'File (PDF only, 10MB max)',
        }
        widgets = {
            'file': forms.FileInput(attrs={'class': 'file-input'}),
        }

    def clean_file(self):
        file = self.cleaned_data.get('file', False)
        if not file:
            raise ValidationError("No file selected.")
        
        # Validate the extension
        if not file.name.endswith('.pdf'):
            raise ValidationError("The file must be in PDF format.")
        
        # Validate the size
        if file.size > MAX_FILE_SIZE:
            raise ValidationError(f"The file size should not exceed {int(MAX_FILE_SIZE / 1024 / 1024)}MB.")
            
        return file