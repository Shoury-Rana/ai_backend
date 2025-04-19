# end_call/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChatSessionViewSet, UserAPIKeyViewSet

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'sessions', ChatSessionViewSet, basename='session')
router.register(r'keys', UserAPIKeyViewSet, basename='key')

# The API URLs are now determined automatically by the router.
# - /api/end_call/sessions/ -> List sessions, Create session (POST to custom 'create' action)
# - /api/end_call/sessions/{pk}/ -> Retrieve session details
# - /api/end_call/sessions/{pk}/message/ -> Add message (POST)
# - /api/end_call/sessions/{pk}/ -> Delete session (DELETE)
# - /api/end_call/keys/ -> List keys, Create key (POST)
# - /api/end_call/keys/{pk}/ -> Retrieve, Update, Delete key

urlpatterns = [
    path('', include(router.urls)),
]