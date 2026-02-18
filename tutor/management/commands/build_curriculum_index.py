import json
import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from pypdf import PdfReader
from core.ai_utils import get_embedding

class Command(BaseCommand):
    help = "Vectorise le programme scolaire (RAG) et sauvegarde l'index JSON."

    def handle(self, *args, **options):
        # Chemins absolus basés sur la racine du projet
        pdf_path = settings.BASE_DIR / 'data' / 'curriculum.pdf'
        index_path = settings.BASE_DIR / 'data' / 'curriculum_index.json'

        if not pdf_path.exists():
            self.stdout.write(self.style.ERROR(f"Fichier PDF non trouvé : {pdf_path}"))
            return

        self.stdout.write(f"Lecture du PDF depuis : {pdf_path}")
        
        try:
            reader = PdfReader(pdf_path)
            full_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur lors de la lecture du PDF : {e}"))
            return

        # Découpage en "chunks" (morceaux) de ~1000 caractères avec chevauchement
        chunk_size = 1000
        overlap = 200
        chunks = []
        
        start = 0
        while start < len(full_text):
            end = start + chunk_size
            chunk = full_text[start:end]
            # On essaie de couper à la fin d'une phrase pour être propre
            last_period = chunk.rfind('.')
            if last_period != -1 and last_period > chunk_size // 2:
                end = start + last_period + 1
                chunk = full_text[start:end]
            
            chunks.append(chunk)
            start = end - overlap # Chevauchement pour ne pas perdre de contexte

        self.stdout.write(f"Génération des embeddings pour {len(chunks)} segments...")
        
        data_store = []
        for i, chunk in enumerate(chunks):
            try:
                vector = get_embedding(chunk)
                data_store.append({
                    "text": chunk,
                    "vector": vector
                })
                if i % 10 == 0:
                    self.stdout.write(f"Traité {i}/{len(chunks)}...")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erreur sur le segment {i}: {e}"))

        # Sauvegarde de l'index
        try:
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(data_store, f)
            self.stdout.write(self.style.SUCCESS(f"Index RAG créé avec succès dans : {index_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur lors de la sauvegarde de l'index : {e}"))