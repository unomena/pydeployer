from django.urls import path
from .views import GitLabWebhookView, GenericWebhookView

urlpatterns = [
    path('gitlab/', GitLabWebhookView.as_view(), name='webhook_gitlab'),
    path('generic/', GenericWebhookView.as_view(), name='webhook_generic'),
]