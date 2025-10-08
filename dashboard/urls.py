from django.urls import path
from .views import *

urlpatterns = [
    # Le nom 'dashboard' est utilisé dans settings.py pour LOGIN_REDIRECT_URL
    path("", DashboardView.as_view(), name="dashboard"),

    # URLs pour le suivi des sessions par le professeur
    path('class-dashboard/', ClassDashboardView.as_view(), name='class-dashboard'),
    path('sessions/', SessionListView.as_view(), name='session-list'),
    path('sessions/<int:session_id>/', SessionDetailView.as_view(), name='session-detail'),
    # NOUVELLE URL: API pour récupérer le contenu du chat
    path('api/sessions/<int:session_id>/content/', SessionChatContentView.as_view(), name='session-chat-content'),
    # NOUVELLE URL: API pour générer un résumé de la session
    path('api/sessions/<int:session_id>/summary/', SessionSummaryView.as_view(), name='session-summary'),

    # URLs pour la gestion des classes et des élèves
    path('manage-classes/', ClassManagementView.as_view(), name='manage-classes'),
    path('api/classes/create/', ClassCreateView.as_view(), name='class-create'),
    path('api/classes/<int:group_id>/action/', ClassActionView.as_view(), name='class-action'),
    path('api/students/create/', StudentCreateView.as_view(), name='student-create'),
    path('api/students/<int:user_id>/action/', StudentActionView.as_view(), name='student-action'),
]