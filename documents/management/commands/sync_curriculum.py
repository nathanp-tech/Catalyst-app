import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from documents.models import Category, Document


class Command(BaseCommand):
    help = "Synchronise la structure du programme scolaire depuis un fichier JSON vers la base de données."

    def handle(self, *args, **options):
        # Chemin vers le fichier JSON
        json_path = Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'curriculum.json'

        if not json_path.exists():
            self.stdout.write(self.style.ERROR(f"Le fichier {json_path} n'a pas été trouvé."))
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.stdout.write("Début de la synchronisation du programme scolaire...")

        try:
            # Utiliser une transaction pour assurer l'intégrité des données
            with transaction.atomic():
                self._sync_curriculum(data['curriculum'])
            self.stdout.write(self.style.SUCCESS("Synchronisation terminée avec succès !"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Une erreur est survenue : {e}"))

    def _sync_curriculum(self, curriculum_data):
        """Logique de synchronisation."""

        # Helper pour le tri naturel (gère "NO2" avant "NO10")
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

        # On garde une trace des IDs pour nettoyer les anciens éléments
        processed_category_ids = set()
        processed_document_ids = set()

        for grade_index, grade_data in enumerate(curriculum_data):
            grade_name = grade_data['grade']
            grade_cat, _ = Category.objects.update_or_create(name=grade_name, parent=None, defaults={'order': grade_index})
            processed_category_ids.add(grade_cat.id)

            for chapter_index, chapter_data in enumerate(grade_data['chapters']):
                chapter_name = chapter_data['name']
                chapter_cat, _ = Category.objects.update_or_create(name=chapter_name, parent=grade_cat, defaults={'order': chapter_index})
                processed_category_ids.add(chapter_cat.id)

                for exercise_name in sorted(chapter_data['exercises'], key=natural_sort_key):
                    # Créer ou récupérer l'exercice
                    exercise_doc, _ = Document.objects.get_or_create(
                        category=chapter_cat,
                        title=exercise_name,
                        solution_for=None,
                    )
                    processed_document_ids.add(exercise_doc.id)

                    # Créer ou récupérer le corrigé associé
                    solution_doc, _ = Document.objects.get_or_create(
                        category=chapter_cat,
                        title=f"{exercise_name} (Corrigé)",
                        solution_for=exercise_doc,
                    )
                    processed_document_ids.add(solution_doc.id)

        # Nettoyage : supprimer les catégories et documents qui ne sont plus dans le JSON
        Document.objects.exclude(id__in=processed_document_ids).delete()
        Category.objects.exclude(id__in=processed_category_ids).delete()

        self.stdout.write(f"{len(processed_category_ids)} catégories et {len(processed_document_ids)} documents traités.")