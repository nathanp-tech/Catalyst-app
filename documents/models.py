from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model


class Category(models.Model):
    """
    Represents a folder or category in the document tree.
    Can be nested to create a hierarchy (e.g., 11th Grade > NRPR).
    """
    name = models.CharField(max_length=100, verbose_name="Category Name")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name="Parent Category")
    order = models.PositiveIntegerField(default=0, verbose_name="Display Order")

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['order', 'name']
        # Ensures that category names are unique within the same parent
        unique_together = ('name', 'parent')

    def __str__(self):
        # Displays the full path, e.g., "11th Grade > NRPR"
        full_path = [self.name]
        p = self.parent
        while p is not None:
            full_path.append(p.name)
            p = p.parent
        return ' > '.join(full_path[::-1])


class Document(models.Model):
    """
    Represents a PDF file, which can be an exercise or a solution.
    """
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents', verbose_name="Category")
    title = models.CharField(max_length=255, verbose_name="Title")
    file = models.FileField(upload_to='documents/', verbose_name="File")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Upload Date")
    uploaded_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, verbose_name="Uploaded by")
    solution_for = models.OneToOneField('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='solution', verbose_name="Solution for exercise")

    def __str__(self):
        return self.title