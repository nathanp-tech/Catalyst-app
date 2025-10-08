from django.db import models
from django.conf import settings
from documents.models import Document

class ChatSession(models.Model):
    """
    Représente une session de tutorat complète pour un élève sur un document.
    """
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_sessions')
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    question_context = models.TextField(blank=True, help_text="La question de l'exercice extraite par l'IA.")
    solution_context = models.TextField(blank=True, help_text="La solution de l'exercice extraite par l'IA.")
    teacher_notes = models.TextField(blank=True, help_text="Notes privées du professeur sur cette session.")

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return f"Session for {self.student.username} on {self.document.title if self.document else 'N/A'}"

    @property
    def duration(self):
        """Calcule la durée de la session si elle est terminée."""
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        return None


class ChatMessage(models.Model):
    """
    Représente un message unique au sein d'une session de chat.
    """
    session = models.ForeignKey(ChatSession, related_name='messages', on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=[('user', 'User'), ('assistant', 'Assistant')])
    content = models.JSONField()  # Stocke le contenu du message, potentiellement complexe (texte + image)
    timestamp = models.DateTimeField(auto_now_add=True)
