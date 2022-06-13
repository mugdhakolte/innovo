# -*- coding: utf-8 -*-
"""User related views."""
from django.db import transaction

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet, ViewSet

from api.models import *
from api.permissions import *
from api.serializers.user import *


class UserViewSet(ModelViewSet):
    """For user operations."""

    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action in ('retrieve', 'list'):
            return (IsAuthenticated(), )
        else:
            return (IsSuperUser(), )

    @action(methods=["POST"], detail=True, url_path='add-board-to-favourites',
            url_name='add-board-to-favourites')
    def add_board_to_favourites(self, request, pk=None):
        user = request.user
        favourite_boards = user.favourite_boards
        favourite_boards.append(pk)
        user.favourite_boards = favourite_boards
        user.save()
        return Response({}, status=status.HTTP_200_OK)

    @action(methods=["POST"], detail=True,
            url_path='remove-board-from-favourites',
            url_name='remove_board_from_favourites')
    def remove_board_from_favourites(self, request, pk=None):
        user = request.user
        favourite_boards = user.favourite_boards
        favourite_boards.remove(pk)
        user.favourite_boards = favourite_boards
        user.save()
        return Response({}, status=status.HTTP_200_OK)

    @action(methods=["POST"], detail=False, url_path='get-user-data', url_name='get_user_data')
    def get_user_data(self, request, pk=None):
        serializer = ActivityUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        users = User.objects.filter(id__in=serializer.data['user_id'])
        serializer = ActivityUserDetailSerializer(instance=users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RegisterUserViewSet(ViewSet):
    """
    To complete registration and check existence of user created by Admin user.

    Creates the user if the token is validated.
    """
    permission_classes = (AllowAny,)

    def create(self, request):
        """
        To create users registration.

        :param request:
        :input token first_name last_name password
        :return: relevant response if created or not found
        """
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = request.data.get('token')
        password = request.data.get('password')
        user_token = Token.objects.get(token=token)
        user_token.user.set_password(password)
        user_token.user.is_active = True
        user_token.user.save()
        user_token.delete()
        return Response({'message': 'User registered successfully.'},
                        status=status.HTTP_200_OK)


class MyProfileView(APIView):
    """
    To get the current user details.

    Returns the authenticated user's details.
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user_data = UserSerializer(request.user).data
        return Response(user_data, status=status.HTTP_200_OK)
