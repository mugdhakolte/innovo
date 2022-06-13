# -*- coding: utf-8 -*-
"""For projects related views."""
from opencage.geocoder import OpenCageGeocode
from django.shortcuts import get_object_or_404

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated, AllowAny

from api.models import *
from api.mixins import *
from api.filters import *
from api.permissions import *
from api.serializers.project import *
from api.inter_service_communicator import *


class ProjectTypeViewSet(ModelViewSet):
    """Class for project types APIs."""

    serializer_class = ProjectTypeSerializer
    queryset = ProjectType.objects.all()

    def get_permissions(self):
        if self.action == 'list':
            return (IsAuthenticated(), )
        else:
            return (IsSuperUser(), )


class CountryViewSet(ModelViewSet):
    """Class for project country APIs"""

    serializer_class = CountrySerializer
    queryset = Country.objects.all()

    def get_permissions(self):
        if self.action == 'list':
            return (IsAuthenticated(), )
        else:
            return (IsSuperUser(), )


class StateViewSet(ModelViewSet):
    """Class for project city and state APIs"""

    serializer_class = StateSerializer
    queryset = State.objects.all()

    def get_permissions(self):
        if self.action == 'list':
            return (IsAuthenticated(), )
        else:
            return (IsSuperUser(), )


class CityViewSet(ModelViewSet):
    """Class for project city and state APIs"""

    serializer_class = CitySerializer
    queryset = City.objects.all()

    def get_permissions(self):
        if self.action == 'list':
            return (IsAuthenticated(), )
        else:
            return (IsSuperUser(), )


class ProjectViewSet(DeleteFileMixin, ModelViewSet):
    """Class for Project APIs."""

    serializer_class = ProjectSerializer
    queryset = Project.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ProjectFilter

    def get_permissions(self):
        if self.action in ('list', 'add_to_favourite', 'remove_from_favourite'):
            return (IsAuthenticated(), )
        elif self.action == 'get_project_detail':
            return (AllowAny(),)
        elif self.action == 'create':
            return (IsSuperUser(), )
        else:
            action_permissions_map = {
                'retrieve': 'can_view_project_details',
                'update': 'can_edit_project_details',
                'partial_update': 'can_edit_project_details',
                'destroy': 'can_delete_project_details'
            }
            return (HasProjectPermission(action_permissions_map[self.action]), )

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Project.objects.all()
        else:
            project_ids = self.request.user.user_projects.all().values_list("project_id", flat=True)
            return Project.objects.filter(id__in=project_ids)

    def create(self, request, *args, **kwargs):
        if request.data.get('address'):
            city = self._get_city_state_country(request.data.get('address'))
            if city:
                request.data['city'] = city.id
                res = super(ProjectViewSet, self).create(request, *args, **kwargs)
                return res
        else:
            return Response({'detail': 'Error please, try again with different address'}, status=status.HTTP_400_BAD_REQUEST)

    def _get_city_state_country(self, address):
        """Get City for project."""
        city_data = {}

        key = "1a492b842a45475d89f704581aa5237c"
        geocoder = OpenCageGeocode(key)
        results = geocoder.geocode(address)
        components = results[0].get('components')
        city_data['country'] = components.get('country')
        country, created= Country.objects.get_or_create(name=components.get('country'))
        if created:
            country = country
        if country:
            if not components.get('state'):
                state, created = State.objects.get_or_create(name=components.get('country'), country=country)
                if created:
                    state = state
                if state:
                    city, created = City.objects.get_or_create(name=components.get('city'), state=state)
                    if created:
                        return city
                    return city
            state, created = State.objects.get_or_create(name=components.get('state'), country=country)
            if created:
                state = state
            if state:
                if components.get('city'):
                    city, created = City.objects.get_or_create(name=components.get('city'), state=state)
                    if created:
                        return city
                    return city
                if components.get('town'):
                    city, created = City.objects.get_or_create(name=components.get('town'), state=state)
                    if created:
                        return city
                    return city
                if components.get('village'):
                    city, created = City.objects.get_or_create(name=components.get('village'), state=state)
                    if created:
                        return city
                    return city
                else:
                    city, created = City.objects.get_or_create(name=components.get('state'), state=state)
                    if created:
                        return city
                    return city
            else:
                return None
        else:
            return None

    @action(methods=["POST"], detail=True, url_path='add-to-favourite',
            url_name='add_to_favourite')
    def add_to_favourite(self, request, pk=None):
        user = request.user
        favourite_projects = user.favourite_projects
        favourite_projects.append(pk)
        user.favourite_projects = favourite_projects
        user.save()
        return Response({}, status=status.HTTP_200_OK)

    @action(methods=["POST"], detail=True, url_path='remove-from-favourite',
            url_name='remove_from_favourite')
    def remove_from_favourite(self, request, pk=None):
        user = request.user
        favourite_projects = user.favourite_projects
        favourite_projects.remove(pk)
        user.favourite_projects = favourite_projects
        user.save()
        return Response({}, status=status.HTTP_200_OK)

    @action(methods=['GET'], detail=True, url_path='get-project-detail', url_name='get_project_detail')
    def get_project_detail(self, request, pk=None):
        project = get_object_or_404(Project, id=pk)
        serializer = ProjectDetailSerializer(project)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProjectMemberViewSet(ModelViewSet):
    """
    To create Project Member.

    API for creation,reading,updating,deletion of project member.
    """

    queryset = ProjectMember.objects.all()
    serializer_class = ProjectMemberSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ProjectMemberFilter

    def get_permissions(self):
        if self.action in ('accept_invitation', 'send_email'):
            return (IsAuthenticated(), )
        action_permissions_map = {
            'list': 'can_view_project_details',
            'create': 'can_add_members',
            'retrieve': 'can_view_members',
            'update': 'can_edit_members',
            'partial_update': 'can_edit_members',
            'destroy': 'can_delete_members'
        }
        return (HasProjectMemberPermission(action_permissions_map[self.action]),)

    def get_serializer_class(self):
        if self.action == 'list':
            return GetProjectMemberSerializer
        else:
            return self.serializer_class

    def get_queryset(self):
        if self.request.user.is_superuser:
            return ProjectMember.objects.all()
        else:
            project_ids = self.request.user.user_projects.all().values_list("project_id", flat=True)
            return ProjectMember.objects.filter(project_id__in=project_ids)

    @action(methods=["POST"], detail=True, url_path='send-email', url_name='send_email')
    def send_email(self, request, pk=None):
        project_member = get_object_or_404(ProjectMember, id=pk)
        data = {'subject': request.data.get('subject'), 'description': request.data.get('description')}
        serializer=SendEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        files = {}
        for file_d in request.FILES:
            file_name = request.FILES[file_d].field_name
            file = {'name': request.data.get(file_name).name,
                    'read': request.data.get(file_name) \
                        if type(request.data.get(file_name).content_type) in ['image/png', 'image/jpeg'] \
                        else request.data.get(file_name).read().decode('latin-1'),
                    'content_type':request.data.get(file_name).content_type}
            files[file_name] = file
        data['files'] = files
        notification_service = NotificationService()
        response = notification_service.send_email(project_member.user, data)
        if response.status_code:
            return Response(response.text, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'please try again'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(methods=["POST"], detail=True, url_path='accept-invitation', url_name='accept_invitation')
    def accept_invitation(self, request, pk=None):
        # project_member = get_object_or_404(ProjectMember, id=pk)
        # project_member.user.is_staff = True
        # project_member.user.save()
        return Response({'message': 'invitation accepted successfully.'}, status=status.HTTP_202_ACCEPTED)


class PageViewSet(ModelViewSet):
    """ For crud operations on pages"""

    queryset = Page.objects.all()
    serializer_class = PageSerializer
    lookup_field = 'name'
    lookup_url_kwarg = 'name'

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return (IsAuthenticated(), )
        else:
            return (IsSuperUser(), )
