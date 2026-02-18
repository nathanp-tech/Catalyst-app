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
from pypdf import PdfReader


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
                context['categories'] = Category.objects.filter(parent__isnull=True).prefetch_related(
                    Prefetch('children', queryset=Category.objects.order_by('order', 'name')),
                    Prefetch('children__documents', queryset=Document.objects.order_by('title'))
                ).order_by('order', 'name')
        else:
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

        question_context = f"Exercice: {document.title}"
        solution_context = "No solution provided."
        
        # Fonction utilitaire pour extraire le texte d'un PDF
        def extract_pdf_text(doc_file):
            text = ""
            try:
                if doc_file:
                    with doc_file.open('rb') as f:
                        reader = PdfReader(f)
                        for page in reader.pages:
                            extracted = page.extract_text()
                            if extracted:
                                text += extracted + "\n"
            except Exception as e:
                print(f"Erreur lecture PDF: {e}")
            return text

        if solution_doc and solution_doc.file:
            # Si un corrigé existe, on essaie de lire son contenu
            extracted = extract_pdf_text(solution_doc.file)
            if extracted.strip():
                solution_context = extracted
            else:
                solution_context = f"The solution for the exercise '{solution_doc.title}' is available."
        else:
            try:
                # Sinon, on lit l'énoncé pour le donner à l'IA
                exercise_content = f"Titre : {document.title}"
                extracted_text = extract_pdf_text(document.file)
                if extracted_text.strip():
                    exercise_content += f"\n\nContenu de l'exercice (extrait du PDF) :\n{extracted_text}"

                solve_prompt = {
                    "role": "system",
                    "content": "Tu es un professeur de mathématiques expert. Résous l'exercice suivant de manière EXTRÊMEMENT DÉTAILLÉE, étape par étape. Fournis toutes les équations, les calculs intermédiaires et les justifications logiques. Cette résolution servira de correction de référence absolue."
                }
                generated_solution = generate_ai_response(
                    messages=[solve_prompt, {"role": "user", "content": exercise_content}],
                    model_name=AppConfig.get_active_model(),
                    temperature=0.2
                )
                solution_context = generated_solution
            except Exception as e:
                print(f"Erreur lors de la génération de la correction: {e}")
                solution_context = "Attention: Correction détaillée non disponible. Le tuteur devra s'appuyer sur ses propres calculs en temps réel."

        chat_session = ChatSession.objects.create(
            student=request.user,
            document=document,
            question_context=question_context,
            solution_context=solution_context
        )
        
        try:
            welcome_prompt = {
                "role": "system",
                "content": "Tu es un tuteur de maths sympathique. Tu t'apprêtes à commencer un exercice avec un élève. Ton premier message doit l'inviter à commencer spécifiquement par la question 1 (ex: 'Salut ! Prêt à commencer ? Commençons par la question 1...'). Tu tutoies l'élève. Ne donne aucune réponse."
            }
            assistant_welcome_text = generate_ai_response(
                messages=[welcome_prompt, {"role": "user", "content": "Commence la conversation."}],
                model_name=AppConfig.get_active_model(),
                temperature=0.5
            )
            assistant_welcome_structured = [{"type": "text", "text": assistant_welcome_text}]
            
            ChatMessage.objects.create(session=chat_session, role='assistant', content=assistant_welcome_structured)
        except Exception as e:
            print(f"Error generating welcome message: {e}")

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
                "content": "Tu es un expert en mathématiques. 1) Extrait l'énoncé complet et exact de l'image. 2) Résous l'exercice toi-même de manière EXTRÊMEMENT DÉTAILLÉE, étape par étape, en incluant tous les calculs et raisonnements logiques. Renvoie UNIQUEMENT un objet JSON avec les clés 'question' (l'énoncé) et 'solution' (ta correction détaillée pas à pas)."
            }
            user_content = [
                {"type": "text", "text": "Analyse cette image, extrais l'énoncé complet puis rédige la correction détaillée étape par étape."},
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
                "content": "Tu es un tuteur de maths sympathique. Tu t'apprêtes à commencer un exercice avec un élève. Ton premier message doit l'inviter à commencer spécifiquement par la question 1. Tu tutoies l'élève. Ne mentionne pas la solution."
            }
            
            assistant_welcome_text = generate_ai_response(
                messages=[welcome_prompt, {"role": "user", "content": "Commence la conversation."}],
                model_name=AppConfig.get_active_model(),
                temperature=0.5
            )
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
RAG_INDEX = None

def get_relevant_curriculum(query, top_k=3):
    global RAG_INDEX
    index_path = settings.BASE_DIR / 'data' / 'curriculum_index.json'

    if RAG_INDEX is None:
        if os.path.exists(index_path):
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    RAG_INDEX = json.load(f)
            except Exception as e:
                print(f"Erreur chargement index RAG: {e}")
                return ""
        else:
            return ""

    if not RAG_INDEX:
        return ""

    try:
        query_vector = get_embedding(query)
        scores = []
        for item in RAG_INDEX:
            doc_vector = item['vector']
            score = np.dot(query_vector, doc_vector)
            scores.append((score, item['text']))
        
        scores.sort(key=lambda x: x[0], reverse=True)
        best_chunks = [text for score, text in scores[:top_k]]
        
        return "\n---\n".join(best_chunks)
    except Exception as e:
        print(f"Erreur recherche RAG: {e}")
        return ""

class BaseTutorAPIView(OpenAIAPIView):
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        self.chat_session_id = request.session.get('chat_session_id')
        self.exercise_context = request.session.get('exercise_context')
        self.client_messages = request.data.get("messages")

        if not all([self.chat_session_id, self.exercise_context, self.client_messages]):
            return Response({"error": "Session is invalid or messages are missing."}, status=status.HTTP_400_BAD_REQUEST)

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

        search_query = f"{self.exercise_context['question']} {user_message_content}"
        relevant_curriculum = get_relevant_curriculum(search_query)
        
        curriculum_instruction = ""
        if relevant_curriculum:
            curriculum_instruction = f"""
            IMPORTANT - RESTRICTIONS DU PROGRAMME SCOLAIRE :
            Tu dois respecter le niveau et les méthodes du programme scolaire. Voici les extraits pertinents :
            --- DÉBUT EXTRAITS PROGRAMME ---
            {relevant_curriculum}
            --- FIN EXTRAITS PROGRAMME ---
            """

        system_prompt = f"""
        Tu es un tuteur de mathématiques strict et méthodique. Ton rôle n'est pas d'être complaisant, mais de garantir l'exactitude mathématique absolue.

        {curriculum_instruction}

        CONTEXTE DE L'EXERCICE :
        - Énoncé : "{self.exercise_context['question']}"
        - Solution de référence (LA VÉRITÉ ABSOLUE) : 
        "{self.exercise_context['solution']}"

        RÈGLES D'OR DE LA CORRECTION (CRITIQUES) :
        1. VÉRIFICATION INTRANSIGEANTE : Compare TOUJOURS la proposition de l'élève à la Solution de référence et à l'énoncé. Si l'élève propose une formule (comme 20-10x), demande-toi d'abord si les nombres correspondent à ceux de l'énoncé. Ne valide JAMAIS une formule contenant les mauvaises constantes.
        2. DIRE CLAIREMENT QUAND C'EST FAUX : Si la réponse est fausse, tu DOIS le dire sans ambiguïté. Commence ta réponse par "Non, ce n'est pas correct".
        3. ANALYSER LA RÉPONSE DE L'ÉLÈVE : Identifie ses erreurs ou ses bonnes idées. Après avoir dit que c'est faux, explique EXACTEMENT où l'élève s'est trompé en pointant la contradiction avec l'énoncé. S'il oublie un concept (ex: somme des angles = 180°), demande-lui "Te souviens-tu de la règle des angles ?" au lieu de lui donner la valeur.
        4. GUIDAGE ÉTAPE PAR ÉTAPE : Ne traite qu'une seule question ou idée à la fois. Si vous débutez, dis "Commençons par répondre à la question 1". Ne laisse pas l'élève sauter des étapes.
        5. DONNER DES INDICES SUBTILS : Si l'élève est bloqué, pose des questions ouvertes. N'écris pas la formule corrigée et ne fais pas le calcul à sa place. Force l'élève à la trouver suite à ton explication.
        6. TOLÉRANCE SUR LA MÉTHODE : N'oblige pas l'élève à utiliser une méthode spécifique si sa méthode mathématique est correcte et mène au bon résultat (sauf si le programme scolaire l'interdit).
        7. PROGRESSION : Seulement APRÈS avoir vérifié et validé formellement que la réponse à la question en cours est 100% correcte, félicite-le et suggère explicitement de passer à la question suivante. Si l'élève semble avoir compris, demande-lui d'expliquer avec ses propres mots pour valider sa compréhension.

        TON ET STYLE : Utilise le tutoiement, un ton amical mais rigoureux, et reste toujours concis (une idée à la fois).
        """
        
        processed_messages = []
        for msg in self.client_messages:
            new_msg = {'role': msg['role']}
            if isinstance(msg['content'], list):
                new_content = []
                for part in msg['content']:
                    if part.get('type') == 'image_url' and 'url' in part:
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
                temperature=0.2 # Température très basse pour limiter la créativité complaisante
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
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        chat_session_id = request.session.get('chat_session_id')
        if chat_session_id:
            try:
                session = ChatSession.objects.get(id=chat_session_id, student=request.user)
                if not session.end_time:
                    session.end_time = now()
                    thread = threading.Thread(target=generate_and_save_session_summary, args=[session.id])
                    thread.start()
                    session.save()
            except ChatSession.DoesNotExist:
                pass

            request.session.pop('chat_session_id', None)
            request.session.pop('exercise_context', None)
            request.session.pop('hint_level', None)
        
        return Response({'redirect_url': reverse('dashboard:dashboard')}, status=status.HTTP_200_OK)


class SaveWhiteboardView(APIView):
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

class GetSolutionView(APIView):
    """
    API endpoint to retrieve the solution of the current exercise.
    """
    def get(self, request, *args, **kwargs):
        chat_session_id = request.session.get('chat_session_id')
        if not chat_session_id:
            return Response({"error": "No active session."}, status=status.HTTP_400_BAD_REQUEST)
        
        session = get_object_or_404(ChatSession, id=chat_session_id, student=request.user)
        return Response({"solution": session.solution_context}, status=status.HTTP_200_OK)