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

        student_data = data.get('students', [])

        if not student_data:
            self.stdout.write(self.style.ERROR("Le JSON doit contenir une liste 'students' d'objets avec une clé 'username'."))
            return

        # Récupération ou création des groupes "11VP" et "Eleves"
        target_class, _ = Group.objects.get_or_create(name="11VP")
        eleves_group, _ = Group.objects.get_or_create(name="Eleves")

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
            user.groups.add(eleves_group)
            self.stdout.write(f"  [OK] Utilisateur créé : {username}")

            # --- Génération PDF sur une seule page (Colonne unique) ---
            
            # En-tête
            c.setFont("Helvetica-Bold", 20)
            c.drawCentredString(width / 2, height - 2.5 * cm, "Guide d'utilisation de Catalyst-teaching")
            
            # Ligne de séparation
            c.setStrokeColorRGB(0.8, 0.8, 0.8)
            c.line(2 * cm, height - 3.5 * cm, width - 2 * cm, height - 3.5 * cm)

            # Section 1: Identifiants
            c.setFont("Helvetica-Bold", 14)
            c.drawString(2.5 * cm, height - 5 * cm, "1. Tes identifiants de connexion")
            
            # Cadre pour les identifiants
            c.setStrokeColorRGB(0.2, 0.2, 0.2)
            c.rect(2.5 * cm, height - 7.5 * cm, width - 5 * cm, 2 * cm)
            
            c.setFont("Helvetica", 12)
            c.drawString(3.5 * cm, height - 6.2 * cm, f"Identifiant : {username}")
            c.drawString(3.5 * cm, height - 6.9 * cm, f"Mot de passe : {password}")

            # Section 2: Guide (Colonne unique)
            text_y_start = height - 9 * cm
            text = c.beginText(2.5 * cm, text_y_start)
            text.setFont("Helvetica-Bold", 14)
            text.textLine("2. Comment utiliser l'application ?")
            text.moveCursor(0, 15)

            text.setFont("Helvetica-Bold", 12)
            text.textLine("Étape 1 : Choisir un exercice")
            text.setFont("Helvetica", 11)
            text.setLeading(14)
            text.textLine("Une fois connecté, tu arrives sur ton tableau de bord.")
            text.textLine("Tu y trouveras la liste des chapitres et des exercices disponibles.")
            text.textLine("Clique sur un exercice pour démarrer une session avec le tuteur IA.")
            text.moveCursor(0, 10)

            text.setFont("Helvetica-Bold", 12)
            text.textLine("Étape 2 : Discuter avec l'IA")
            text.setFont("Helvetica", 11)
            text.textLine("L'IA est là pour t'aider à réfléchir, pas pour te donner la réponse.")
            text.textLine("Utilise le chat pour proposer tes calculs, tes idées ou poser des questions.")
            text.textLine("Si tu es bloqué, demande un indice. L'IA te guidera étape par étape.")
            text.moveCursor(0, 10)

            text.setFont("Helvetica-Bold", 12)
            text.textLine("Étape 3 : Terminer la session")
            text.setFont("Helvetica", 11)
            text.textLine("Quand tu as fini l'exercice ou si tu dois t'arrêter, clique sur le bouton")
            text.textLine("'Terminer la session' (en haut ou en bas de l'écran).")
            text.textLine("C'est essentiel pour sauvegarder ta progression.")
            text.moveCursor(0, 10)
            
            text.setFont("Helvetica-Bold", 12)
            text.textLine("Étape 4 : Questionnaire")
            text.setFont("Helvetica", 11)
            text.textLine("Après quelques sessions, un questionnaire de satisfaction apparaîtra.")
            text.textLine("Merci de le remplir pour nous aider à améliorer Catalyst.")
            
            c.drawText(text)

            # QR Code en bas
            qr_size = 4 * cm
            qr_y = 2 * cm
            
            qr = qrcode.make(base_url)
            qr_buffer = io.BytesIO()
            qr.save(qr_buffer, format='PNG')
            qr_buffer.seek(0)
            
            c.drawImage(ImageReader(qr_buffer), (width - qr_size) / 2, qr_y, width=qr_size, height=qr_size)
            
            c.setFont("Helvetica", 10)
            c.drawCentredString(width / 2, qr_y - 0.5 * cm, "Scanne ce code pour accéder au site")
            c.drawCentredString(width / 2, qr_y - 1.0 * cm, base_url)

            c.showPage() # Terminer la page pour cet élève

        c.save()
        self.stdout.write(self.style.SUCCESS(f"Terminé ! Le PDF a été généré ici : {output_path}"))