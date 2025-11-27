from django.urls import path
from django.contrib.auth.decorators import login_required

from .views import TutorInteractionView, TutorPageView, TutorImageAnalysisView, EndSessionView, SaveWhiteboardView, StartSessionView

urlpatterns = [
    # The HTML page for the chat
    path("", login_required(TutorPageView.as_view()), name="tutor-page"),
    path('start-session/<int:document_id>/', StartSessionView.as_view(), name='start-session'),
    # API endpoint for image analysis
    path("api/analyze-image/", TutorImageAnalysisView.as_view(), name="tutor-analyze-image"),
    # API endpoint for interaction
    path("api/interact/", TutorInteractionView.as_view(), name="tutor-interact"),
    # NEW URL: Endpoint to end a session
    path("api/end-session/", EndSessionView.as_view(), name="end-session"),
    # NEW URL: Endpoint to save the whiteboard state
    path("api/save-whiteboard/", SaveWhiteboardView.as_view(), name="save-whiteboard"),
]