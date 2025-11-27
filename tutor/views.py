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
                # Load categories for the tree if no session is in progress
                context['categories'] = Category.objects.filter(parent__isnull=True).prefetch_related(
                    'children__children__documents'
                ).order_by('order', 'name')
        else:
            # Load categories for the tree if no session is in progress
            context['categories'] = Category.objects.filter(parent__isnull=True).prefetch_related(
                'children__children__documents'
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
            
            extraction_response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[extraction_prompt, {"role": "user", "content": user_content}],
                response_format={"type": "json_object"}
            )
            
            exercise_data = json.loads(extraction_response.choices[0].message.content)
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
            
            welcome_response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[welcome_prompt, {"role": "user", "content": "Commence la conversation."}],
                temperature=0.5
            )
            
            assistant_welcome_text = welcome_response.choices[0].message.content
            
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

        self.chat_session = get_object_or_404(ChatSession, id=self.chat_session_id)
        return self.handle_logic(request, *args, **kwargs)

    def handle_logic(self, request, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement handle_logic.")


class TutorInteractionView(BaseTutorAPIView):
    """Handles a normal interaction with the AI tutor."""
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