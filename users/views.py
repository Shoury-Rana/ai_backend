from django.contrib.auth.models import User
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import UserRegistrationSerializer, UserSerializer, LogoutSerializer

class UserRegistrationView(generics.CreateAPIView):
    """
    API view for user registration.
    Allows any user (authenticated or not) to create a new user account.
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny] # Override default permission

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Optionally, generate tokens for the user immediately after registration
        # refresh = RefreshToken.for_user(user)
        # tokens = {
        #     'refresh': str(refresh),
        #     'access': str(refresh.access_token),
        # }
        # return Response(tokens, status=status.HTTP_201_CREATED)
        # Or just return a success message
        return Response({"message": "User registered successfully."}, status=status.HTTP_201_CREATED)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    API view for retrieving and updating the logged-in user's profile.
    Only accessible by authenticated users.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Returns the user associated with the current request token
        return self.request.user

    # PUT is handled by default by RetrieveUpdateAPIView
    # PATCH is also handled by default

class LogoutView(APIView):
    """
    API view for user logout (blacklisting refresh token).
    Requires refresh token in the request body.
    """
    serializer_class = LogoutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"message": "Logout successful."}, status=status.HTTP_204_NO_CONTENT)