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
            class_id = data.get('class_id')
            student_data = data.get('students', [])

            if not class_id or not student_data:
                return JsonResponse({'error': "Le JSON doit contenir 'class_id' et une liste 'students' d'objets avec une clé 'username'."}, status=400)

            try:
                target_class = Group.objects.get(id=class_id)
            except Group.DoesNotExist:
                return JsonResponse({'error': 'Class not found.'}, status=404)

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

                # --- Génération PDF sur une seule page ---
            
                # En-tête commun
                p.setFont("Helvetica-Bold", 20)
                p.drawCentredString(width / 2, height - 2.5 * cm, "Bienvenue sur Catalyst !")
                p.setFont("Helvetica", 14)
                p.drawCentredString(width / 2, height - 3.5 * cm, f"Classe : {target_class.name}")
                p.setStrokeColorRGB(0.8, 0.8, 0.8)
                p.line(2 * cm, height - 4.2 * cm, width - 2 * cm, height - 4.2 * cm) # Ligne horizontale

                # --- Partie gauche : Accès ---
                left_col_x = 3 * cm
                
                p.setFont("Helvetica-Bold", 16)
                p.drawString(left_col_x, height - 6 * cm, "Tes informations de connexion")
                p.setFont("Helvetica", 12)
                p.drawString(left_col_x, height - 7.5 * cm, f"Identifiant : {username}")
                p.drawString(left_col_x, height - 8.5 * cm, f"Mot de passe : {password}")

                # --- Partie droite : Guide de démarrage ---
                right_col_x = width / 2 + 0.5 * cm
                
                p.setFont("Helvetica-Bold", 16)
                p.drawString(right_col_x, height - 6 * cm, "Guide de Démarrage")

                text = p.beginText(right_col_x, height - 7.5 * cm)
                text.setFont("Helvetica-Bold", 12)
                text.setLeading(16)
                text.textLine("1. Choisir un exercice")
                text.setFont("Helvetica", 10)
                text.textLine("   Connecte-toi, choisis un chapitre, puis")
                text.textLine("   clique sur un exercice pour commencer.")
                text.textLine("")

                text.setFont("Helvetica-Bold", 12)
                text.textLine("2. Discuter avec l'IA")
                text.setFont("Helvetica", 10)
                text.textLine("   L'IA est ton tuteur personnel. Elle te")
                text.textLine("   guide pas à pas. N'hésite pas à lui")
                text.textLine("   montrer ton travail sur le brouillon.")
                text.textLine("")

                text.setFont("Helvetica-Bold", 12)
                text.textLine("3. Terminer la session")
                text.setFont("Helvetica", 10)
                text.textLine("   Quand tu as fini, clique sur le bouton")
                text.textLine("   'Terminer la session'.")
                text.textLine("")
                
                text.setFont("Helvetica-Bold", 12)
                text.textLine("4. Donner ton avis (Important !)")
                text.setFont("Helvetica", 10)
                text.textLine("   Après quelques sessions, un questionnaire")
                text.textLine("   apparaîtra. Tes réponses sont cruciales")
                text.textLine("   pour améliorer l'outil.")
                p.drawText(text)

                # --- QR Code en bas au centre ---
                qr = qrcode.make(base_url)
                qr_buffer = io.BytesIO()
                qr.save(qr_buffer, format='PNG')
                qr_buffer.seek(0)
                qr_size = 6 * cm
                p.drawImage(ImageReader(qr_buffer), (width - qr_size) / 2, 3 * cm, width=qr_size, height=qr_size)
                p.setFont("Helvetica", 10)
                p.drawCentredString(width / 2, 2.5 * cm, "Scanne ce code pour accéder au site")
                p.drawCentredString(width / 2, 2 * cm, base_url)
                
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