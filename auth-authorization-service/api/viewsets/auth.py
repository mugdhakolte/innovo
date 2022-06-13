"""Module for Authentication services APIs."""

from django.contrib.auth import authenticate

from rest_framework import status
from rest_framework.views import Response
from rest_framework.viewsets import ViewSet
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import *
from api.permissions import *
from api.serializers.auth import *
from api.signal_receivers import create_token
from api.inter_service_communicator import *



class LoginViewSet(ViewSet):
    """Check email and password and returns an auth token."""

    permission_classes = (AllowAny,)

    def create(self, request):
        """
        For logging user.

        :param request:
        :return:
        """
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            email = request.data['email']
            password = request.data['password']
            user = authenticate(email=email, password=password)
            if user:
                refresh = RefreshToken.for_user(user)
                return Response(
                    {
                        'message': 'User loggedin successfully',
                        'data': {
                            'refresh_token': str(refresh),
                            'access_token': str(refresh.access_token),
                            'first_name': user.first_name,
                            'last_name': user.last_name,
                            'email': user.email,
                            'id': user.id,
                            'full_name': user.full_name,
                            'profile_pic': user.profile_pic.url if user.profile_pic else "",
                            'is_superuser': user.is_superuser
                        },
                    },
                    status=status.HTTP_200_OK,
                )
        return Response({'message': 'Please enter valid credentials.'}, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordViewSet(ViewSet):
    """Class for forgot password."""

    permission_classes = (AllowAny,)

    def create(self, request):
        """
        For creating password for forgot password.

        :param request:
        :return: response
        """
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.data['email']
        user = User.objects.get(email=email)
        token = create_token(user, 'forgot_password')
        notification_service = NotificationService()
        notification_service.send_forgot_password_email(user, token)
        return Response({'message': 'Password reset link successfully sent to your email'},
                        status=status.HTTP_200_OK)


class ResetPasswordViewSet(ViewSet):
    """Class to reset password."""

    permission_classes = (AllowAny,)

    def create(self, request):
        """
        To reset password.

        :param request:
        :return: response
        """
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_password = request.data['new_password']
        token = request.data['token']
        token = Token.objects.get(token=token)
        user = token.user
        user.set_password(new_password)
        user.save()
        token.delete()
        return Response({'message': 'Successfully updated the password.' }, status=status.HTTP_200_OK)


class ChangePasswordViewSet(ViewSet):
    """Class to change password."""

    permission_classes = (IsAuthenticated,)

    def create(self, request):
        """
        To change password.

        :param request:
        :return:response
        """
        serializer_class = ChangePasswordSerializer(data=request.data)
        serializer_class.is_valid(raise_exception=True)
        old_password = request.data.get('old_password')
        if request.user.check_password(old_password):
            new_password = request.data.get('new_password')
            request.user.set_password(new_password)
            request.user.save()
            return Response({'message': 'Password has been changed'}, status=status.HTTP_200_OK )
        else:
            return Response({'message': "Old password is not correct"}, status=status.HTTP_400_BAD_REQUEST)


class HasPermissionViewSet(ViewSet, BaseHasProjectPermission):

    http_method_names = ['post']
    permission_classes = (IsAuthenticated,)
    serializer_class = HasPermissionSerializer

    def create(self, request):
        """
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        project_id = serializer.data.get('project_id')
        permission_code = serializer.data.get('permission_code')
        has_permission = self._has_permission(project_id, request, permission_code)
        return Response({'has_permission': has_permission}, status=status.HTTP_200_OK)


class IsProjectAdminViewSet(ViewSet, HasProjectPermission):

    http_method_names = ['post']
    permission_classes = (IsAuthenticated,)
    serializer_class = IsProjectAdminSerializer

    def create(self, request):
        """
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        project_id = serializer.data.get('project_id')
        is_admin = request.user.is_superuser
        if not is_admin:
            project = Project.objects.get(id=project_id)
            is_admin = project.is_admin(request.user)
        return Response({'is_admin' : is_admin}, status=status.HTTP_200_OK)
