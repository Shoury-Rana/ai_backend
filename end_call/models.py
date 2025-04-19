from django.db import models

# Create your models here.

# end_call/models.py
import os
from django.conf import settings
from django.db import models
from cryptography.fernet import Fernet
from django.core.exceptions import ValidationError

# Ensure FIELD_ENCRYPTION_KEY is set in settings, loaded from environment
try:
    # Use Django settings to access the key, assuming it's loaded there
    # Load from environment variable directly if preferred
    key = settings.FIELD_ENCRYPTION_KEY
    if isinstance(key, str):
        key = key.encode() # Ensure key is bytes
    fernet = Fernet(key)
except AttributeError:
    raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY must be set in Django settings.")


# --- API Key Management ---
# Choices for supported services
SERVICE_CHOICES = [
    ('openai', 'OpenAI'),
    ('anthropic', 'Anthropic'),
    ('google', 'Google Gemini'),
    # Add more services here as needed
]

class UserAPIKey(models.Model):
    """ Stores API keys provided by users for specific AI services. """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys')
    service_name = models.CharField(max_length=50, choices=SERVICE_CHOICES, help_text="The AI service this key is for (e.g., 'openai').")
    encrypted_api_key = models.BinaryField(help_text="The encrypted API key.") # Store encrypted key as bytes
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'service_name') # One key per service per user
        verbose_name = "User API Key"
        verbose_name_plural = "User API Keys"

    def set_api_key(self, raw_key):
        """Encrypts and sets the API key."""
        if not raw_key:
             raise ValueError("API key cannot be empty.")
        self.encrypted_api_key = fernet.encrypt(raw_key.encode())

    def get_api_key(self):
        """Decrypts and returns the API key."""
        if not self.encrypted_api_key:
            return None
        try:
            return fernet.decrypt(self.encrypted_api_key).decode()
        except Exception as e:
            # Handle potential decryption errors (e.g., key change, corrupted data)
            print(f"Error decrypting key for user {self.user.id}, service {self.service_name}: {e}")
            # Decide error handling: return None, raise exception, log critical error?
            return None # Returning None might be safest default

    # Prevent direct access/modification of encrypted_api_key via standard save
    def save(self, *args, **kwargs):
        if not self.pk and not hasattr(self, '_raw_api_key_to_encrypt'):
             raise ValidationError("Use set_api_key() to provide the key before saving a new UserAPIKey.")
        if hasattr(self, '_raw_api_key_to_encrypt'):
             self.set_api_key(self._raw_api_key_to_encrypt)
             del self._raw_api_key_to_encrypt # Clean up temporary attribute
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.user.username}'s {self.get_service_name_display()} Key"


# --- Chat Models ---

# Define available AI models users can choose
# Format: 'service_model', 'User Friendly Name'
# This helps map user selection to the correct service and potentially specific model variant
AI_MODEL_CHOICES = [
    ('openai_gpt-3.5-turbo', 'OpenAI GPT-3.5 Turbo'),
    ('openai_gpt-4', 'OpenAI GPT-4'),
    ('openai_gpt-4-turbo', 'OpenAI GPT-4 Turbo'),
    ('anthropic_claude-3-opus', 'Anthropic Claude 3 Opus'),
    ('anthropic_claude-3-sonnet', 'Anthropic Claude 3 Sonnet'),
    ('anthropic_claude-3-haiku', 'Anthropic Claude 3 Haiku'),
    ('google_gemini-pro', 'Google Gemini Pro'),
    ('google_gemini-2.5-pro-preview-03-25', 'google_gemini-2.5-pro-preview-03-25'),
    ('google_gemini-2.0-flash', 'Gemini 2.0 Flash'),
    # Add more models as needed
]

class ChatSession(models.Model):
    """ Represents a single conversation thread. """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_sessions')
    title = models.CharField(max_length=200, blank=True, default="New Chat")
    ai_model_identifier = models.CharField(
        max_length=100,
        choices=AI_MODEL_CHOICES,
        help_text="The specific AI model used for this session."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at'] # Show most recent chats first

    def __str__(self):
        return f"Chat ({self.id}) - {self.title} ({self.user.username}) using {self.get_ai_model_identifier_display()}"

    def get_service_name(self):
        """ Extracts the service name (e.g., 'openai') from the identifier. """
        if self.ai_model_identifier:
            return self.ai_model_identifier.split('_')[0]
        return None


class ChatMessage(models.Model):
    """ Stores a single message within a chat session. """
    ROLE_CHOICES = [
        ('system', 'System'), # Optional: For initial instructions to the AI
        ('user', 'User'),
        ('assistant', 'Assistant'), # AI's response
    ]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    # Optional: Store token counts, raw response, etc. if needed
    # raw_response = models.JSONField(null=True, blank=True)
    # prompt_tokens = models.IntegerField(null=True, blank=True)
    # completion_tokens = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['timestamp'] # Ensure messages are ordered correctly

    def __str__(self):
        return f"{self.get_role_display()} ({self.session.id}) @ {self.timestamp:%Y-%m-%d %H:%M}"