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
    help = "Crée des élèves depuis un JSON (contenant des usernames) et génère un PDF avec les identifiants."

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
        student_data = data.get('students', [])

        if not class_id or not student_data:
            self.stdout.write(self.style.ERROR("Le JSON doit contenir 'class_id' et une liste 'students' d'objets avec une clé 'username'."))
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

        self.stdout.write(f"Création de {len(student_data)} élèves pour la classe '{target_class.name}'...")

        for student_info in student_data:
            username = student_info.get('username')
            if not username:
                self.stdout.write(self.style.WARNING("  [SKIP] Entrée élève sans 'username' ignorée."))
                continue

            # On vérifie si l'utilisateur existe déjà et on passe au suivant si c'est le cas.
            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.WARNING(f"  [SKIP] L'utilisateur {username} existe déjà."))
                continue
            
            # Génération mot de passe
            password = User.objects.make_random_password(length=8)
            
            # Création User
            user = User.objects.create_user(username=username, password=password)
            user.groups.add(target_class)
            self.stdout.write(f"  [OK] Utilisateur créé : {username}")

            # --- Génération PDF sur une seule page ---
            
            # En-tête commun
            c.setFont("Helvetica-Bold", 20)
            c.drawCentredString(width / 2, height - 2.5 * cm, "Bienvenue sur Catalyst !")
            c.setFont("Helvetica", 14)
            c.drawCentredString(width / 2, height - 3.5 * cm, f"Classe : {target_class.name}")
            c.setStrokeColorRGB(0.8, 0.8, 0.8)
            c.line(2 * cm, height - 4.2 * cm, width - 2 * cm, height - 4.2 * cm) # Ligne horizontale

            # --- Partie gauche : Accès ---
            left_col_x = 3 * cm
            
            c.setFont("Helvetica-Bold", 16)
            c.drawString(left_col_x, height - 6 * cm, "Tes informations de connexion")
            c.setFont("Helvetica", 12)
            c.drawString(left_col_x, height - 7.5 * cm, f"Identifiant : {username}")
            c.drawString(left_col_x, height - 8.5 * cm, f"Mot de passe : {password}")

            # --- Partie droite : Guide de démarrage ---
            right_col_x = width / 2 + 0.5 * cm
            
            c.setFont("Helvetica-Bold", 16)
            c.drawString(right_col_x, height - 6 * cm, "Guide de Démarrage")

            text = c.beginText(right_col_x, height - 7.5 * cm)
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
            c.drawText(text)

            # --- QR Code en bas au centre ---
            qr = qrcode.make(base_url)
            qr_buffer = io.BytesIO()
            qr.save(qr_buffer, format='PNG')
            qr_buffer.seek(0)
            qr_size = 6 * cm
            c.drawImage(ImageReader(qr_buffer), (width - qr_size) / 2, 3 * cm, width=qr_size, height=qr_size)
            c.setFont("Helvetica", 10)
            c.drawCentredString(width / 2, 2.5 * cm, "Scanne ce code pour accéder au site")
            c.drawCentredString(width / 2, 2 * cm, base_url)

            c.showPage() # Terminer la page pour cet élève

        c.save()
        self.stdout.write(self.style.SUCCESS(f"Terminé ! Le PDF a été généré ici : {output_path}"))