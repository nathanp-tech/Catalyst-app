# dashboard/models.py
from django.db import models
from django.contrib.auth.models import Group, User

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

class SurveyResponse(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='survey_responses')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Dimension 1 : Utilité perçue
    utility_errors = models.IntegerField(verbose_name="Aide erreurs", default=3)
    utility_hints = models.IntegerField(verbose_name="Indices utiles", default=3)
    utility_correction = models.IntegerField(verbose_name="Correction autonome", default=3)
    utility_understanding = models.IntegerField(verbose_name="Compréhension chapitre", default=3)

    # Dimension 2 : Facilité d'usage
    ease_asking = models.IntegerField(verbose_name="Facilité questions", default=3)
    ease_knowing = models.IntegerField(verbose_name="Savoir quoi demander", default=3)
    ease_understanding = models.IntegerField(verbose_name="Compréhension par l'IA", default=3)
    ease_reformulation = models.IntegerField(verbose_name="Reformulation nécessaire", default=3)

    # Dimension 3 : Sentiment de compétence
    competence_capability = models.IntegerField(verbose_name="Capacité résolution", default=3)
    competence_confidence = models.IntegerField(verbose_name="Confiance en soi", default=3)
    competence_preference = models.IntegerField(verbose_name="Préférence IA", default=3)
    competence_new_ways = models.IntegerField(verbose_name="Nouvelles façons de penser", default=3)

    # Dimension 4 : Relation et posture
    relation_tutor = models.IntegerField(verbose_name="Posture tuteur", default=3)
    relation_trust = models.IntegerField(verbose_name="Confiance conseils", default=3)
    relation_interest = models.IntegerField(verbose_name="Intérêt cours", default=3)

    # Questions ouvertes
    open_difficulty = models.TextField(blank=True, null=True, verbose_name="Difficulté du prompting")
    open_confusion = models.TextField(blank=True, null=True, verbose_name="Moments de confusion")

    def __str__(self):
        return f"Réponse de {self.student.username} - {self.created_at.strftime('%d/%m/%Y')}"