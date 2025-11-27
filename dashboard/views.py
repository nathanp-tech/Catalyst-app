from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import View, TemplateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse
from datetime import timedelta
from documents.models import Document, Category
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
    """Checks if a user belongs to a specific group."""
    return user.groups.filter(name=group_name).exists()

class DashboardView(LoginRequiredMixin, View):
    """
    Displays the appropriate dashboard based on the user's group.
    """
    login_url = '/accounts/login/' # Redirect if not logged in

    def get(self, request, *args, **kwargs):
        user = request.user

        if is_user_in_group(user, 'Professeurs'):
            context = {
                'user': user,
                'documents': Document.objects.filter(uploaded_by=user).order_by('-uploaded_at')
            }
            return render(request, 'dashboard/teacher_dashboard.html', context)
        
        # By default, if the user is not a teacher, display the student dashboard.
        else:
            student_sessions = ChatSession.objects.filter(student=user).select_related('document').order_by('-start_time')
            
            # Add status for each session
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
    """Checks if the user is a teacher."""
    return is_user_in_group(user, 'Professeurs')


class StudentProgressionView(LoginRequiredMixin, TemplateView):
    """
    Displays a gamified progression page for the student.
    """
    template_name = "dashboard/student_progression.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.user
        sessions = ChatSession.objects.filter(student=student).order_by('start_time')

        # --- 1. General statistics ---
        total_sessions = sessions.count()
        total_duration_seconds = sum(((s.end_time - s.start_time).total_seconds() for s in sessions if s.end_time), 0)
        total_messages = sum(s.messages.count() for s in sessions)

        context['total_sessions'] = total_sessions
        context['total_duration_minutes'] = int(total_duration_seconds / 60)
        context['total_messages'] = total_messages

        # --- 2. Error analysis (for charts) ---
        error_key_map = {
            "Erreurs de calcul": "calcul", "Erreurs de substitution": "substitution",
            "Erreurs de procédure": "procedure", "Erreurs conceptuelles": "conceptuelle",
        }
        overall_error_counts = defaultdict(int)
        errors_over_time = defaultdict(lambda: defaultdict(int)) # {week_start_date: {error_type: count}}

        for session in sessions:
            if session.summary_data and 'error_analysis' in session.summary_data:
                # For the global pie chart
                for error, count in session.summary_data['error_analysis'].items():
                    short_key = error_key_map.get(error)
                    if short_key:
                        overall_error_counts[short_key] += count
                
                # For the evolution chart
                week_start = session.start_time.date() - timedelta(days=session.start_time.weekday())
                for error, count in session.summary_data['error_analysis'].items():
                    short_key = error_key_map.get(error)
                    if short_key:
                        errors_over_time[week_start][short_key] += count

        context['overall_error_counts_json'] = json.dumps(overall_error_counts)
        
        # Format data for the evolution chart
        sorted_weeks = sorted(errors_over_time.keys())
        evolution_data = {
            'labels': [week.strftime('%d/%m') for week in sorted_weeks],
            'datasets': {
                'calcul': [errors_over_time[week]['calcul'] for week in sorted_weeks],
                'substitution': [errors_over_time[week]['substitution'] for week in sorted_weeks],
                'procedure': [errors_over_time[week]['procedure'] for week in sorted_weeks],
                'conceptuelle': [errors_over_time[week]['conceptuelle'] for week in sorted_weeks],
            }
        }
        context['error_evolution_json'] = json.dumps(evolution_data)

        # --- 3. Gamification: Badges ---
        badges = []
        if total_sessions >= 1:
            badges.append({'name': 'Premier Pas', 'icon': 'fa-shoe-prints', 'desc': 'Avoir terminé sa première session.'})
        if total_sessions >= 10:
            badges.append({'name': 'Apprenti Sérieux', 'icon': 'fa-graduation-cap', 'desc': 'Avoir terminé 10 sessions.'})
        if total_duration_seconds >= 3600: # 1 heure
            badges.append({'name': 'Marathonien', 'icon': 'fa-stopwatch', 'desc': 'Avoir passé plus d\'une heure à apprendre.'})
        if len(set(s.document_id for s in sessions if s.document_id)) >= 5:
            badges.append({'name': 'Explorateur', 'icon': 'fa-compass', 'desc': 'Avoir travaillé sur 5 exercices différents.'})
        
        context['badges'] = badges
        context['points'] = total_sessions * 10 + int(total_duration_seconds / 60) # Simple point calculation

        return context


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class LogbookListView(LoginRequiredMixin, TemplateView):
    """
    Displays a list of all pedagogical logbooks filled out by the teacher.
    """
    template_name = "dashboard/logbook_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # We only retrieve sessions where the teacher has filled at least part of the logbook
        # and which belong to that teacher's students (implicitly via documents)
        sessions_with_logbooks = ChatSession.objects.filter(
            teacher_analysis__isnull=False
        ).exclude(
            teacher_analysis__exact={}
        ).select_related('student', 'document').order_by('-start_time')
        context['sessions'] = sessions_with_logbooks
        return context


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class ClassDashboardView(LoginRequiredMixin, TemplateView):
    """
    Displays a class dashboard with student performance by exercise.
    """
    template_name = "dashboard/class_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        User = get_user_model()

        # 1. Prepare context for filters
        context['classes'] = Group.objects.exclude(name='Professeurs')
        context['exercise_categories'] = Category.objects.filter(parent__isnull=True).prefetch_related(
            'children__children__documents'
        ).order_by('order', 'name')

        selected_class_id = self.request.GET.get('class_id')
        selected_exercise_id = self.request.GET.get('exercise_id')
        context['selected_class_id'] = selected_class_id
        context['selected_exercise_id'] = selected_exercise_id

        # 2. Retrieve students if a class is selected
        students = []
        selected_group = None
        if selected_class_id:
            try:
                selected_group = Group.objects.get(id=selected_class_id)
                context['selected_group'] = selected_group
                students = User.objects.filter(groups=selected_group).prefetch_related(
                    'chatsession_set__document', 
                    'chatsession_set__messages'
                )
            except Group.DoesNotExist:
                pass # The group does not exist, return an empty student list

        # 3. Aggregate performance data for the found students
        student_performance = []
        for student in students:
            performance_details = []
            sessions_for_student = student.chatsession_set.all()

            if selected_exercise_id:
                # View by exercise
                sessions_for_doc = sessions_for_student.filter(document_id=selected_exercise_id)
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
                # Aggregated view "All exercises"
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
    Displays saved group configurations for a selected class.
    """
    template_name = "dashboard/saved_groups.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all classes for the selector
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
    Displays a list of all tutoring sessions for teachers.
    """
    template_name = "dashboard/session_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student_id = self.request.GET.get('student_id')
        document_id = self.request.GET.get('document_id')
        sessions = ChatSession.objects.select_related('student', 'document').prefetch_related('student__groups').all().order_by('-start_time')

        # Get all documents for the filter
        all_documents = Document.objects.all().order_by('title')
        context['all_documents'] = all_documents

        # If a student_id is passed as a parameter, use it for filtering
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
    Displays the details of a conversation session for teachers.
    Also handles saving notes.
    """
    model = ChatSession
    template_name = "dashboard/session_detail.html"
    context_object_name = 'session'
    pk_url_kwarg = 'session_id'

    def get_queryset(self):
        # Ensure that related data is loaded efficiently
        return ChatSession.objects.select_related('student', 'document').prefetch_related('messages')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ai_influence_choices'] = ChatSession.AI_INFLUENCE_CHOICES
        return context

    def post(self, request, *args, **kwargs):
        session = self.get_object()
        
        # Retrieve existing analysis or initialize a dictionary
        teacher_analysis_data = session.teacher_analysis or {}

        # Update with data from the logbook form
        teacher_analysis_data['divergence_analysis'] = request.POST.get('divergence_analysis', '')
        teacher_analysis_data['remediation_strategy'] = request.POST.get('remediation_strategy', '')
        teacher_analysis_data['ai_influence_rating'] = request.POST.get('ai_influence_rating')
        teacher_analysis_data['general_notes'] = request.POST.get('general_notes', '')

        session.teacher_analysis = teacher_analysis_data
        session.save()
        
        # Redirect to the same page to see the confirmation
        return redirect('dashboard:session-detail', session_id=session.id)

@method_decorator(user_passes_test(is_teacher), name='dispatch')
class SessionChatContentView(LoginRequiredMixin, View):
    """
    API view that returns the HTML content of a conversation for PDF generation.
    """
    def get(self, request, *args, **kwargs):
        session_id = kwargs.get('session_id')
        session = get_object_or_404(
            ChatSession.objects.prefetch_related('messages'),
            id=session_id
        )
        # Use a partial template to render only the chat
        html_content = render_to_string(
            'dashboard/partials/chat_content.html', 
            {'session': session, 'is_pdf_render': True}
        )
        return JsonResponse({'html': html_content})


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class CoAnalysisView(LoginRequiredMixin, DetailView):
    """
    Displays the Teacher-AI co-analysis interface for a session.
    """
    model = ChatSession
    template_name = 'dashboard/co_analysis.html'
    context_object_name = 'session'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['error_choices'] = ChatSession.TEACHER_ERROR_CHOICES
        # Ensures the AI summary is available for comparison
        if self.object.summary_data and 'error_analysis' in self.object.summary_data:
            context['ai_error_analysis'] = self.object.summary_data['error_analysis']
            context['ai_summary_text'] = self.object.summary_data.get('summary_text', "Aucun résumé textuel fourni par l'IA.")
        return context

    def post(self, request, *args, **kwargs):
        session = self.get_object()
        
        error_analysis = {}
        for key, _ in ChatSession.TEACHER_ERROR_CHOICES:
            count = request.POST.get(f'error_count_{key}')
            if count and int(count) > 0:
                error_analysis[key] = int(count)

        teacher_analysis_data = {
            'error_analysis': error_analysis,
            'notes': request.POST.get('teacher_diagnostic_notes', '')
        }
        session.teacher_analysis = teacher_analysis_data
        session.save()
        # Redirect to the same page to see the comparison result
        return redirect('dashboard:co-analysis', pk=session.pk)


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class DeleteSessionView(LoginRequiredMixin, View):
    """
    API view to delete a chat session.
    """
    def delete(self, request, *args, **kwargs):
        session_id = kwargs.get('session_id')
        try:
            session = ChatSession.objects.get(id=session_id)
            session.delete()
            return JsonResponse({'success': True, 'message': 'Session deleted successfully.'})
        except ChatSession.DoesNotExist:
            return JsonResponse({'error': 'Session not found.'}, status=404)


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class SessionSummaryView(LoginRequiredMixin, View):
    """
    API view that generates a session summary via AI for the teacher.
    """
    def get(self, request, *args, **kwargs):
        session_id = kwargs.get('session_id')
        session = get_object_or_404(
            ChatSession.objects.prefetch_related('messages', 'document', 'student'),
            id=session_id
        )

        # Generation is now automatic. Check if the summary is ready.
        if session.summary_data:
            return JsonResponse(session.summary_data)
        elif session.end_time:
            # The session is over but the summary is not yet available
            return JsonResponse({'status': 'processing', 'message': 'Le résumé est en cours de génération. Veuillez réessayer dans quelques instants.'})
        else:
            # The session is not yet over
            return JsonResponse({'status': 'not_ended', 'message': 'Le résumé sera généré automatiquement à la fin de la session.'})


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class ClassManagementView(LoginRequiredMixin, TemplateView):
    """
    Displays the class and student management page.
    """
    template_name = "dashboard/class_management.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        User = get_user_model()

        # Get all classes (Groups except 'Professeurs')
        classes = Group.objects.exclude(name='Professeurs').prefetch_related('user_set').order_by('name')
        
        # Get unassigned students
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
            return JsonResponse({'error': 'Class name is required.'}, status=400)
        if Group.objects.filter(name=class_name).exists():
            return JsonResponse({'error': 'A class with this name already exists.'}, status=400)
        
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
                return JsonResponse({'error': 'New name is required.'}, status=400)
            group.name = new_name
            group.save()
            return JsonResponse({'id': group.id, 'name': group.name})

        elif action == 'delete':
            if group.user_set.exists():
                return JsonResponse({'error': 'Cannot delete a non-empty class.'}, status=400)
            group.delete()
            return JsonResponse({'success': True, 'id': group_id})

        return JsonResponse({'error': 'Invalid action.'}, status=400)


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class StudentCreateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        password = request.POST.get('password')
        class_id = request.POST.get('class_id')

        if not username or not password:
            return JsonResponse({'error': 'Username and password are required.'}, status=400)
        
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            return JsonResponse({'error': 'This user already exists.'}, status=400)

        student = User.objects.create_user(username=username, password=password)
        
        if class_id:
            try:
                group = Group.objects.get(id=class_id)
                student.groups.add(group)
            except Group.DoesNotExist:
                pass # The student is created but not assigned

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
            student.groups.clear() # Remove the student from all current classes
            if target_class_id:
                target_class = get_object_or_404(Group, id=target_class_id)
                student.groups.add(target_class)
            return JsonResponse({'success': True, 'student_id': user_id, 'target_class_id': target_class_id or ''})

        elif action == 'delete':
            # Warning: this deletes the user and all associated data (sessions, etc.)
            student.delete()
            return JsonResponse({'success': True, 'student_id': user_id})

        return JsonResponse({'error': 'Invalid action.'}, status=400)


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
            return JsonResponse({'error': 'Class ID and number of groups are required.'}, status=400)

        try:
            teacher_class = Group.objects.get(id=class_id)
        except Group.DoesNotExist:
            return JsonResponse({'error': 'Class not found.'}, status=404)

        # 1. Get students and their overall performance
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

        # 2. Build the prompt for the AI
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
    API view to save a student group configuration.
    """
    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        class_id = data.get('class_id')
        config_name = data.get('name')
        groups = data.get('groups')

        if not all([class_id, config_name, groups]):
            return JsonResponse({'error': 'Missing data.'}, status=400)

        GroupConfiguration.objects.create(teacher_class_id=class_id, name=config_name, configuration=groups)
        return JsonResponse({'success': True, 'message': 'Group configuration saved.'})


@method_decorator(user_passes_test(is_teacher), name='dispatch')
class ClassAnalyticsAPIView(LoginRequiredMixin, View):
    """
    Provides aggregated data for class analysis charts.
    """
    def get(self, request, class_id, *args, **kwargs):
        try:
            teacher_class = Group.objects.get(id=class_id)
        except Group.DoesNotExist:
            return JsonResponse({'error': 'Class not found.'}, status=404)

        # Preload all sessions and messages for students in the class in 2 queries
        students = get_user_model().objects.filter(
            groups=teacher_class
        ).prefetch_related('chatsession_set__messages')

        analytics_data = []
        error_key_map = {
            "Erreurs de calcul": "calcul", "Erreurs de substitution": "substitution",
            "Erreurs de procédure": "procedure", "Erreurs conceptuelles": "conceptuelle",
        }

        for student in students:
            sessions = student.chatsession_set.all()
            total_duration = sum(((s.end_time - s.start_time).total_seconds() for s in sessions if s.end_time), 0)

            error_counts = defaultdict(int)
            for s in sessions:
                if s.summary_data and 'error_analysis' in s.summary_data:
                    for error, count in s.summary_data['error_analysis'].items():
                        short_key = error_key_map.get(error)
                        if short_key:
                            error_counts[short_key] += count

            analytics_data.append({
                'student_name': student.username,
                'total_sessions': len(sessions),
                'total_duration_minutes': int(total_duration / 60),
                'total_messages': sum(s.messages.count() for s in sessions),
                'total_errors': sum(error_counts.values()),
                'error_distribution': dict(error_counts)
            })

        return JsonResponse({
            'class_name': teacher_class.name,
            'analytics': analytics_data
        })
