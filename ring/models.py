from django.contrib.auth.models import User, Group
from django.db import models

class Ring(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"Ring {self.name.title()}"

class RingKey(models.Model):
    ring = models.OneToOneField(Ring, on_delete=models.CASCADE)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    encrypted_key = models.CharField(max_length=255)  # base64_encrypted_key

    class Meta:
        unique_together = ('ring', 'user')

    def __str__(self):
        return f"RingKey for {self.ring.name.title()}:{self.user.username}"

class UserKey(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    public_key = models.TextField()  # JWK format (JSON Web Key)

    def __str__(self):
        return f"UserKey for {self.user.username}"
