"""Serializer for related to auth.
Used for validations and serialization related to auth.
"""
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers

from api.models import *
from api.mixins import EmailValidatorMixin


class LoginSerializer(serializers.Serializer, EmailValidatorMixin):
    """To validate the login credentials."""

    password = serializers.CharField(trim_whitespace=False)
    email = serializers.EmailField(trim_whitespace=False)


class ForgotPasswordSerializer(serializers.Serializer, EmailValidatorMixin):
    """A serializer for forgot password."""


    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    """A serializer for change password."""

    token = serializers.SlugRelatedField(queryset=Token.objects, slug_field='token')
    new_password = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    """A serializer for change password."""

    old_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)
    confirm_password = serializers.CharField(trim_whitespace=False)

    def validate(self, validated_data):
        """To validate on new and old password."""

        old_password = validated_data.get('old_password')
        new_password = validated_data.get('new_password')
        confirm_password = validated_data.get('confirm_password')
        if old_password == new_password:
            msg = _('Old Password and New Password should not be same')
            raise serializers.ValidationError(msg, code='authorization')
        if new_password != confirm_password:
            msg = _('New Password and Confirm Password does not match')
            raise serializers.ValidationError(msg, code='authorization')
        return validated_data


class HasPermissionSerializer(serializers.Serializer):

    project_id = serializers.PrimaryKeyRelatedField(queryset=Project.objects)
    permission_code = serializers.SlugRelatedField(queryset=Permission.objects, slug_field='code')


class IsProjectAdminSerializer(serializers.Serializer):

    project_id = serializers.PrimaryKeyRelatedField(queryset=Project.objects)
