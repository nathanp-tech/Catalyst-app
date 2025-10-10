# dashboard/models.py
from django.db import models
from django.contrib.auth.models import Group

class GroupConfiguration(models.Model):
    """
    Stocke une configuration de groupes d'élèves pour une classe donnée.
    """
    teacher_class = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='group_configurations')
    name = models.CharField(max_length=255, help_text="Ex: Groupes pour le projet 'Volcans'")
    configuration = models.JSONField(help_text="La structure des groupes, ex: [['Alice', 'Bob'], ['Charlie']]")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Configuration '{self.name}' pour la classe {self.teacher_class.name}"