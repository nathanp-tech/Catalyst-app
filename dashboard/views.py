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
from .models import GroupConfiguration


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
        
        # Par défaut, si l'utilisateur n'est pas un professeur, on affiche le tableau de bord élève.
        else:
            student_sessions = ChatSession.objects.filter(student=user).select_related('document').order_by('-start_time')
            
            # Ajout du statut pour chaque session
            for session in student_sessions:
                session.status = "Terminé" if session.end_time else "En cours"
                session.status_class = "completed" if session.end_time else "in-progress"

            context = {
                'user': user, 
                'documents': Document.objects.all().order_by('-uploaded_at'),
                'sessions': student_sessions
            }
            return render(request, 'dashboard/student_dashboard.html', context)


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
                    'chatsession_set__document', 
                    'chatsession_set__messages'
                )
            except Group.DoesNotExist:
                pass # Le groupe n'existe pas, on renvoie une liste d'élèves vide
        
        # Agréger les données de performance pour les élèves trouvés
        student_performance = []
        for student in students:
            performance_details = []
            sessions_for_student = student.chatsession_set.all()

            if selected_document_id:
                # Vue par exercice
                sessions_for_doc = sessions_for_student.filter(document_id=selected_document_id)
                if sessions_for_doc.exists():
                    latest_session = sessions_for_doc.latest('start_time')
                    total_duration = sum(((s.end_time - s.start_time).total_seconds() for s in sessions_for_doc if s.end_time), 0)
                    aggregated_errors = defaultdict(int)
                    for s in sessions_for_doc:
                        if s.summary_data and 'error_analysis' in s.summary_data:
                            for error, count in s.summary_data['error_analysis'].items():
                                aggregated_errors[error] += count

                    performance_details.append({
                        'doc_title': latest_session.document.title,
                        'attempts': sessions_for_doc.count(),
                        'message_count': sum(s.messages.count() for s in sessions_for_doc),
                        'total_duration_seconds': total_duration,
                        'aggregated_errors': dict(aggregated_errors),
                        'last_activity': latest_session.start_time.strftime("%d/%m/%Y %H:%M"),
                    })
            else:
                # Vue agrégée "Tous les exercices"
                if sessions_for_student.exists():
                    error_key_map = {
                        "Erreurs de calcul": "calcul",
                        "Erreurs de substitution": "substitution",
                        "Erreurs de procédure": "procedure",
                        "Erreurs conceptuelles": "conceptuelle",
                    }
                    total_duration = sum(((s.end_time - s.start_time).total_seconds() for s in sessions_for_student if s.end_time), 0)
                    aggregated_errors = defaultdict(int)
                    for s in sessions_for_student:
                        if s.summary_data and 'error_analysis' in s.summary_data:
                            for error, count in s.summary_data['error_analysis'].items():
                                short_key = error_key_map.get(error)
                                if short_key:
                                    aggregated_errors[short_key] += count
                    
                    total_errors = sum(aggregated_errors.values())
                    error_percentages = {err: (count / total_errors) * 100 for err, count in aggregated_errors.items()} if total_errors > 0 else {}

                    performance_details.append({
                        'is_aggregated': True,
                        'attempts': sessions_for_student.count(),
                        'message_count': sum(s.messages.count() for s in sessions_for_student),
                        'total_duration_seconds': total_duration,
                        'aggregated_errors': dict(aggregated_errors),
                        'error_percentages': error_percentages,
                        'last_activity': sessions_for_student.latest('start_time').start_time.strftime("%d/%m/%Y %H:%M"),
                    })

            student_performance.append({
                'student': student,
                'performance_data': performance_details
            })
            
        context['student_performance'] = student_performance
        return context


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class SavedGroupsView(LoginRequiredMixin, TemplateView):
    """
    Affiche les configurations de groupes enregistrées pour une classe sélectionnée.
    """
    template_name = "dashboard/saved_groups.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Récupérer toutes les classes pour le sélecteur
        all_classes = Group.objects.exclude(name='Professeurs')
        context['all_classes'] = all_classes

        selected_class_id = self.request.GET.get('class_id')
        context['selected_class_id'] = selected_class_id

        if selected_class_id:
            try:
                selected_class = Group.objects.get(id=selected_class_id)
                context['selected_class'] = selected_class
                context['saved_groups'] = GroupConfiguration.objects.filter(teacher_class=selected_class).order_by('-created_at')
            except Group.DoesNotExist:
                context['saved_groups'] = []
        
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

        # Récupérer tous les documents pour le filtre
        all_documents = Document.objects.all().order_by('title')
        context['all_documents'] = all_documents

        # Si un student_id est passé en paramètre, on l'utilise pour le filtre
        context['filtered_student_id'] = student_id if student_id else ''
        context['filtered_document_id'] = document_id if document_id else ''

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
        return redirect('dashboard:session-detail', session_id=session.id)

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
class DeleteSessionView(LoginRequiredMixin, View):
    """
    Vue API pour supprimer une session de chat.
    """
    def delete(self, request, *args, **kwargs):
        session_id = kwargs.get('session_id')
        try:
            session = ChatSession.objects.get(id=session_id)
            session.delete()
            return JsonResponse({'success': True, 'message': 'Session supprimée avec succès.'})
        except ChatSession.DoesNotExist:
            return JsonResponse({'error': 'Session non trouvée.'}, status=404)


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

        # La génération est maintenant automatique. On vérifie si le résumé est prêt.
        if session.summary_data:
            return JsonResponse(session.summary_data)
        elif session.end_time:
            # La session est terminée mais le résumé n'est pas encore là
            return JsonResponse({'status': 'processing', 'message': 'Le résumé est en cours de génération. Veuillez réessayer dans quelques instants.'})
        else:
            # La session n'est pas encore terminée
            return JsonResponse({'status': 'not_ended', 'message': 'Le résumé sera généré automatiquement à la fin de la session.'})


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


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class CreateStudentGroupsView(LoginRequiredMixin, View):
    """
    Vue API pour interagir avec l'IA afin de créer des groupes d'élèves.
    """
    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        class_id = data.get('class_id')
        num_groups = data.get('num_groups')
        messages = data.get('messages', [])

        if not class_id or not num_groups:
            return JsonResponse({'error': 'ID de classe et nombre de groupes requis.'}, status=400)

        try:
            teacher_class = Group.objects.get(id=class_id)
        except Group.DoesNotExist:
            return JsonResponse({'error': 'Classe non trouvée.'}, status=404)

        # 1. Récupérer les élèves et leurs performances globales
        students = get_user_model().objects.filter(groups=teacher_class)
        student_data_for_prompt = []
        for student in students:
            all_sessions = list(student.chatsession_set.all())
            if not all_sessions:
                student_data_for_prompt.append(f"- {student.username}: Aucune session.")
                continue

            total_duration = sum(((s.end_time - s.start_time).total_seconds() for s in all_sessions if s.end_time), 0)
            aggregated_errors = defaultdict(int)
            for s in all_sessions:
                if s.summary_data and 'error_analysis' in s.summary_data:
                    for error, count in s.summary_data['error_analysis'].items():
                        aggregated_errors[error] += count
            
            student_data_for_prompt.append(
                f"- {student.username}: {len(all_sessions)} sessions, "
                f"{int(total_duration / 60)} min au total, "
                f"erreurs fréquentes: {json.dumps(dict(aggregated_errors))}"
            )

        # 2. Construire le prompt pour l'IA
        system_prompt = f"""
        Tu es un assistant pédagogique expert. Un enseignant souhaite créer {num_groups} groupes de travail pour sa classe "{teacher_class.name}".
        Ton objectif est de proposer une répartition équilibrée (hétérogène par défaut) en te basant sur leurs performances. Toutes tes réponses doivent être en français.

        Voici les données des élèves de la classe :
        {chr(10).join(student_data_for_prompt)}

        Interagis avec l'enseignant pour affiner la répartition.
        À la fin, tu dois fournir la répartition finale UNIQUEMENT sous forme d'un objet JSON avec la clé "groups", qui est une liste de listes de noms d'élèves.
        Exemple pour 2 groupes: {{"groups": [["Alice", "Bob"], ["Charlie", "David"]]}}
        
        Commence la conversation en proposant une première répartition et en expliquant brièvement ta logique.
        """

        api_messages = [{"role": "system", "content": system_prompt}] + messages

        try:
            client = OpenAI()
            response = client.chat.completions.create(model="gpt-4o", messages=api_messages)
            ai_response = response.choices[0].message.content
            return JsonResponse({'reply': ai_response})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class SaveGroupConfigurationView(LoginRequiredMixin, View):
    """
    Vue API pour sauvegarder une configuration de groupes d'élèves.
    """
    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        class_id = data.get('class_id')
        config_name = data.get('name')
        groups = data.get('groups')

        if not all([class_id, config_name, groups]):
            return JsonResponse({'error': 'Données manquantes.'}, status=400)

        GroupConfiguration.objects.create(teacher_class_id=class_id, name=config_name, configuration=groups)
        return JsonResponse({'success': True, 'message': 'Configuration des groupes enregistrée.'})
