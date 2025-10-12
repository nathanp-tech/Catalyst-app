# tutor/models.py

from django.db import models
from django.conf import settings

# Assurez-vous d'importer votre modèle Document
from documents.models import Document 

class ChatSession(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    question_context = models.TextField()
    solution_context = models.TextField()
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    summary_data = models.JSONField(null=True, blank=True, help_text="Résumé et analyse d'erreur générés par l'IA.")
    whiteboard_state = models.JSONField(null=True, blank=True, help_text="Dernier état sauvegardé du tableau blanc.")

    # Nouveaux champs pour le diagnostic de l'enseignant
    TEACHER_ERROR_CHOICES = [
        ('calcul', 'Erreur de calcul'),
        ('substitution', 'Erreur de substitution'),
        ('procedure', 'Erreur de procédure'),
        ('conceptuelle', 'Erreur conceptuelle'),
        ('autre', 'Autre'),
    ]
    teacher_analysis = models.JSONField(null=True, blank=True, help_text="Analyse structurée de l'enseignant. Contient 'error_analysis', 'notes', 'divergence_analysis', 'remediation_strategy', 'ai_influence_rating'.")

    AI_INFLUENCE_CHOICES = [
        (1, 'Pas du tout'),
        (2, 'Un peu'),
        (3, 'Moyennement'),
        (4, 'Beaucoup'),
    ]

    def __str__(self):
        return f"Session de {self.student.username} le {self.start_time.strftime('%d/%m/%Y')}"

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, related_name='messages', on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=[('user', 'User'), ('assistant', 'Assistant')])
    
    # --- LA CORRECTION EST ICI ---
    # On passe de TextField à JSONField pour stocker des données complexes (texte + image)
    content = models.JSONField() 
    
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role} à {self.timestamp.strftime('%H:%M')}"