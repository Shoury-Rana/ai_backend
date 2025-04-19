# users/urls.py

from django.urls import path
from .views import UserRegistrationView, UserProfileView, LogoutView

# Define app name for namespacing if needed, though not strictly required for API views
app_name = 'users'

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user-register'),
    path('me/', UserProfileView.as_view(), name='user-profile'), # GET, PUT, PATCH for logged-in user
    path('logout/', LogoutView.as_view(), name='user-logout'), # POST for logout (blacklisting)
]