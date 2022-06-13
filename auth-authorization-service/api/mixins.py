"""Mixins for auth."""

from google.cloud import storage

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from rest_framework import status
from rest_framework import serializers
from rest_framework.views import Response

from api.models import User


class EmailValidatorMixin:
    """
    To validate email.

    For validation if user with given email exists and user is active.
    """

    def validate_email(self, email):
        """To validate if email exists."""

        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                raise serializers.ValidationError(_('User is not active.'))
        except User.DoesNotExist:
            raise serializers.ValidationError(_('Invalid email id'))
        return email


class DeleteFileMixin(object):
    """To delete file"""

    def destroy(self, request, pk=None):
        instance = self.get_object()
        try:
            self.delete_blob(str(instance.cover_image).encode('utf-8'))
        except Exception as e:
            pass
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete_blob(self, blob_name):
        bucket_name = settings.GS_BUCKET_NAME
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.delete()
