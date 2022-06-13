import datetime

from django.dispatch import receiver
from django.db.models.signals import post_save
from django.utils.crypto import get_random_string

from api.models import *
from api.inter_service_communicator import NotificationService


@receiver(post_save, sender=User)
def send_user_registration_invite_email(sender, instance, created, **kwargs):
    if created and not instance.is_superuser:
        token = create_token(instance, 'registration')
        notification_service = NotificationService()
        notification_service.send_user_registration_invite_email(instance, token)


@receiver(post_save, sender=ProjectMember)
def send_project_invitation_email(sender, instance, created, **kwargs):
    if created:
        notification_service = NotificationService()
        notification_service.send_project_invitation_email(instance.user, instance.project)


def create_token(user, action):
    """To create random token in database."""

    token = get_random_string(length=32)

    expires_at = datetime.datetime.now() + datetime.timedelta(days=1)

    token = Token.objects.create(
        user=user, action=action, token=token,
        expires_at=expires_at,

    )
    return token