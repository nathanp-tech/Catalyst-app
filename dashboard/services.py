# dashboard/services.py

import json
from openai import OpenAI
from tutor.models import ChatSession

def generate_and_save_session_summary(session_id):
    """
    Génère un résumé pour une session de chat donnée en utilisant OpenAI et le sauvegarde dans la base de données.
    Cette fonction est conçue pour être exécutée en arrière-plan afin de ne pas bloquer la requête principale.
    """
    try:
        session = ChatSession.objects.get(id=session_id)
        
        # Si un résumé existe déjà, on ne fait rien.
        if session.summary_data:
            return

        # Construire l'historique de la conversation pour le prompt
        chat_history = ""
        for msg in session.messages.order_by('timestamp'):
            role = "Élève" if msg.role == 'user' else "Tuteur"
            content_text = ""
            if isinstance(msg.content, list):
                for item in msg.content:
                    if item.get('type') == 'text':
                        content_text += item.get('text', '') + " "
            elif isinstance(msg.content, str):
                content_text = msg.content
            chat_history += f"{role}: {content_text.strip()}\n"

        # Prompt pour l'IA
        prompt = f"""
        Analyse la conversation suivante entre un tuteur et un élève.
        Contexte de l'exercice:
        - Question: {session.question_context}
        - Solution: {session.solution_context}

        Conversation:
        {chat_history}

        Génère un résumé pour un enseignant au format JSON. Tes réponses doivent être exclusivement en français. Le JSON doit contenir deux clés :
        1. "error_analysis" : un objet JSON. Les seules clés autorisées dans cet objet sont : "Erreurs de calcul", "Erreurs de substitution", "Erreurs de procédure", "Erreurs conceptuelles". La valeur de chaque clé est le nombre de fois que ce type d'erreur a été commis par l'élève. Si un type d'erreur n'est pas présent, ne l'inclus pas.
        2. "summary_text" : un court paragraphe (3-4 phrases) résumant les échanges, les difficultés de l'élève et son évolution.
        """

        client = OpenAI()
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": prompt}], response_format={"type": "json_object"})
        summary_data = json.loads(response.choices[0].message.content)
        session.summary_data = summary_data
        session.save()

    except Exception as e:
        print(f"Erreur lors de la génération automatique du résumé pour la session {session_id}: {e}")