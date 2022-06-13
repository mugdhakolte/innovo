"""Write all user related serializers here."""
from rest_framework import serializers

from api.models import *


class UserSerializer(serializers.ModelSerializer):
    """To serialize User."""

    projects_count = serializers.SerializerMethodField(read_only=True)
    full_name = serializers.SerializerMethodField(read_only=True)
    favourite_projects = serializers.SerializerMethodField(read_only=True)
    favourite_boards = serializers.SerializerMethodField(read_only=True)

    def get_projects_count(self, user):
        return ProjectMember.objects.filter(user_id=user.id).count()

    def get_full_name(self, user):
        return user.full_name

    def get_favourite_projects(self, user):
        return user.favourite_projects

    def get_favourite_boards(self, user):
        return user.favourite_boards


    class Meta:
        """Meta class for User model."""

        exclude = ('password', '_favourite_projects', '_favourite_boards')
        model = User


class ActivityUserSerializer(serializers.Serializer):

    user_id = serializers.SlugRelatedField(queryset=User.objects, slug_field='id', many=True)


class ActivityUserDetailSerializer(serializers.ModelSerializer):

    class Meta:
        """Meta class for User model."""
        fields = ['id', 'full_name', 'profile_pic']
        model = User


class UserRegistrationSerializer(serializers.Serializer):
    """A serializer for New User registration."""

    token = serializers.CharField()
    password = serializers.CharField()

    def validate_token(self, token):
        try:
            Token.objects.get(token=token)
        except Token.DoesNotExist as e:
            raise serializers.ValidationError('Invalid token provided')

