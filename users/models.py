from django.db import models

# Create your models here.

class Keys(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='keys')
    model_name = models.CharField(max_length=255)
    key_value = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)