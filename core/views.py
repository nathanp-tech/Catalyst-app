from django.views.generic import TemplateView, UpdateView, View
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from .models import AppConfig
import json
import io
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader


class HomeView(TemplateView):
    """
    Displays the homepage for unauthenticated visitors.
    If a user is already logged in, they are redirected to their dashboard.
    """
    template_name = "core/home.html"

    def get(self, request, *args, **kwargs):
        # If the user is authenticated, redirect to their dashboard.
        if request.user.is_authenticated:
            return redirect(reverse('dashboard:dashboard'))
        
        # Otherwise, show the normal homepage for visitors.
        return super().get(request, *args, **kwargs)

class SettingsView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = AppConfig
    fields = ['active_model']
    template_name = "core/settings.html"
    success_url = reverse_lazy('settings')

    def test_func(self):
        return self.request.user.is_staff

    def get_object(self, queryset=None):
        obj, _ = AppConfig.objects.get_or_create(pk=1)
        return obj

def is_teacher(user):
    """Checks if the user is a teacher."""
    return user.groups.filter(name='Professeurs').exists()

@method_decorator(user_passes_test(is_teacher), name='dispatch')
class BulkCreateStudentsView(LoginRequiredMixin, View):
    """
    Crée des comptes élèves en masse à partir d'une liste de noms d'utilisateurs et génère un PDF avec les identifiants.
    Attend un JSON : {"class_id": 1, "students": [{"username": "user1"}, ...]}
    """
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            student_data = data.get('students', [])

            if not student_data:
                return JsonResponse({'error': "Le JSON doit contenir une liste 'students' d'objets avec une clé 'username'."}, status=400)

            target_class, _ = Group.objects.get_or_create(name="11VP")
            eleves_group, _ = Group.objects.get_or_create(name="Eleves")

            User = get_user_model()

            # Préparation du PDF
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4
            base_url = request.build_absolute_uri('/') # URL racine du site

            for student_info in student_data:
                username = student_info.get('username')
                if not username:
                    continue # On ignore les entrées sans username

                # Si l'utilisateur existe déjà, on l'ignore pour ne pas bloquer la création en masse
                if User.objects.filter(username=username).exists():
                    continue

                password = User.objects.make_random_password(length=8)

                # Création du compte
                user = User.objects.create_user(username=username, password=password)
                user.groups.add(target_class)
                user.groups.add(eleves_group)

                # --- Génération PDF sur une seule page (Colonne unique) ---
            
                # En-tête
                p.setFont("Helvetica-Bold", 20)
                p.drawCentredString(width / 2, height - 2.5 * cm, "Guide d'utilisation de Catalyst-teaching")
                
                # Ligne de séparation
                p.setStrokeColorRGB(0.8, 0.8, 0.8)
                p.line(2 * cm, height - 3.5 * cm, width - 2 * cm, height - 3.5 * cm)

                # Section 1: Identifiants
                p.setFont("Helvetica-Bold", 14)
                p.drawString(2.5 * cm, height - 5 * cm, "1. Tes identifiants de connexion")
                
                # Cadre pour les identifiants
                p.setStrokeColorRGB(0.2, 0.2, 0.2)
                p.rect(2.5 * cm, height - 7.5 * cm, width - 5 * cm, 2 * cm)
                
                p.setFont("Helvetica", 12)
                p.drawString(3.5 * cm, height - 6.2 * cm, f"Identifiant : {username}")
                p.drawString(3.5 * cm, height - 6.9 * cm, f"Mot de passe : {password}")

                # Section 2: Guide (Colonne unique)
                text = p.beginText(2.5 * cm, height - 9 * cm)
                text.setFont("Helvetica-Bold", 14)
                text.textLine("2. Comment utiliser l'application ?")
                text.moveCursor(0, 15)
                text.setLeading(15)

                text.setFont("Helvetica-Bold", 12)
                text.textLine("1. Connexion")
                text.setFont("Helvetica", 11)
                text.textLine("Dans Safari, scanne le QR code ou recopie le lien. Remplis ensuite")
                text.textLine("ton nom d'utilisateur et ton mot de passe.")
                text.moveCursor(0, 12)

                text.setFont("Helvetica-Bold", 12)
                text.textLine("2. Choisir un exercice")
                text.setFont("Helvetica", 11)
                text.textLine("Sur ton tableau de bord, clique sur \"Démarrer avec le tuteur IA\",")
                text.textLine("puis sur \"Documents complémentaires / Général\" et choisis un exercice.")
                text.moveCursor(0, 12)

                text.setFont("Helvetica-Bold", 12)
                text.textLine("3. Travailler avec l'IA")
                text.setFont("Helvetica", 11)
                text.textLine("L'exercice s'affiche. Partage tes réponses et questions avec l'IA via :")
                text.textLine("   - Le clavier (texte)")
                text.textLine("   - Le brouillon de l'application (dessin)")
                text.textLine("   - La photo de ta feuille")
                text.moveCursor(0, 12)

                text.setFont("Helvetica-Bold", 12)
                text.textLine("4. Terminer la session")
                text.setFont("Helvetica", 11)
                text.textLine("Quand tu as terminé, clique sur le bouton rouge \"Terminer\".")
                text.moveCursor(0, 12)

                text.setFont("Helvetica-Bold", 12)
                text.textLine("5. Donner ton avis")
                text.setFont("Helvetica", 11)
                text.textLine("De retour au tableau de bord, clique sur \"Donne ton avis\" pour")
                text.textLine("répondre à un questionnaire rapide.")

                p.drawText(text)

                # QR Code en bas
                qr_size = 4 * cm
                qr_y = 2 * cm
                
                qr = qrcode.make(base_url)
                qr_buffer = io.BytesIO()
                qr.save(qr_buffer, format='PNG')
                qr_buffer.seek(0)
                
                p.drawImage(ImageReader(qr_buffer), (width - qr_size) / 2, qr_y, width=qr_size, height=qr_size)
                
                p.setFont("Helvetica", 10)
                p.drawCentredString(width / 2, qr_y - 0.5 * cm, "Scanne ce code pour accéder au site")
                p.drawCentredString(width / 2, qr_y - 1.0 * cm, base_url)
                
                p.showPage() # Nouvelle page pour le prochain élève

            p.save()
            buffer.seek(0)
            
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="comptes_{target_class.name}.pdf"'
            return response

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)