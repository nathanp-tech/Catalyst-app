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
    Crée des comptes élèves en masse à partir d'une liste de noms et génère un PDF avec les identifiants.
    Attend un JSON : {"class_id": 1, "students": ["Nom1", "Nom2", ...]}
    """
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            class_id = data.get('class_id')
            student_names = data.get('students', [])

            if not class_id or not student_names:
                return JsonResponse({'error': 'Class ID and students list are required.'}, status=400)

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

            for name in student_names:
                # Génération username (nettoyage simple) et mot de passe
                base_username = "".join(c for c in name if c.isalnum()).lower()
                if not base_username: base_username = "eleve"
                
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                password = User.objects.make_random_password(length=8)
                
                # Création du compte
                user = User.objects.create_user(username=username, password=password)
                user.groups.add(target_class)

                # --- Génération de la page PDF ---
                p.setFont("Helvetica-Bold", 20)
                p.drawCentredString(width / 2, height - 3 * cm, "Bienvenue sur Catalyst !")
                
                p.setFont("Helvetica", 14)
                p.drawCentredString(width / 2, height - 4.5 * cm, f"Classe : {target_class.name}")
                
                p.setFont("Helvetica", 12)
                p.drawString(3 * cm, height - 7 * cm, f"Bonjour {name}, voici tes accès :")
                
                # Cadre identifiants
                p.rect(3 * cm, height - 11 * cm, width - 6 * cm, 3 * cm)
                p.setFont("Helvetica-Bold", 16)
                p.drawString(4 * cm, height - 9 * cm, f"Identifiant : {username}")
                p.drawString(4 * cm, height - 10 * cm, f"Mot de passe : {password}")
                
                # QR Code
                qr = qrcode.make(base_url)
                qr_buffer = io.BytesIO()
                qr.save(qr_buffer, format='PNG')
                qr_buffer.seek(0)
                p.drawImage(ImageReader(qr_buffer), (width - 6 * cm) / 2, height - 18 * cm, width=6 * cm, height=6 * cm)
                
                p.setFont("Helvetica", 10)
                p.drawCentredString(width / 2, height - 19 * cm, f"Accède à l'application : {base_url}")
                
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