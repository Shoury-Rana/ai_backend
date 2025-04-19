# end_call/ai_clients.py
import os
import requests
from django.conf import settings
from .models import UserAPIKey
from abc import ABC, abstractmethod
import json

# --- Helper Function to Get API Key ---

def get_api_key_for_service(user, service_name):
    """
    Retrieves the API key for a given service and user.
    Prioritizes user-specific key, falls back to system key.
    """
    # 1. Try UserAPIKey model
    try:
        user_key_entry = UserAPIKey.objects.get(user=user, service_name=service_name)
        decrypted_key = user_key_entry.get_api_key()
        if decrypted_key:
            # print(f"Using user-provided key for {service_name}") # Debugging
            return decrypted_key
    except UserAPIKey.DoesNotExist:
        pass # No user key found, proceed to system key
    except Exception as e:
        print(f"Error retrieving or decrypting user key for {service_name}: {e}")
        # Decide: fall back or raise? Falling back might be safer initially.

    # 2. Try System Key from Environment/Settings
    system_key_var_name = f"{service_name.upper()}_API_KEY" # e.g., OPENAI_API_KEY
    system_key = getattr(settings, system_key_var_name, os.getenv(system_key_var_name))

    if system_key:
        # print(f"Using system key for {service_name}") # Debugging
        return system_key

    # 3. No key found
    print(f"Warning: No API key found for service '{service_name}' for user {user.id} or system.")
    return None

# --- Base Client Class ---

class BaseAIClient(ABC):
    """ Abstract base class for AI API clients. """
    def __init__(self, user, model_identifier):
        self.user = user
        self.model_identifier = model_identifier
        self.service_name = self._extract_service_name(model_identifier)
        self.api_key = get_api_key_for_service(user, self.service_name)
        if not self.api_key:
             raise ValueError(f"API Key for service '{self.service_name}' is missing.")

    def _extract_service_name(self, model_identifier):
        # Assumes format 'service_model'
        return model_identifier.split('_')[0]

    def _get_model_name(self):
         # Assumes format 'service_model'
         parts = self.model_identifier.split('_', 1)
         return parts[1] if len(parts) > 1 else None

    @abstractmethod
    def format_messages(self, messages_queryset):
        """ Formats Django ChatMessage queryset into API-specific format. """
        pass

    @abstractmethod
    def call_api(self, formatted_messages):
        """ Makes the actual HTTP request to the AI API. """
        pass

    @abstractmethod
    def parse_response(self, response_data):
        """ Extracts the assistant's message content from the API response. """
        pass

    def get_completion(self, messages_queryset):
        """ Orchestrates formatting, calling, and parsing. """
        formatted_messages = self.format_messages(messages_queryset)
        if not formatted_messages:
            raise ValueError("Message formatting resulted in empty payload.")
        raw_response = self.call_api(formatted_messages)
        return self.parse_response(raw_response)


# --- Specific Client Implementations ---

class OpenAIClient(BaseAIClient):
    BASE_URL = "https://api.openai.com/v1/chat/completions"

    def format_messages(self, messages_queryset):
        # OpenAI uses a list of {'role': '...', 'content': '...'}
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages_queryset if msg.role in ['user', 'assistant', 'system'] # Filter valid roles
        ]

    def call_api(self, formatted_messages):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._get_model_name(), # e.g., 'gpt-4'
            "messages": formatted_messages,
            # Add other parameters like temperature, max_tokens etc. if needed
        }
        # print("OpenAI Payload:", json.dumps(payload, indent=2)) # Debugging
        try:
            response = requests.post(self.BASE_URL, headers=headers, json=payload, timeout=90) # Increased timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error calling OpenAI API: {e}")
            if e.response is not None:
                print(f"Response status: {e.response.status_code}")
                try:
                    print(f"Response body: {e.response.json()}")
                except json.JSONDecodeError:
                    print(f"Response body: {e.response.text}")
            raise  # Re-raise the exception after logging

    def parse_response(self, response_data):
        # print("OpenAI Response:", json.dumps(response_data, indent=2)) # Debugging
        try:
            # Check for errors in the response body
            if 'error' in response_data:
                error_details = response_data['error']
                print(f"OpenAI API Error: {error_details.get('message', 'Unknown error')}")
                # Optionally, raise a custom exception here
                raise ValueError(f"OpenAI API Error: {error_details.get('message', 'Unknown error')}")

            content = response_data['choices'][0]['message']['content']
            # You might want to extract other info like token usage here
            # usage = response_data.get('usage')
            return content.strip() if content else None
        except (KeyError, IndexError, TypeError) as e:
            print(f"Error parsing OpenAI response: {e}. Response data: {response_data}")
            raise ValueError("Failed to parse response from OpenAI API.")


class AnthropicClient(BaseAIClient):
    BASE_URL = "https://api.anthropic.com/v1/messages"

    def format_messages(self, messages_queryset):
        # Anthropic uses a list of {'role': '...', 'content': '...'}
        # The first message must be 'user'. System prompts go in a separate 'system' parameter.
        formatted = []
        system_prompt = None
        for msg in messages_queryset:
            if msg.role == 'system':
                if system_prompt is None: # Use the first system message found
                     system_prompt = msg.content
                continue # Skip adding system messages to the main list
            if msg.role in ['user', 'assistant']:
                 formatted.append({"role": msg.role, "content": msg.content})

        if not formatted or formatted[0]['role'] != 'user':
             # Prepend a dummy user message if needed, or ideally ensure FE/BE logic starts correctly
             # Or raise an error if the conversation structure is invalid for Claude
             print("Warning: Anthropic requires the first message to be from 'user'.")
             # raise ValueError("Anthropic requires the first message to be from 'user'.")

        return {"messages": formatted, "system": system_prompt}


    def call_api(self, formatted_data):
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01", # Check for latest recommended version
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._get_model_name(), # e.g., 'claude-3-opus-20240229'
            "messages": formatted_data["messages"],
            "max_tokens": 1024, # Anthropic requires max_tokens
            # Add system prompt if present
            **({"system": formatted_data["system"]} if formatted_data["system"] else {})
            # Add other parameters like temperature etc. if needed
        }
        # print("Anthropic Payload:", json.dumps(payload, indent=2)) # Debugging
        try:
            response = requests.post(self.BASE_URL, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error calling Anthropic API: {e}")
            if e.response is not None:
                print(f"Response status: {e.response.status_code}")
                try:
                    print(f"Response body: {e.response.json()}")
                except json.JSONDecodeError:
                    print(f"Response body: {e.response.text}")
            raise

    def parse_response(self, response_data):
        # print("Anthropic Response:", json.dumps(response_data, indent=2)) # Debugging
        try:
             # Check for errors
             if response_data.get('type') == 'error':
                 error_details = response_data.get('error', {})
                 print(f"Anthropic API Error: {error_details.get('message', 'Unknown error')}")
                 raise ValueError(f"Anthropic API Error: {error_details.get('message', 'Unknown error')}")

             # Response structure: content is a list of blocks, usually one text block
             content_block = response_data['content'][0]
             if content_block['type'] == 'text':
                 return content_block['text'].strip()
             else:
                 print(f"Warning: Received unexpected content block type from Anthropic: {content_block['type']}")
                 return None # Or handle other block types if necessary
        except (KeyError, IndexError, TypeError) as e:
            print(f"Error parsing Anthropic response: {e}. Response data: {response_data}")
            raise ValueError("Failed to parse response from Anthropic API.")

class GoogleClient(BaseAIClient):
    # Using v1beta for generative model API
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def _get_model_name_for_api(self):
        # Google API uses slightly different model names
        model_map = {
             'gemini-2.0-flash': 'gemini-2.0-flash',
             'gemini-2.5-pro-preview-03-25': 'gemini-2.5-pro-preview-03-25',
             'gemini-2.0-flash': 'gemini-2.0-flash',
             # Add mappings for other Google models if needed
        }
        internal_name = self._get_model_name()
        return model_map.get(f"google_{internal_name}", internal_name) # Default to internal name if no mapping

    def format_messages(self, messages_queryset):
         # Google Gemini API uses 'contents' list with alternating 'user' and 'model' roles.
         # It doesn't have a dedicated 'system' role in the main content; system instructions might be handled differently depending on the exact use case (or potentially prepended to the first user message).
         contents = []
         current_content = None
         last_role = None

         for msg in messages_queryset:
             if msg.role == 'user':
                 # Start a new user turn
                 current_content = {"role": "user", "parts": [{"text": msg.content}]}
                 contents.append(current_content)
                 last_role = 'user'
             elif msg.role == 'assistant':
                 # This should follow a user message
                 if last_role == 'user':
                      current_content = {"role": "model", "parts": [{"text": msg.content}]}
                      contents.append(current_content)
                      last_role = 'model'
                 else:
                      # Handle consecutive assistant messages if needed (e.g., merge or log warning)
                      print(f"Warning: Consecutive assistant messages detected for Google API - merging content for message ID {msg.id}")
                      if contents and contents[-1]['role'] == 'model':
                           contents[-1]['parts'][0]['text'] += f"\n{msg.content}"
                      else:
                          # If the sequence is broken (e.g., starts with assistant), handle appropriately
                          print(f"Warning: Unexpected message sequence for Google API. Role '{msg.role}' cannot directly follow '{last_role}'. Skipping message {msg.id}.")


             elif msg.role == 'system':
                 # System prompts are often handled via a specific parameter or prepended.
                 # For basic chat, we might ignore them here or prepend to the *first* user message.
                 print(f"Warning: System message (ID: {msg.id}) encountered. Google Gemini API handles system prompts differently. It will be ignored in this basic implementation.")
                 # TODO: Potentially implement system prompt handling via `system_instruction` parameter if API supports it well for multi-turn.

         # Ensure the last message isn't from the model (API expects user prompt)
         # This shouldn't happen if we're calling this *before* sending to the API
         if contents and contents[-1]['role'] == 'model':
             print("Warning: Last message in history for Google API is from the model. This might lead to errors.")

         return {"contents": contents}


    def call_api(self, formatted_data):
        model_name = self._get_model_name_for_api() # e.g., 'gemini-pro'
        url = self.BASE_URL.format(model=model_name)
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = formatted_data # Contains the 'contents' list
        # Add generationConfig if needed (temperature, max output tokens, etc.)
        # payload["generationConfig"] = { "temperature": 0.7, "maxOutputTokens": 1000 }

        # print("Google Payload:", json.dumps(payload, indent=2)) # Debugging
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error calling Google API: {e}")
            if e.response is not None:
                print(f"Response status: {e.response.status_code}")
                try:
                    print(f"Response body: {e.response.json()}")
                except json.JSONDecodeError:
                    print(f"Response body: {e.response.text}")
            raise


    def parse_response(self, response_data):
        # print("Google Response:", json.dumps(response_data, indent=2)) # Debugging
        try:
             # Check for errors indicated by the absence of 'candidates'
             if not response_data.get('candidates'):
                 error_info = response_data.get('error', {})
                 message = error_info.get('message', 'Unknown Google API error, response did not contain candidates.')
                 print(f"Google API Error: {message}")
                 # Check for prompt feedback (content filtering, safety)
                 prompt_feedback = response_data.get('promptFeedback')
                 if prompt_feedback:
                      print(f"Google API Prompt Feedback: {prompt_feedback}")
                      block_reason = prompt_feedback.get('blockReason')
                      if block_reason:
                           message += f" Blocked due to: {block_reason}."
                           safety_ratings = prompt_feedback.get('safetyRatings', [])
                           message += f" Safety Ratings: {safety_ratings}"
                 raise ValueError(f"Google API Error: {message}")

             # Extract text from the first candidate's content parts
             candidate = response_data['candidates'][0]
             # Check finish reason if needed (e.g., 'STOP', 'MAX_TOKENS', 'SAFETY')
             finish_reason = candidate.get('finishReason')
             if finish_reason not in ['STOP', 'MAX_TOKENS', None]: # None if streaming, STOP is normal
                 print(f"Warning: Google API finish reason: {finish_reason}")
                 # Handle safety blocks here if needed based on finishReason == 'SAFETY'
                 if finish_reason == 'SAFETY':
                     safety_ratings = candidate.get('safetyRatings', [])
                     raise ValueError(f"Google API response blocked due to safety concerns. Ratings: {safety_ratings}")


             content = candidate['content']
             # Content parts is a list, typically with one text part
             text_parts = [part['text'] for part in content.get('parts', []) if 'text' in part]
             full_text = "\n".join(text_parts)

             return full_text.strip() if full_text else None
        except (KeyError, IndexError, TypeError) as e:
            print(f"Error parsing Google response: {e}. Response data: {response_data}")
            raise ValueError("Failed to parse response from Google API.")


# --- Client Factory ---

def get_ai_client(user, model_identifier):
    """ Factory function to get the appropriate AI client instance. """
    service_name = model_identifier.split('_')[0]

    if service_name == 'openai':
        return OpenAIClient(user, model_identifier)
    elif service_name == 'anthropic':
        return AnthropicClient(user, model_identifier)
    elif service_name == 'google':
        return GoogleClient(user, model_identifier)
    # Add other clients here
    else:
        raise ValueError(f"Unsupported AI service: {service_name}")