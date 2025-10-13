# tutor/views.py

import threading
import os
import json
from django.core.serializers.json import DjangoJSONEncoder
from openai import OpenAI
from django.urls import reverse, reverse_lazy
from django.shortcuts import redirect, render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from .models import ChatSession, ChatMessage
from documents.models import Document
from dashboard.services import generate_and_save_session_summary
from documents.models import Category
from django.db.models.functions import Cast

class TutorPageView(TemplateView):
    """
    Affiche la page de chat du tuteur et fournit la liste des documents disponibles.
    """
    template_name = "tutor/tutor.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        resume_session_id = self.request.GET.get('resume')
        if resume_session_id:
            self.request.session['chat_session_id'] = resume_session_id
            chat_session_id = resume_session_id
        else:
            chat_session_id = self.request.session.get('chat_session_id')
        
        if chat_session_id:
            try:
                session = ChatSession.objects.select_related('document').get(id=chat_session_id)
                # Si on reprend une session, on s'assure qu'elle est marquée comme "en cours"
                if resume_session_id and session.end_time:
                    session.end_time = None
                    session.save()

                messages = ChatMessage.objects.filter(session=session).order_by('timestamp')
                
                chat_history = []
                for msg in messages:
                    chat_history.append({
                        'role': msg.role,
                        'content': msg.content
                    })
                
                context['ongoing_session'] = True
                context['chat_history_json'] = json.dumps(chat_history, cls=DjangoJSONEncoder)
                if session.document:
                    context['exercise_document_json'] = json.dumps({
                        'title': session.document.title,
                        'url': session.document.file.url
                    })
                if session.whiteboard_state:
                    context['whiteboard_state_json'] = json.dumps(session.whiteboard_state)

                
                self.request.session['exercise_context'] = {
                    'question': session.question_context,
                    'solution': session.solution_context
                }

            except ChatSession.DoesNotExist:
                self.request.session.pop('chat_session_id', None)
                context['documents'] = Document.objects.all().order_by('title')
                # Charger les catégories pour l'arborescence si aucune session n'est en cours
                context['categories'] = Category.objects.filter(parent__isnull=True).prefetch_related(
                    'children__children__documents'
                ).order_by('order', 'name')
        else:
            # Charger les catégories pour l'arborescence si aucune session n'est en cours
            context['categories'] = Category.objects.filter(parent__isnull=True).prefetch_related(
                'children__children__documents'
            ).order_by('order', 'name')
        return context

class OpenAIAPIView(APIView):
    """
    Vue de base qui initialise le client OpenAI.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class StartSessionView(LoginRequiredMixin, View):
    """
    Crée une nouvelle session de chat pour un document donné et redirige vers la page du tuteur.
    """
    def get(self, request, document_id):
        document = get_object_or_404(Document, pk=document_id)
        solution_doc = Document.objects.filter(solution_for=document).first()

        # Préparer le contexte pour l'IA
        question_context = f"Exercice: {document.title}"
        solution_context = "Aucun corrigé fourni."
        if solution_doc and solution_doc.file:
            # Idéalement, ici on extrairait le texte du PDF du corrigé.
            # Pour l'instant, on se contente d'une information basique.
            solution_context = f"Le corrigé de l'exercice '{solution_doc.title}' est disponible."

        # Créer une nouvelle session
        chat_session = ChatSession.objects.create(
            student=request.user,
            document=document,
            question_context=question_context,
            solution_context=solution_context
        )
        
        # Générer le message de bienvenue de l'IA
        try:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            welcome_prompt = {
                "role": "system",
                "content": "Tu es un tuteur de maths sympathique et encourageant. Tu t'apprêtes à commencer un exercice avec un élève. Ton premier message doit être un message d'accueil court et motivant pour l'inviter à commencer. Tu tutoies l'élève. Ne mentionne ni la question ni la solution. Réponds uniquement en français."
            }
            welcome_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[welcome_prompt, {"role": "user", "content": "Commence la conversation."}],
                temperature=0.5
            )
            assistant_welcome_text = welcome_response.choices[0].message.content
            assistant_welcome_structured = [{"type": "text", "text": assistant_welcome_text}]
            
            # Sauvegarder le premier message dans la base de données
            ChatMessage.objects.create(session=chat_session, role='assistant', content=assistant_welcome_structured)
        except Exception as e:
            print(f"Erreur lors de la génération du message de bienvenue : {e}")

        # Stocker l'ID de la session et le contexte dans la session de l'utilisateur
        request.session['chat_session_id'] = chat_session.id
        request.session['exercise_context'] = {
            'question': chat_session.question_context,
            'solution': chat_session.solution_context
        }
        return redirect('tutor-page')

class TutorImageAnalysisView(OpenAIAPIView):
    """
    Analyse une image de question mathématique au début de l'exercice.
    """
    def post(self, request, *args, **kwargs):
        document_url = request.data.get('document_url')
        image_base64 = request.data.get('image')
        if not image_base64:
            return Response({"error": "Aucune image fournie."}, status=status.HTTP_400_BAD_REQUEST)

        document = Document.objects.filter(file=document_url.replace('/media/', '')).first()

        try:
            extraction_prompt = {
                "role": "system",
                "content": "Tu es un expert en mathématiques. Extrait la question et la solution détaillée de l'image. Renvoie UNIQUEMENT un objet JSON avec les clés 'question' et 'solution'."
            }
            user_content = [
                {"type": "text", "text": "Analyse cette image et extrais-en la question et la solution."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
            ]
            
            extraction_response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[extraction_prompt, {"role": "user", "content": user_content}],
                response_format={"type": "json_object"}
            )
            
            exercise_data = json.loads(extraction_response.choices[0].message.content)
            question = exercise_data.get("question")
            solution = exercise_data.get("solution")

            if not question or not solution:
                raise ValueError("Extraction de la question/solution échouée.")

            chat_session = ChatSession.objects.create(
                student=request.user,
                document=document,
                question_context=question,
                solution_context=solution
            )
            request.session['chat_session_id'] = chat_session.id
            request.session['exercise_context'] = {'question': question, 'solution': solution}

            welcome_prompt = {
                "role": "system",
                "content": "Tu es un tuteur de maths sympathique et encourageant. Tu t'apprêtes à commencer un exercice avec un élève. Ton premier message doit être un message d'accueil court et motivant pour l'inviter à commencer. Tu tutoies l'élève. Ne mentionne ni la question ni la solution. Réponds uniquement en français."
            }
            
            welcome_response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[welcome_prompt, {"role": "user", "content": "Commence la conversation."}],
                temperature=0.5
            )
            
            assistant_welcome_text = welcome_response.choices[0].message.content
            
            # On formate le message pour qu'il corresponde au JSONField
            assistant_welcome_structured = [{"type": "text", "text": assistant_welcome_text}]
            
            ChatMessage.objects.create(
                session=chat_session,
                role='assistant',
                content=assistant_welcome_structured
            )
            
            initial_history = [{"role": "assistant", "content": assistant_welcome_structured}]
            return Response({"initial_history": initial_history}, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Erreur lors de l'analyse d'image par OpenAI: {e}")
            return Response({"error": "Une erreur est survenue lors de l'analyse de l'image."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BaseTutorAPIView(OpenAIAPIView):
    """
    Classe de base pour les vues d'API du tuteur qui partagent une logique commune.
    """
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        self.chat_session_id = request.session.get('chat_session_id')
        self.exercise_context = request.session.get('exercise_context')
        self.client_messages = request.data.get("messages")

        if not all([self.chat_session_id, self.exercise_context, self.client_messages]):
            return Response({"error": "La session est invalide ou les messages sont manquants."}, status=status.HTTP_400_BAD_REQUEST)

        self.chat_session = get_object_or_404(ChatSession, id=self.chat_session_id)
        return self.handle_logic(request, *args, **kwargs)

    def handle_logic(self, request, *args, **kwargs):
        raise NotImplementedError("Les sous-classes doivent implémenter handle_logic.")


class TutorInteractionView(BaseTutorAPIView):
    """Gère une interaction normale avec le tuteur IA."""
    def handle_logic(self, request, *args, **kwargs):
        user_message_content = self.client_messages[-1]['content']
        ChatMessage.objects.create(session=self.chat_session, role='user', content=user_message_content)
        request.session['hint_level'] = 1

        system_prompt = f"""
        Tu es un tuteur de mathématiques bienveillant et Socratique. Ton objectif est de guider l'élève sans jamais lui donner la réponse. Toutes tes réponses doivent être en français.
        
        Voici le contexte de l'exercice :
        - La question est : "{self.exercise_context['question']}"
        - La solution correcte est : "{self.exercise_context['solution']}"

        Tes règles d'or sont :
        1.  **Ne jamais donner la réponse directe** ou la prochaine étape.
        2.  **Analyser la réponse de l'élève** (image et/ou texte) pour identifier les erreurs ou les bonnes idées.
        3.  **Si la réponse est incorrecte ou hors-sujet, corrige gentiment mais directement.** Ne te contente pas de demander "en quoi cela aide ?". Compare ce que l'élève a fait avec ce que l'énoncé demande. Par exemple, si l'élève dessine un polygone irrégulier pour un exercice sur les polygones réguliers, dis : "C'est un bon début de dessiner un polygone ! L'énoncé nous demande un polygone *régulier*. Te souviens-tu de ce qui le rend 'régulier' ?". Sois un guide actif, pas seulement un questionneur passif.
        4.  **Donner des indices subtils** si l'élève est bloqué, en posant des questions ouvertes.
        6.  **Utiliser le tutoiement** et un ton amical.
        7.  Garder tes réponses concises et focalisées sur une seule idée à la fois.
        8.  Si l'élève semble avoir compris, demande-lui d'expliquer avec ses propres mots pour valider sa compréhension.
        """
        
        # Logique de formatage de l'historique pour l'API
        processed_messages = []
        for msg in self.client_messages:
            new_msg = {'role': msg['role']}
            # Si le contenu est une liste (avec potentiellement des images), on le garde tel quel.
            if isinstance(msg['content'], list):
                # Assurons-nous que le format est correct pour l'API
                new_content = []
                for part in msg['content']:
                    # CORRECTION: Gérer le format envoyé par le frontend {type: 'image_url', url: '...'}
                    if part.get('type') == 'image_url' and 'url' in part:
                        # On reconstruit la structure attendue par l'API OpenAI
                        new_content.append({'type': 'image_url', 'image_url': {'url': part['url']}})
                    elif part.get('type') == 'text':
                        new_content.append({'type': 'text', 'text': part['text']})
                new_msg['content'] = new_content
            else:
                new_msg['content'] = str(msg['content'])
            
            processed_messages.append(new_msg)

        api_messages = [{"role": "system", "content": system_prompt}] + processed_messages

        try:
            completion = self.client.chat.completions.create(
                model="gpt-4o",
                messages=api_messages,
                temperature=0.4,
                max_tokens=1000
            )

            assistant_reply_text = completion.choices[0].message.content
            assistant_reply_structured = [{"type": "text", "text": assistant_reply_text}]
            
            ChatMessage.objects.create(
                session=self.chat_session,
                role='assistant',
                content=assistant_reply_structured
            )
            return Response({"content": assistant_reply_structured}, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Erreur lors de l'appel à OpenAI: {e}")
            return Response({"error": "Une erreur est survenue lors de la communication avec l'IA."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EndSessionView(APIView):
    """
    Termine la session de tutorat en cours et nettoie la session de l'utilisateur.
    """
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        chat_session_id = request.session.get('chat_session_id')
        if chat_session_id:
            try:
                session = ChatSession.objects.get(id=chat_session_id, student=request.user)
                if not session.end_time:
                    session.end_time = now()
                    # Lancer la génération du résumé en arrière-plan
                    thread = threading.Thread(target=generate_and_save_session_summary, args=[session.id])
                    thread.start()
                    session.save()
            except ChatSession.DoesNotExist:
                pass

            request.session.pop('chat_session_id', None)
            request.session.pop('exercise_context', None)
            request.session.pop('hint_level', None)
        
        # Voici la ligne corrigée :
        return Response({'redirect_url': reverse('dashboard:dashboard')}, status=status.HTTP_200_OK)


class SaveWhiteboardView(APIView):
    """
    Sauvegarde l'état actuel du tableau blanc pour une session donnée.
    """
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        chat_session_id = request.session.get('chat_session_id')
        whiteboard_data = request.data.get('whiteboard_state')

        if not chat_session_id or whiteboard_data is None:
            return Response({"error": "Données manquantes."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = ChatSession.objects.get(id=chat_session_id)
            session.whiteboard_state = whiteboard_data
            session.save(update_fields=['whiteboard_state'])
            return Response({"success": True}, status=status.HTTP_200_OK)
        except ChatSession.DoesNotExist:
            return Response({"error": "Session non trouvée."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)