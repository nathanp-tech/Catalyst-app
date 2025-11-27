# dashboard/models.py
from django.db import models
from django.contrib.auth.models import Group

class GroupConfiguration(models.Model):
    """
    Stores a configuration of student groups for a given class.
    """
    teacher_class = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='group_configurations')
    name = models.CharField(max_length=255, help_text="E.g., Groups for the 'Volcanoes' project")
    configuration = models.JSONField(help_text="The group structure, e.g., [['Alice', 'Bob'], ['Charlie']]")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Configuration '{self.name}' for class {self.teacher_class.name}"