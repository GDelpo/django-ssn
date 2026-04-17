"""
Django signals for accounts app.

Handle events like user creation, password change, etc.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import User

logger = logging.getLogger("accounts")


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """
    Signal handler for user creation/update.

    Can be extended for additional logic like:
    - Sending welcome emails
    - Creating user profiles
    - Logging user creation
    """
    if created:
        logger.info(f"✅ New user registered: {instance.email}")
