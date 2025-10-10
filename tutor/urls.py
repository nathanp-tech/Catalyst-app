from django.urls import path
from django.contrib.auth.decorators import login_required

from .views import TutorInteractionView, TutorPageView, TutorImageAnalysisView, EndSessionView, TutorHintView, SaveWhiteboardView

urlpatterns = [
    # La page HTML pour le chat
    path("", login_required(TutorPageView.as_view()), name="tutor-page"),
    # L'endpoint API pour l'analyse d'image
    path("api/analyze-image/", TutorImageAnalysisView.as_view(), name="tutor-analyze-image"),
    # L'endpoint API pour l'interaction
    path("api/interact/", TutorInteractionView.as_view(), name="tutor-interact"),
    # L'endpoint API pour obtenir un indice
    path("api/get-hint/", TutorHintView.as_view(), name="tutor-get-hint"),
    # NOUVELLE URL: Endpoint pour terminer une session
    path("api/end-session/", EndSessionView.as_view(), name="tutor-end-session"),
    # NOUVELLE URL: Endpoint pour sauvegarder l'état du tableau blanc
    path("api/save-whiteboard/", SaveWhiteboardView.as_view(), name="tutor-save-whiteboard"),
]