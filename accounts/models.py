from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=120, blank=True)
    role = models.CharField(
        max_length=20,
        choices=[
            ('admin', 'Admin'),
            ('reviewer', 'Reviewer'),
            ('user', 'User'),
        ],
        default='user',
    )
    theme_preference = models.CharField(
        max_length=10,
        choices=[('light', 'Light'), ('dark', 'Dark')],
        default='light',
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email
