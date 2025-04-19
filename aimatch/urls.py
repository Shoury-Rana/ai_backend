from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView, # Login view
    TokenRefreshView,    # Refresh token view
    TokenVerifyView,     # Optional: Verify token view
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # API URLs
    path('api/users/', include('users.urls')), # Include your users app urls

    # JWT Token Endpoints
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'), # POST username/password -> returns access/refresh tokens
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'), # POST refresh_token -> returns new access token
    # Optional: Verify token endpoint
    # path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'), # POST token -> verifies token validity

    # You might want to include DRF's browsable API login/logout views for development/testing
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),

    path('api/end_call/', include('end_call.urls')), 
]