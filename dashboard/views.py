from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import View, TemplateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse
from documents.models import Document
from django.db.models import Q
from django.contrib.auth.models import Group
import json
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from openai import OpenAI
from collections import defaultdict
from tutor.models import ChatSession, ChatMessage


def is_user_in_group(user, group_name):
    """Vérifie si un utilisateur appartient à un groupe spécifique."""
    return user.groups.filter(name=group_name).exists()

class DashboardView(LoginRequiredMixin, View):
    """
    Affiche le tableau de bord approprié en fonction du groupe de l'utilisateur.
    """
    login_url = '/accounts/login/' # Redirige si non connecté

    def get(self, request, *args, **kwargs):
        user = request.user

        if is_user_in_group(user, 'Professeurs'):
            context = {
                'user': user,
                'documents': Document.objects.filter(uploaded_by=user).order_by('-uploaded_at')
            }
            return render(request, 'dashboard/teacher_dashboard.html', context)
        
        # Si l'utilisateur est un élève ou n'a pas de groupe assigné,
        # on affiche le tableau de bord élève par défaut.
        elif is_user_in_group(user, 'Eleves') or not user.groups.exists():
            student_sessions = ChatSession.objects.filter(student=user).select_related('document').order_by('-start_time')
            context = {
                'user': user, 
                'documents': Document.objects.all().order_by('-uploaded_at'),
                'sessions': student_sessions
            }
            return render(request, 'dashboard/student_dashboard.html', context)
        
        # Si un utilisateur est dans un autre groupe, on peut prévoir une page par défaut
        return render(request, 'dashboard/student_dashboard.html', {'user': user, 'documents': []})


def is_teacher(user):
    """Vérifie si l'utilisateur est un professeur."""
    return is_user_in_group(user, 'Professeurs')


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class ClassDashboardView(LoginRequiredMixin, TemplateView):
    """
    Affiche un tableau de bord de classe avec les performances des élèves par exercice.
    """
    template_name = "dashboard/class_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Récupérer tous les groupes qui peuvent être des classes (on exclut les profs)
        all_classes = Group.objects.exclude(name='Professeurs')
        context['all_classes'] = all_classes
        context['all_documents'] = Document.objects.all().order_by('title')
        
        selected_group_id = self.request.GET.get('group')
        selected_document_id = self.request.GET.get('document')
        context['selected_group_id'] = selected_group_id
        context['selected_document_id'] = selected_document_id
        
        selected_group_id = self.request.GET.get('group')
        students = []
        
        User = get_user_model()
        if selected_group_id:
            try:
                selected_group = Group.objects.get(id=selected_group_id)
                context['selected_group'] = selected_group
                students = User.objects.filter(groups=selected_group).prefetch_related(
                    'chat_sessions__document', 
                    'chat_sessions__messages'
                )
            except Group.DoesNotExist:
                pass # Le groupe n'existe pas, on renvoie une liste d'élèves vide
        
        # Agréger les données de performance pour les élèves trouvés
        student_performance = []
        for student in students:
            sessions_by_doc = defaultdict(list)
            for session in student.chat_sessions.all():
                # Filtrer par document si un document est sélectionné
                if selected_document_id:
                    if session.document and str(session.document.id) == selected_document_id:
                        sessions_by_doc[session.document.id].append(session)
                # Sinon, regrouper toutes les sessions par document
                elif session.document:
                    sessions_by_doc[session.document.id].append(session)
            
            # Préparer les données pour la modale (format JSON)
            performance_details = []
            for doc_id, sessions in sessions_by_doc.items():
                latest_session = max(sessions, key=lambda s: s.start_time)
                total_duration = sum((s.duration.total_seconds() for s in sessions if s.duration), 0)
                
                performance_details.append({
                    'doc_title': latest_session.document.title,
                    'status': 'Terminé' if latest_session.end_time else 'En cours',
                    'attempts': len(sessions),
                    'message_count': sum(s.messages.count() for s in sessions),
                    'total_duration_seconds': total_duration,
                    'last_activity': latest_session.start_time.strftime("%d/%m/%Y %H:%M"),
                    'latest_session_url': reverse('session-detail', args=[latest_session.id])
                })
            
            student_data = {
                'student': student,
                'student_id': student.id,
                'performance_data': performance_details
            }
            student_performance.append(student_data)
            
        context['student_performance'] = student_performance
        return context


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class SessionListView(LoginRequiredMixin, TemplateView):
    """
    Affiche la liste de toutes les sessions de tutorat pour les professeurs.
    """
    template_name = "dashboard/session_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student_id = self.request.GET.get('student_id')
        document_id = self.request.GET.get('document_id')
        sessions = ChatSession.objects.select_related('student', 'document').all().order_by('-start_time')

        # Récupérer tous les élèves (ceux qui ne sont pas professeurs) pour le filtre
        User = get_user_model()
        all_students = User.objects.exclude(groups__name='Professeurs').order_by('username')
        context['all_students'] = all_students

        # Récupérer tous les documents pour le filtre
        all_documents = Document.objects.all().order_by('title')
        context['all_documents'] = all_documents

        # Si un student_id est passé en paramètre, on l'utilise pour le filtre
        context['filtered_student_id'] = student_id if student_id else ''
        context['filtered_document_id'] = document_id if student_id else ''

        if student_id:
            sessions = sessions.filter(student_id=student_id)

        if document_id:
            sessions = sessions.filter(document_id=document_id)

        context['sessions'] = sessions
        return context


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class SessionDetailView(LoginRequiredMixin, DetailView):
    """
    Affiche le détail d'une session de conversation pour les professeurs.
    Gère également la sauvegarde des notes.
    """
    model = ChatSession
    template_name = "dashboard/session_detail.html"
    context_object_name = 'session'
    pk_url_kwarg = 'session_id'

    def get_queryset(self):
        # S'assurer que les données associées sont chargées efficacement
        return ChatSession.objects.select_related('student', 'document').prefetch_related('messages')

    def post(self, request, *args, **kwargs):
        session = self.get_object()
        notes = request.POST.get('teacher_notes', '')
        session.teacher_notes = notes
        session.save()
        # Redirige vers la même page pour voir la confirmation
        return redirect('session-detail', session_id=session.id)

@method_decorator(user_passes_test(is_teacher), name='dispatch')
class SessionChatContentView(LoginRequiredMixin, View):
    """
    Vue API qui renvoie le contenu HTML d'une conversation pour la génération de PDF.
    """
    def get(self, request, *args, **kwargs):
        session_id = kwargs.get('session_id')
        session = get_object_or_404(
            ChatSession.objects.prefetch_related('messages'),
            id=session_id
        )
        # On utilise un template partiel pour ne rendre que le chat
        html_content = render_to_string(
            'dashboard/partials/chat_content.html', 
            {'session': session, 'is_pdf_render': True}
        )
        return JsonResponse({'html': html_content})


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class SessionSummaryView(LoginRequiredMixin, View):
    """
    Vue API qui génère un résumé de la session via l'IA pour l'enseignant.
    """
    def get(self, request, *args, **kwargs):
        session_id = kwargs.get('session_id')
        session = get_object_or_404(
            ChatSession.objects.prefetch_related('messages', 'document', 'student'),
            id=session_id
        )

        # Construire l'historique de la conversation
        chat_history = ""
        for msg in session.messages.order_by('timestamp'):
            role = "Élève" if msg.role == 'user' else "Tuteur"
            content_text = ""
            # Le contenu peut être une liste de dictionnaires (texte/image)
            if isinstance(msg.content, list):
                for item in msg.content:
                    if item.get('type') == 'text':
                        content_text += item.get('text', '') + " "
            elif isinstance(msg.content, str): # Ancien format
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

        Génère un résumé pour un enseignant au format JSON. Le JSON doit contenir :
        1. Une clé "error_analysis" : un objet où chaque clé est un type d'erreur (ex: "Erreur de calcul", "Mauvaise application de formule", "Incompréhension du concept") et la valeur est le nombre d'occurrences.
        2. Une clé "summary_text" : un court paragraphe résumant les échanges, les difficultés de l'élève et son évolution.
        """

        try:
            client = OpenAI() # Assurez-vous que OPENAI_API_KEY est dans vos variables d'environnement
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"}
            )
            summary_data = json.loads(response.choices[0].message.content)
            return JsonResponse(summary_data)
        except Exception as e:
            return JsonResponse({'error': f"Erreur lors de la génération du résumé: {str(e)}"}, status=500)


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class ClassManagementView(LoginRequiredMixin, TemplateView):
    """
    Affiche la page de gestion des classes et des élèves.
    """
    template_name = "dashboard/class_management.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        User = get_user_model()

        # Récupérer toutes les classes (Groupes sauf 'Professeurs')
        classes = Group.objects.exclude(name='Professeurs').prefetch_related('user_set').order_by('name')
        
        # Récupérer les élèves non assignés
        assigned_student_ids = ChatMessage.objects.filter(
            session__student__groups__isnull=False
        ).values_list('session__student_id', flat=True).distinct()

        unassigned_students = User.objects.exclude(
            groups__name='Professeurs'
        ).exclude(
            id__in=assigned_student_ids
        ).filter(groups__isnull=True).order_by('username')

        context['classes'] = classes
        context['unassigned_students'] = unassigned_students
        return context


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class ClassCreateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        class_name = request.POST.get('class_name')
        if not class_name:
            return JsonResponse({'error': 'Le nom de la classe est requis.'}, status=400)
        if Group.objects.filter(name=class_name).exists():
            return JsonResponse({'error': 'Une classe avec ce nom existe déjà.'}, status=400)
        
        new_class = Group.objects.create(name=class_name)
        return JsonResponse({'id': new_class.id, 'name': new_class.name})


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class ClassActionView(LoginRequiredMixin, View):
    def post(self, request, group_id, *args, **kwargs):
        action = request.POST.get('action')
        group = get_object_or_404(Group, id=group_id)

        if action == 'rename':
            new_name = request.POST.get('new_name')
            if not new_name:
                return JsonResponse({'error': 'Le nouveau nom est requis.'}, status=400)
            group.name = new_name
            group.save()
            return JsonResponse({'id': group.id, 'name': group.name})

        elif action == 'delete':
            if group.user_set.exists():
                return JsonResponse({'error': 'Impossible de supprimer une classe non vide.'}, status=400)
            group.delete()
            return JsonResponse({'success': True, 'id': group_id})

        return JsonResponse({'error': 'Action non valide.'}, status=400)


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class StudentCreateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        password = request.POST.get('password')
        class_id = request.POST.get('class_id')

        if not username or not password:
            return JsonResponse({'error': 'Nom d\'utilisateur et mot de passe requis.'}, status=400)
        
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            return JsonResponse({'error': 'Cet utilisateur existe déjà.'}, status=400)

        student = User.objects.create_user(username=username, password=password)
        
        if class_id:
            try:
                group = Group.objects.get(id=class_id)
                student.groups.add(group)
            except Group.DoesNotExist:
                pass # L'élève est créé mais non assigné

        return JsonResponse({
            'id': student.id, 
            'username': student.username,
            'class_id': class_id or ''
        })


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class StudentActionView(LoginRequiredMixin, View):
    def post(self, request, user_id, *args, **kwargs):
        action = request.POST.get('action')
        student = get_object_or_404(get_user_model(), id=user_id)

        if action == 'move':
            target_class_id = request.POST.get('target_class_id')
            student.groups.clear() # Retire l'élève de toutes ses classes actuelles
            if target_class_id:
                target_class = get_object_or_404(Group, id=target_class_id)
                student.groups.add(target_class)
            return JsonResponse({'success': True, 'student_id': user_id, 'target_class_id': target_class_id or ''})

        elif action == 'delete':
            # Attention: ceci supprime l'utilisateur et toutes ses données associées (sessions, etc.)
            student.delete()
            return JsonResponse({'success': True, 'student_id': user_id})

        return JsonResponse({'error': 'Action non valide.'}, status=400)
