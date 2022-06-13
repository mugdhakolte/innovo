from rest_framework import permissions

from api.models import Project


class IsSuperUser(permissions.BasePermission):
    """
    Global permission check for SuperUser.
    """

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and user.is_superuser

    def has_object_permission(self, request, view, obj):
        return request.user.is_authenticated and request.user.is_superuser


class BaseHasProjectPermission(object):

    def _has_permission(self, project_id, request, permission_code):
        user = request.user
        if user.is_authenticated and user.is_superuser:
            return True
        else:
            project = Project.objects.get(id=project_id)
            return project.has_permission(user, permission_code)


class HasProjectPermission(permissions.BasePermission, BaseHasProjectPermission):
    """
    Global permission check for SuperUser, ProjectAdmin, Project IPs.
    """

    def __init__(self, permission_code, project_field=None):

        self.permission_code = permission_code

    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        return self._has_permission(obj.id, request, self.permission_code)


class HasProjectMemberPermission(permissions.BasePermission, BaseHasProjectPermission):
    """
    Global permission check for SuperUser, ProjectAdmin, Project IPs.
    """

    def __init__(self, permission_code, project_field=None):

        self.permission_code = permission_code
        self.project_field = project_field

    def has_permission(self, request, view):
        project_id = request.query_params.get('project')
        if project_id:
            return self._has_permission(project_id, request, self.permission_code)
        if view.action == 'create':
            project_id = request.data.get('project')
            return self._has_permission(project_id, request, self.permission_code)
        return True

    def has_object_permission(self, request, view, obj):
        return self._has_permission(obj.project.id, request, self.permission_code)
