from django.db import models

class AppConfig(models.Model):
    GPT_4O = 'gpt-4o'
    GEMINI_1_5_FLASH = 'gemini-1.5-flash'
    GEMINI_2_0_FLASH = 'gemini-2.0-flash'
    
    MODEL_CHOICES = [
        (GPT_4O, 'GPT-4o'),
        (GEMINI_1_5_FLASH, 'Gemini 1.5 Flash'),
        (GEMINI_2_0_FLASH, 'Gemini 2.0 Flash'),
    ]
    
    active_model = models.CharField(
        max_length=50,
        choices=MODEL_CHOICES,
        default=GPT_4O,
        verbose_name="Modèle IA actif"
    )

    def save(self, *args, **kwargs):
        self.pk = 1  # Singleton : on garde toujours l'ID 1
        super().save(*args, **kwargs)

    @classmethod
    def get_active_model(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config.active_model

    class Meta:
        verbose_name = "Configuration de l'application"
        verbose_name_plural = "Configuration de l'application"