# end_call/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ChatSession, ChatMessage, UserAPIKey, SERVICE_CHOICES, AI_MODEL_CHOICES

User = get_user_model()


class UserAPIKeySerializer(serializers.ModelSerializer):
    # Use CharField for input/output, handle encryption/decryption internally
    api_key = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    service_name = serializers.ChoiceField(choices=SERVICE_CHOICES)
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = UserAPIKey
        fields = ['id', 'user', 'service_name', 'api_key', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def create(self, validated_data):
        # Pop the raw key and use the model's setter method
        raw_key = validated_data.pop('api_key')
        # Pass the raw key temporarily for the save method to handle
        instance = UserAPIKey(**validated_data)
        instance._raw_api_key_to_encrypt = raw_key
        instance.save()
        return instance

    def update(self, instance, validated_data):
        # Allow updating the key
        raw_key = validated_data.pop('api_key', None)
        if raw_key:
             # Use the setter method to handle encryption
             instance.set_api_key(raw_key)

        # Update other fields if necessary (service_name usually shouldn't change)
        instance.service_name = validated_data.get('service_name', instance.service_name)
        # Note: user should not be changed here

        instance.save()
        return instance

    def to_representation(self, instance):
        # Exclude the key when reading back (even the encrypted one)
        # Only show metadata
        representation = super().to_representation(instance)
        representation.pop('api_key', None) # Remove api_key field from output
        representation['service_display'] = instance.get_service_name_display()
        return representation


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'session', 'role', 'content', 'timestamp']
        read_only_fields = ['id', 'session', 'timestamp'] # Role/content set internally


class ChatSessionListSerializer(serializers.ModelSerializer):
    """Serializer for listing chat sessions."""
    ai_model_display = serializers.CharField(source='get_ai_model_identifier_display', read_only=True)

    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'ai_model_identifier', 'ai_model_display', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'ai_model_display']


class ChatSessionDetailSerializer(serializers.ModelSerializer):
    """Serializer for viewing a single chat session with its messages."""
    messages = ChatMessageSerializer(many=True, read_only=True)
    ai_model_display = serializers.CharField(source='get_ai_model_identifier_display', read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True) # Show user ID

    class Meta:
        model = ChatSession
        fields = [
            'id', 'user', 'title', 'ai_model_identifier', 'ai_model_display',
            'created_at', 'updated_at', 'messages'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'messages', 'ai_model_display']


class NewChatSessionSerializer(serializers.Serializer):
    """Serializer for creating a new chat session."""
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    ai_model_identifier = serializers.ChoiceField(choices=AI_MODEL_CHOICES, required=True)

    def create(self, validated_data):
        user = self.context['request'].user
        title = validated_data.get('title') or f"Chat with {dict(AI_MODEL_CHOICES).get(validated_data['ai_model_identifier'], 'AI')}"
        session = ChatSession.objects.create(
            user=user,
            title=title,
            ai_model_identifier=validated_data['ai_model_identifier']
        )
        return session


class NewChatMessageSerializer(serializers.Serializer):
    """Serializer for receiving a new user message."""
    content = serializers.CharField(required=True, allow_blank=False)