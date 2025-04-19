from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken # Import RefreshToken

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True, label="Confirm Password")
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2') # Add other fields like first_name, last_name if needed

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        # Ensure email is unique (Model field already enforces this, but explicit check is fine)
        if User.objects.filter(email=attrs['email']).exists():
             raise serializers.ValidationError({"email": "Email already exists."})
        # Ensure username is unique (Model field already enforces this)
        if User.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError({"username": "Username already exists."})

        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
            # Add other fields here if they are in Meta.fields and validated_data
            # first_name=validated_data.get('first_name', ''),
            # last_name=validated_data.get('last_name', '')
        )
        # No need to explicitly call user.set_password() because create_user handles hashing
        return user

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying User information (used in /me endpoint)
    """
    class Meta:
        model = User
        # Define fields to expose via the API
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined')
        # Ensure sensitive fields like password are not included
        read_only_fields = ('id', 'is_staff', 'date_joined') # Fields not editable via this serializer


# No specific serializer needed for SimpleJWT's built-in views (login/refresh)
# unless you want to customize their payload.

# Serializer for Logout (Blacklisting)
class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    default_error_messages = {
        'bad_token': ('Token is invalid or expired')
    }

    def validate(self, attrs):
        self.token = attrs['refresh']
        return attrs

    def save(self, **kwargs):
        try:
            RefreshToken(self.token).blacklist()
        except Exception: # Catch specific exceptions if needed (e.g., TokenError from simplejwt)
             # You might want to log this exception
             # Consider if you want to raise validation error even if token is already blacklisted or invalid
             # For simplicity, we might just proceed silently or raise a generic error
             # raise serializers.ValidationError({'detail': self.error_messages['bad_token']})
             pass # Silently ignore errors during blacklist, as the goal is achieved (token can't be used)