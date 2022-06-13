"""Urls for authentication service APIs."""

from django.conf.urls import url

from rest_framework.routers import DefaultRouter

from api.viewsets import *


router = DefaultRouter()

# Auth Routes

router.register('login', LoginViewSet, base_name='login')
router.register('registration', RegisterUserViewSet, base_name='registration')
router.register('reset-password', ResetPasswordViewSet, base_name='reset_password')
router.register('change-password', ChangePasswordViewSet, base_name='change_password')
router.register('forgot-password', ForgotPasswordViewSet, base_name='forgot_password')


# User Routes
router.register('user', UserViewSet, base_name='user_operations')

# Project Routes
router.register('project', ProjectViewSet, base_name='project')
router.register('project-type', ProjectTypeViewSet, base_name='project_type')
router.register('project-member', ProjectMemberViewSet, base_name='project_member')
router.register('country', CountryViewSet, base_name='country')
router.register('state', StateViewSet, base_name='state')
router.register('city', CityViewSet, base_name='city')

# Permission Routes
router.register('has-permission', HasPermissionViewSet, base_name='permission')
router.register('is-project-admin', IsProjectAdminViewSet, base_name='projectadminpermission')

#Page Routes
router.register('page', PageViewSet, base_name='page')

urlpatterns = router.urls

urlpatterns.append(url("my-profile", MyProfileView.as_view()),)
