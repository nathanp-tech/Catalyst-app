import json
import os
import io
import qrcode
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.conf import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader

class Command(BaseCommand):
    help = "Crée des élèves depuis un JSON et génère un PDF avec les identifiants."

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='data/students_to_create.json',
            help='Chemin vers le fichier JSON (par défaut: data/students_to_create.json)'
        )
        parser.add_argument(
            '--domain',
            type=str,
            default='https://www.catalyst-teaching.com',
            help='Domaine de base pour le QR code'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        base_url = options['domain']

        # Gestion du chemin relatif
        if not os.path.isabs(file_path):
            file_path = settings.BASE_DIR / file_path

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"Fichier introuvable : {file_path}"))
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR("Format JSON invalide."))
                return

        class_id = data.get('class_id')
        student_names = data.get('students', [])

        if not class_id or not student_names:
            self.stdout.write(self.style.ERROR("Le JSON doit contenir 'class_id' et une liste 'students'."))
            return

        try:
            target_class = Group.objects.get(id=class_id)
        except Group.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Classe avec l'ID {class_id} introuvable."))
            return

        User = get_user_model()
        
        # Configuration du PDF
        output_filename = f"comptes_{target_class.name.replace(' ', '_')}.pdf"
        # Sauvegarde à la racine du projet
        output_path = settings.BASE_DIR / output_filename
        
        c = canvas.Canvas(str(output_path), pagesize=A4)
        width, height = A4

        self.stdout.write(f"Création de {len(student_names)} élèves pour la classe '{target_class.name}'...")

        for name in student_names:
            # Génération username
            base_username = "".join(c for c in name if c.isalnum()).lower()
            if not base_username: base_username = "eleve"
            
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            # Génération mot de passe
            password = User.objects.make_random_password(length=8)
            
            # Création User
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username=username, password=password)
                user.groups.add(target_class)
                self.stdout.write(f"  [OK] Utilisateur créé : {username} ({name})")
            else:
                self.stdout.write(f"  [SKIP] L'utilisateur {username} existe déjà.")

            # --- Génération page PDF ---
            c.setFont("Helvetica-Bold", 20)
            c.drawCentredString(width / 2, height - 3 * cm, "Bienvenue sur Catalyst !")
            
            c.setFont("Helvetica", 14)
            c.drawCentredString(width / 2, height - 4.5 * cm, f"Classe : {target_class.name}")
            
            c.setFont("Helvetica", 12)
            c.drawString(3 * cm, height - 7 * cm, f"Bonjour {name}, voici tes accès :")
            
            # Cadre identifiants
            c.rect(3 * cm, height - 11 * cm, width - 6 * cm, 3 * cm)
            c.setFont("Helvetica-Bold", 16)
            c.drawString(4 * cm, height - 9 * cm, f"Identifiant : {username}")
            c.drawString(4 * cm, height - 10 * cm, f"Mot de passe : {password}")
            
            # QR Code
            qr = qrcode.make(base_url)
            qr_buffer = io.BytesIO()
            qr.save(qr_buffer, format='PNG')
            qr_buffer.seek(0)
            c.drawImage(ImageReader(qr_buffer), (width - 6 * cm) / 2, height - 18 * cm, width=6 * cm, height=6 * cm)
            
            c.setFont("Helvetica", 10)
            c.drawCentredString(width / 2, height - 19 * cm, f"Accède à l'application : {base_url}")
            
            c.showPage()

        c.save()
        self.stdout.write(self.style.SUCCESS(f"Terminé ! Le PDF a été généré ici : {output_path}"))