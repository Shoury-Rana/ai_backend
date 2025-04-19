from django.shortcuts import render
import requests
# Create your views here.

# end_call/views.py
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import ChatSession, ChatMessage, UserAPIKey
from .serializers import (
    ChatSessionListSerializer, ChatSessionDetailSerializer,
    ChatMessageSerializer, NewChatMessageSerializer, NewChatSessionSerializer,
    UserAPIKeySerializer
)
from .ai_clients import get_ai_client, BaseAIClient # Import base for type hinting/exception handling


class UserAPIKeyViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing User API Keys.
    Users can Create, Read, Update, and Delete their own keys.
    """
    serializer_class = UserAPIKeySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Users can only see and manage their own API keys."""
        return UserAPIKey.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Ensure the key is associated with the requesting user
        serializer.save(user=self.request.user)

    # perform_update and perform_destroy are implicitly scoped by get_queryset

class ChatSessionViewSet(mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         mixins.DestroyModelMixin, # Allow deleting sessions
                         viewsets.GenericViewSet):
    """
    API endpoint for listing, retrieving, and managing chat sessions.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Users can only see their own chat sessions."""
        return ChatSession.objects.filter(user=self.request.user).prefetch_related('messages')

    def get_serializer_class(self):
        """ Use different serializers for list and detail views. """
        if self.action == 'list':
            return ChatSessionListSerializer
        elif self.action == 'retrieve':
            return ChatSessionDetailSerializer
        elif self.action == 'create_session': # Custom action uses its own serializer
             return NewChatSessionSerializer
        elif self.action == 'add_message': # Custom action uses its own serializer
             return NewChatMessageSerializer
        return ChatSessionDetailSerializer # Default

    # --- Custom Action for Creating a New Session ---
    @action(detail=False, methods=['post'], url_path='create', serializer_class=NewChatSessionSerializer)
    def create_session(self, request):
        """
        Creates a new chat session for the logged-in user.
        Requires 'ai_model_identifier' and optional 'title'.
        """
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        session = serializer.save() # create method in serializer handles user association
        # Return the detail view of the created session
        detail_serializer = ChatSessionDetailSerializer(session, context={'request': request})
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)

    # --- Custom Action for Adding a Message ---
    @action(detail=True, methods=['post'], url_path='message', serializer_class=NewChatMessageSerializer)
    def add_message(self, request, pk=None):
        """
        Adds a user message to a specific chat session and gets the AI response.
        """
        session = self.get_object() # Ensures session exists and belongs to user

        # 1. Validate incoming user message
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_message_content = serializer.validated_data['content']

        # 2. Save the user's message
        user_message = ChatMessage.objects.create(
            session=session,
            role='user',
            content=user_message_content
        )

        # 3. Prepare message history for AI
        # Retrieve all messages *including* the new user message
        messages_history = session.messages.order_by('timestamp')

        try:
            # 4. Get the appropriate AI client
            client = get_ai_client(request.user, session.ai_model_identifier)

            # 5. Call the AI API
            ai_response_content = client.get_completion(messages_history)

            # 6. Save the AI's response
            if ai_response_content:
                ai_message = ChatMessage.objects.create(
                    session=session,
                    role='assistant',
                    content=ai_response_content
                )
                # Update session's updated_at timestamp
                session.updated_at = timezone.now()
                session.save(update_fields=['updated_at'])

                # Return the newly added messages (user + assistant)
                new_messages_serializer = ChatMessageSerializer([user_message, ai_message], many=True)
                return Response(new_messages_serializer.data, status=status.HTTP_201_CREATED)
            else:
                # Handle cases where AI gives no response (e.g., safety filters, errors handled in client)
                 # Return only the user message if AI failed to respond meaningfully
                 # Frontend should ideally handle this possibility
                 user_message_serializer = ChatMessageSerializer(user_message)
                 # You might want a more specific error response here
                 return Response({
                        "detail": "AI did not return a response.",
                        "user_message": user_message_serializer.data
                    }, status=status.HTTP_200_OK) # Or maybe 503 Service Unavailable?

        except (ValueError, requests.exceptions.RequestException) as e:
            # Handle errors from client init (e.g., missing key) or API calls
            # Log the error server-side
            print(f"Error processing message for session {session.id}: {e}")
            # Return an error response to the client
            return Response(
                {"detail": f"Failed to get response from AI service: {str(e)}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE # 503 indicates backend issue talking to upstream service
            )
        except Exception as e:
             # Catch-all for unexpected errors
             print(f"Unexpected error processing message for session {session.id}: {e}")
             return Response(
                 {"detail": "An unexpected server error occurred."},
                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
             )

    # Standard retrieve, list, destroy actions are provided by the mixins and base viewset
    # Make sure retrieve uses ChatSessionDetailSerializer
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance) # Uses get_serializer_class -> ChatSessionDetailSerializer
        return Response(serializer.data)