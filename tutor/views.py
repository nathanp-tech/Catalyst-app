# tutor/views.py

import threading
import os
import json
import numpy as np
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
from core.models import AppConfig
from core.ai_utils import generate_ai_response, get_embedding
from django.db.models import Prefetch
from django.conf import settings
from django.core.cache import cache


class TutorPageView(TemplateView):
    """
    Displays the tutor chat page and provides the list of available documents.
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
                # If resuming a session, ensure it is marked as "ongoing"
                if resume_session_id and session.end_time:
                    session.end_time = None
                    session.save()

                chat_history = list(ChatMessage.objects.filter(session=session).order_by('timestamp').values('role', 'content'))
                
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
                # Load categories for the tree if no session is in progress
                context['categories'] = Category.objects.filter(parent__isnull=True).prefetch_related(
                    Prefetch('children', queryset=Category.objects.order_by('order', 'name')),
                    Prefetch('children__documents', queryset=Document.objects.order_by('title'))
                ).order_by('order', 'name')
        else:
            # Load categories for the tree if no session is in progress
            context['categories'] = Category.objects.filter(parent__isnull=True).prefetch_related(
                Prefetch('children', queryset=Category.objects.order_by('order', 'name')),
                Prefetch('children__documents', queryset=Document.objects.order_by('title'))
            ).order_by('order', 'name')
        return context

class OpenAIAPIView(APIView):
    """
    Base view that initializes the OpenAI client.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class StartSessionView(LoginRequiredMixin, View):
    """
    Creates a new chat session for a given document and redirects to the tutor page.
    """
    def get(self, request, document_id):
        document = get_object_or_404(Document, pk=document_id)
        solution_doc = Document.objects.filter(solution_for=document).first()

        # Prepare the context for the AI
        question_context = f"Exercice: {document.title}"
        solution_context = "No solution provided."
        if solution_doc and solution_doc.file:
            # Ideally, we would extract the text from the solution PDF here.
            # For now, we'll stick to basic information.
            solution_context = f"The solution for the exercise '{solution_doc.title}' is available."

        # Create a new session
        chat_session = ChatSession.objects.create(
            student=request.user,
            document=document,
            question_context=question_context,
            solution_context=solution_context
        )
        
        # Generate the AI's welcome message
        try:
            welcome_prompt = {
                "role": "system",
                "content": "Tu es un tuteur de maths sympathique et encourageant. Tu t'apprêtes à commencer un exercice avec un élève. Ton premier message doit être un message d'accueil court et motivant pour l'inviter à commencer. Tu tutoies l'élève. Ne mentionne ni la question ni la solution. Réponds uniquement en français."
            }
            assistant_welcome_text = generate_ai_response(
                messages=[welcome_prompt, {"role": "user", "content": "Commence la conversation."}],
                model_name=AppConfig.get_active_model(),
                temperature=0.5
            )
            assistant_welcome_structured = [{"type": "text", "text": assistant_welcome_text}]
            
            # Save the first message to the database
            ChatMessage.objects.create(session=chat_session, role='assistant', content=assistant_welcome_structured)
        except Exception as e:
            print(f"Error generating welcome message: {e}")

        # Store the session ID and context in the user's session
        request.session['chat_session_id'] = chat_session.id
        request.session['exercise_context'] = {
            'question': chat_session.question_context,
            'solution': chat_session.solution_context
        }
        return redirect('tutor-page')

class TutorImageAnalysisView(OpenAIAPIView):
    """
    Analyzes a math question image at the beginning of the exercise.
    """
    def post(self, request, *args, **kwargs):
        document_url = request.data.get('document_url')
        image_base64 = request.data.get('image')
        if not image_base64:
            return Response({"error": "No image provided."}, status=status.HTTP_400_BAD_REQUEST)

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
            
            extraction_response_text = generate_ai_response(
                messages=[extraction_prompt, {"role": "user", "content": user_content}],
                model_name=AppConfig.get_active_model(),
                response_format={"type": "json_object"}
            )
            
            exercise_data = json.loads(extraction_response_text)
            question = exercise_data.get("question")
            solution = exercise_data.get("solution")

            if not question or not solution:
                raise ValueError("Question/solution extraction failed.")

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
            
            assistant_welcome_text = generate_ai_response(
                messages=[welcome_prompt, {"role": "user", "content": "Commence la conversation."}],
                model_name=AppConfig.get_active_model(),
                temperature=0.5
            )
            # Format the message to match the JSONField
            assistant_welcome_structured = [{"type": "text", "text": assistant_welcome_text}]
            
            ChatMessage.objects.create(
                session=chat_session,
                role='assistant',
                content=assistant_welcome_structured
            )
            
            initial_history = [{"role": "assistant", "content": assistant_welcome_structured}]
            return Response({"initial_history": initial_history}, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error during OpenAI image analysis: {e}")
            return Response({"error": "An error occurred while analyzing the image."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# --- RAG SYSTEM ---
# Variable globale pour garder l'index en mémoire vive (RAM)
RAG_INDEX = None

def get_relevant_curriculum(query, top_k=3):
    """
    Cherche les passages les plus pertinents du programme scolaire
    par rapport à la requête de l'utilisateur (recherche vectorielle).
    """
    global RAG_INDEX
    # Chemin vers l'index généré par la commande build_curriculum_index
    index_path = settings.BASE_DIR / 'data' / 'curriculum_index.json'

    # Chargement unique (Lazy loading)
    if RAG_INDEX is None:
        if os.path.exists(index_path):
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    RAG_INDEX = json.load(f)
            except Exception as e:
                print(f"Erreur chargement index RAG: {e}")
                return ""
        else:
            return "" # Pas d'index trouvé

    if not RAG_INDEX:
        return ""

    try:
        query_vector = get_embedding(query)
        
        # Calcul de similarité cosinus (produit scalaire si vecteurs normalisés)
        scores = []
        for item in RAG_INDEX:
            doc_vector = item['vector']
            score = np.dot(query_vector, doc_vector)
            scores.append((score, item['text']))
        
        # Trier par score décroissant et prendre les top_k
        scores.sort(key=lambda x: x[0], reverse=True)
        best_chunks = [text for score, text in scores[:top_k]]
        
        return "\n---\n".join(best_chunks)
    except Exception as e:
        print(f"Erreur recherche RAG: {e}")
        return ""

class BaseTutorAPIView(OpenAIAPIView):
    """
    Base class for tutor API views that share common logic.
    """
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        self.chat_session_id = request.session.get('chat_session_id')
        self.exercise_context = request.session.get('exercise_context')
        self.client_messages = request.data.get("messages")

        if not all([self.chat_session_id, self.exercise_context, self.client_messages]):
            return Response({"error": "Session is invalid or messages are missing."}, status=status.HTTP_400_BAD_REQUEST)

        # Optimisation : On diffère le chargement des champs lourds (whiteboard, summary, analysis)
        # car on a seulement besoin de l'ID et des relations de base pour créer les messages.
        self.chat_session = get_object_or_404(ChatSession.objects.defer('whiteboard_state', 'summary_data', 'teacher_analysis'), id=self.chat_session_id)
        
        return self.handle_logic(request, *args, **kwargs)

    def handle_logic(self, request, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement handle_logic.")


class TutorInteractionView(BaseTutorAPIView):
    """Handles a normal interaction with the AI tutor."""
    def handle_logic(self, request, *args, **kwargs):
        user_message_content = self.client_messages[-1]['content']
        ChatMessage.objects.create(session=self.chat_session, role='user', content=user_message_content)
        request.session['hint_level'] = 1

        # RAG : On cherche le contexte pertinent basé sur le dernier message de l'élève
        # et le contexte de l'exercice (pour être sûr de rester dans le sujet)
        search_query = f"{self.exercise_context['question']} {user_message_content}"
        relevant_curriculum = get_relevant_curriculum(search_query)
        
        curriculum_instruction = ""
        if relevant_curriculum:
            curriculum_instruction = f"""
            IMPORTANT - RESTRICTIONS DU PROGRAMME SCOLAIRE :
            Tu dois respecter le niveau et les méthodes du programme scolaire. Voici les extraits pertinents du programme officiel :
            
            --- DÉBUT EXTRAITS PROGRAMME ---
            {relevant_curriculum}
            --- FIN EXTRAITS PROGRAMME ---
            
            N'utilise PAS de concepts hors de ces extraits si possible.
            """

        system_prompt = f"""
        Tu es un tuteur de mathématiques bienveillant et Socratique. Ton objectif est de guider l'élève sans jamais lui donner la réponse ni les formules directement. Toutes tes réponses doivent être en français.
        
        {curriculum_instruction}

        Voici le contexte de l'exercice :
        - La question est : "{self.exercise_context['question']}"
        - La solution correcte est : "{self.exercise_context['solution']}"

        Tes règles d'or sont :
        1.  **Ne jamais donner la réponse directe** ou la prochaine étape.
        2.  **Analyser la réponse de l'élève** (image et/ou texte) pour identifier les erreurs ou les bonnes idées.
        3.  **Si la réponse est incorrecte, ne donne pas la correction tout de suite.** Guide l'élève pour qu'il retrouve la règle ou le concept lui-même. Par exemple, si l'élève oublie que la somme des angles d'un triangle est 180°, demande-lui : "Te souviens-tu de la somme des angles d'un triangle ?" au lieu de lui donner la valeur.
        4.  **Donner des indices subtils** si l'élève est bloqué, en posant des questions ouvertes.
        5.  **Utiliser le tutoiement** et un ton amical.
        6.  Garder tes réponses concises et focalisées sur une seule idée à la fois.
        7.  Si l'élève semble avoir compris, demande-lui d'expliquer avec ses propres mots pour valider sa compréhension.
        8. Quand l'élève a terminé l'exercice (réponse juste et justification suffisante), félicite le et propose lui de terminer la session pour cet exercice.
        """
        
        # Logic to format the history for the API
        processed_messages = []
        for msg in self.client_messages:
            new_msg = {'role': msg['role']}
            # If the content is a list (potentially with images), keep it as is.
            if isinstance(msg['content'], list):
                # Ensure the format is correct for the API
                new_content = []
                for part in msg['content']:
                    # Handle the format sent by the frontend {type: 'image_url', url: '...'}
                    if part.get('type') == 'image_url' and 'url' in part:
                        # Reconstruct the structure expected by the OpenAI API
                        new_content.append({'type': 'image_url', 'image_url': {'url': part['url']}})
                    elif part.get('type') == 'text':
                        new_content.append({'type': 'text', 'text': part['text']})
                new_msg['content'] = new_content
            else:
                new_msg['content'] = str(msg['content'])
            
            processed_messages.append(new_msg)

        api_messages = [{"role": "system", "content": system_prompt}] + processed_messages

        try:
            assistant_reply_text = generate_ai_response(
                messages=api_messages,
                model_name=AppConfig.get_active_model(),
                temperature=0.4
            )

            assistant_reply_structured = [{"type": "text", "text": assistant_reply_text}]
            
            ChatMessage.objects.create(
                session=self.chat_session,
                role='assistant',
                content=assistant_reply_structured
            )
            return Response({"content": assistant_reply_structured}, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error calling OpenAI: {e}")
            return Response({"error": "An error occurred while communicating with the AI."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EndSessionView(APIView):
    """
    Ends the current tutoring session and cleans up the user's session.
    """
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        chat_session_id = request.session.get('chat_session_id')
        if chat_session_id:
            try:
                session = ChatSession.objects.get(id=chat_session_id, student=request.user)
                if not session.end_time:
                    session.end_time = now()
                    # Start summary generation in the background
                    thread = threading.Thread(target=generate_and_save_session_summary, args=[session.id])
                    thread.start()
                    session.save()
            except ChatSession.DoesNotExist:
                pass

            request.session.pop('chat_session_id', None)
            request.session.pop('exercise_context', None)
            request.session.pop('hint_level', None)
        
        # Corrected line:
        return Response({'redirect_url': reverse('dashboard:dashboard')}, status=status.HTTP_200_OK)


class SaveWhiteboardView(APIView):
    """
    Saves the current state of the whiteboard for a given session.
    """
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        chat_session_id = request.session.get('chat_session_id')
        whiteboard_data = request.data.get('whiteboard_state')

        if not chat_session_id or whiteboard_data is None:
            return Response({"error": "Missing data."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = ChatSession.objects.get(id=chat_session_id)
            session.whiteboard_state = whiteboard_data
            session.save(update_fields=['whiteboard_state'])
            return Response({"success": True}, status=status.HTTP_200_OK)
        except ChatSession.DoesNotExist:
            return Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)