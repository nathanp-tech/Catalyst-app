from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
 
 
class CustomUserCreationForm(UserCreationForm):
    """
    Un formulaire de création d'utilisateur personnalisé.
    """
 
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")