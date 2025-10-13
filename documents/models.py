from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model


class Category(models.Model):
    """
    Représente un dossier ou une catégorie dans l'arborescence des documents.
    Peut être imbriqué pour créer une hiérarchie (ex: 11ème > NRPR).
    """
    name = models.CharField(max_length=100, verbose_name="Nom de la catégorie")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name="Catégorie parente")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ['order', 'name']
        # Assure que les noms de catégories sont uniques au sein d'un même parent
        unique_together = ('name', 'parent')

    def __str__(self):
        # Affiche le chemin complet, ex: "11ème > NRPR"
        full_path = [self.name]
        p = self.parent
        while p is not None:
            full_path.append(p.name)
            p = p.parent
        return ' > '.join(full_path[::-1])


class Document(models.Model):
    """
    Représente un fichier PDF, qui peut être un exercice ou un corrigé.
    """
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents', verbose_name="Catégorie")
    title = models.CharField(max_length=255, verbose_name="Titre")
    file = models.FileField(upload_to='documents/', verbose_name="Fichier")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'envoi")
    uploaded_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, verbose_name="Envoyé par")
    solution_for = models.OneToOneField('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='solution', verbose_name="Corrigé de l'exercice")

    def __str__(self):
        return self.title