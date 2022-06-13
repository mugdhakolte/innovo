import ast

from rest_framework import permissions

from api.models import *
from api.inter_service_communicator import *


class IsSuperUser(permissions.BasePermission):
    """
    Global permission check for SuperUser.
    """

    def has_permission(self, request, view):
        user = ast.literal_eval(request.innovo_user)
        return user['is_superuser']

    def has_object_permission(self, request, view, obj):
        user = ast.literal_eval(request.innovo_user)
        return user['is_superuser']


class IsSuperUserOrProjectAdmin(permissions.BasePermission):
    """
    Global permission check for SuperUser, ProjectAdmin, Project IPs.
    """

    def __init__(self):
        pass

    def _has_permission(self, project_id, request):
        auth_service = AuthService()
        response = auth_service.is_project_admin(project_id, {'Authorization': request.headers.get('Authorization')})
        return response.json()['is_admin']

    def has_permission(self, request, view):
        project_id = request.query_params.get('project_id')
        if not project_id:
            if request.data.get("board_id"):
                try:
                    board = Board.objects.get(id=request.data.get('board_id'))
                    project_id = board.project_id
                except Board.DoesNotExists as e:
                    return False
            else:
                project_id = request.data.get('project_id')
        if project_id:
            return self._has_permission(project_id, request)
        return True

    def has_object_permission(self, request, view, obj):
        """
        check object permission.
        """
        if hasattr(obj, 'project_id'):
            return self._has_permission(obj.project_id, request)
        elif hasattr(obj.board, 'project_id'):
            return self._has_permission(obj.board.project_id, request)
        else:
            return True


class IsSuperUserOrProjectAdminOrBoardMember(permissions.BasePermission):
    """
    Global permission check for SuperUser, ProjectAdmin, BoardMembers.
    """

    def __init__(self):
        pass

    def _has_permission(self, project_id, request):
        auth_service = AuthService()
        response = auth_service.is_project_admin(project_id, {'Authorization': request.headers.get('Authorization')})
        return response.json()['is_admin']

    def _is_board_member_permission(self, board_id, request):
        user = ast.literal_eval(request.innovo_user).get('id')
        board = Board.objects.get(id=board_id)
        res = self._has_permission(board.project_id, request)
        if res:
            return res
        else:
            return board.has_permission(user)

    def has_permission(self, request, view):
        project_id = request.query_params.get('project_id')
        board_id = request.query_params.get('board_id')
        if not project_id:
            project_id = request.data.get('project_id')
        if project_id:
            return self._has_permission(project_id, request)
        if not board_id:
            board_id = request.data.get('board_id')
        if board_id:
            return self._is_board_member_permission(board_id, request)
        return True

    def has_object_permission(self, request, view, obj):
        return True  # self._is_board_member_permission(obj.board_stage.board_id, request)
        # return self._is_board_member_permission(obj.board_id, request)


class CreatedByPermission(permissions.BasePermission):
    """
    Global permission check for Created_by.
    """
    def has_permission(self, request, view):
        user = ast.literal_eval(request.innovo_user)
        return user['id']

    def has_object_permission(self, request, view, obj):
        user = ast.literal_eval(request.innovo_user)
        if user['id'] == obj.created_by:
            return user['id']
        else:
            return False


class ProjectAdminOrBoardMemberOrBoardPrmission(permissions.BasePermission):

    def __init__(self, permission_code):
        self.permission_code = permission_code

    def _has_permission(self, project_id, request):
        permission_code = self.permission_code
        auth_service = AuthService()
        response = auth_service.has_permission(project_id, permission_code,
                                               {'Authorization': request.headers.get('Authorization')})
        return response.json()['has_permission']

    def _has_admin_permission(self, project_id, request):
        auth_service = AuthService()
        response = auth_service.is_project_admin(project_id, {'Authorization': request.headers.get('Authorization')})
        return response.json()['is_admin']

    def has_permission(self, request, view):
        project_id = request.query_params.get('project_id')
        if not project_id:
            project_id = request.data.get('project_id')
        if project_id:
            permission = self._has_permission(project_id, request)
            return permission
        if view.action in ['get_members', 'add_member', 'remove_member']:
            board = Board.objects.get(id=view.kwargs.get('pk'))
            permission = board.has_permission(ast.literal_eval(request.innovo_user).get('id'))
            if permission:
                return permission
            else:
                return self._has_permission(board.project_id, request)
        if view.action in ['get_key_tasks', 'get_project_cmpletion_status',
                           'get_task_schudels', 'get_gantt_chart_tasks']:
            project_id = view.kwargs.get('pk')
            try:
                return self._has_permission(project_id, request)
            except Exception as e:
                return False
        return True

    def has_object_permission(self, request, view, obj):
        permission = self._has_admin_permission(obj.project_id, request)
        if permission:
            return permission
        permission = self._has_permission(obj.project_id, request)
        if permission:
            if view.action == 'retrieve':
                permission = obj.has_permission(ast.literal_eval(request.innovo_user).get('id'))
                return permission
            else:
                return permission
        else:
            return obj.has_permission(ast.literal_eval(request.innovo_user).get('id'))


class ActivityCheckListPredecessorPermission(IsSuperUserOrProjectAdminOrBoardMember):

    def __init__(self, permission_code):
        self.permission_code = permission_code

    def _has_permission(self, project_id, request):
        permission_code = self.permission_code
        auth_service = AuthService()
        response = auth_service.has_permission(project_id, permission_code,
                                               {'Authorization': request.headers.get('Authorization')})
        return response.json()['has_permission']

    def has_permission(self, request, view):
        task_id = request.data.get('task') if request.data.get('task') else request.data.get('source')
        if not task_id:
            task_id = request.query_params.get('task')
            if not task_id:
                task_id = request.query_params.get('source')
        if view.action in ['create', 'list', 'ganttchart_task_predecessor']:
            try:
                task = Task.objects.get(id=task_id)
                if not task.board_stage:
                    board = self.check_task_board_stage(task)
                    if board:
                        project_permission = self._has_permission(board.project_id, request)
                        if project_permission:
                            return True
                        else:
                            return self._is_board_member_permission(board.id, request)
                    else:
                        """TODO:task in label"""
                        return True
                else:
                    project_permission = self._has_permission(task.board_stage.board.project_id, request)
                    if project_permission:
                        return True
                    else:
                        return self._is_board_member_permission(task.board_stage.board_id, request)
            except Task.DoesNotExist as e:
                return False
        return True

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'source') and obj.source:
            if not obj.source.board_stage:
                board = self.check_task_board_stage(obj.source)
                if board:
                    project_permission = self._has_permission(board.project_id, request)
                    if project_permission:
                        return True
                    else:
                        return self._is_board_member_permission(board.id, request)
                else:
                    return False
            else:
                project_permission = self._has_permission(obj.source.board_stage.board.project_id, request)
                if project_permission:
                    return True
                else:
                    return self._is_board_member_permission(obj.board_stage.board_id, request)
        if hasattr(obj, 'task'):
            task = obj.task
            if task:
                project_permission = self._has_permission(task.board_stage.board.project_id, request)
                if project_permission:
                    return True
                else:
                    return self._is_board_member_permission(task.board_stage.board_id, request)
            return False

    def check_task_board_stage(self, obj):
        """
        Return baord object..
        """
        if hasattr(obj, 'parent_task_id'):
            if obj.parent_task_id.board_stage:
                return obj.parent_task_id.board_stage.board
            else:
                return self.check_task_board_stage(obj.parent_task_id)
        else:
            if obj.task_labels.board:
                return obj.task_labels.board
            else:
                return self.check_task_board_stage(obj.task_labels)


class IsSuperUserOrProjectAdminOrHasBoardPermission(permissions.BasePermission):
    """
    Global permission check for SuperUser, ProjectAdmin, BoardMember.
    """

    def __init__(self, permission_code):

        self.permission_code = permission_code

    def _has_permission(self, project_id, request):
        permission_code = self.permission_code
        auth_service = AuthService()
        response = auth_service.has_permission(project_id, permission_code,
                                               {'Authorization': request.headers.get('Authorization')})
        return response.json()['has_permission']

    def _is_board_member_permission(self, board, request):
        user = ast.literal_eval(request.innovo_user).get('id')
        res = self._has_permission(board.project_id, request)
        if res:
            return res
        else:
            return board.has_permission(user)

    def has_permission(self, request, view):
        project_id = request.query_params.get('project_id')
        if not project_id:
            project_id = request.data.get('project_id')
            if request.data.get('board') and not project_id:
                try:
                    board = Board.objects.get(id=request.data.get('board'))
                    return self._is_board_member_permission(board, request)
                except Board.DoesNotExists as e:
                    return False
        if project_id:
            return self._has_permission(project_id, request)
        return True

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'project_id'):  # for board object
            return self._has_permission(obj.project_id, request)
        elif hasattr(obj, 'board_stage') and obj.board_stage:
            if obj.board_stage:
                return self._is_board_member_permission(obj.board_stage.board, request)
            else:
                return False
        elif hasattr(obj, 'parent_task_id') and obj.parent_task_id:  # hasattr(obj, 'parent_task_id'):
            if obj.parent_task_id.board_stage:
                return self._is_board_member_permission(obj.parent_task_id.board_stage.board, request)
            else:
                board = self.check_task_board_stage(obj)
                if board:
                    return self._is_board_member_permission(board, request)
                else:
                    return False
        elif hasattr(obj, 'board_stage'):  # for task,ganttcart tasks.
            if obj.board_stage:
                return self._is_board_member_permission(obj.board_stage.board, request)
            else:
                return False
        elif hasattr(obj, 'board'):  # board_member, board_stage
            return self._is_board_member_permission(obj.board, request)
        elif hasattr(obj, 'task'):  # for taskmember, activity, Attachment, Checklist, Activity
            if hasattr(obj.task, 'board_stage'):
                if obj.task.board_stage:
                    return self._is_board_member_permission(obj.task.board_stage.board, request)
                else:
                    return False
        elif hasattr(obj, 'source') and obj.source:
            if hasattr(obj.source, 'board_stage'):
                if obj.source.board_stage:
                    return self._is_board_member_permission(obj.source.board_stage.board, request)
                else:
                    return False
        else:
            return False

    def check_task_board_stage(self, obj):
        """
        return baord object.
        """
        if hasattr(obj, 'parent_task_id'):
            if obj.board_stage and not obj.parent_task_id:
                return obj.board_stage.board
            if obj.parent_task_id.board_stage:
                return obj.parent_task_id.board_stage.board
            else:
                return self.check_task_board_stage(obj.parent_task_id)
        else:
            if obj.task_labels.board:
                return obj.task_labels.board
            else:
                return self.check_task_board_stage(obj.task_labels)


class IsSuperUserOrProjectGanttLabelPermission(IsSuperUserOrProjectAdminOrHasBoardPermission):

    def __init__(self, permission_code):
        self.permission_code = permission_code

    def has_permission(self, request, view):
        if view.action == 'move_ganttchart_label':
            label_id = view.kwargs.get('pk')
            try:
                label = GanttChartLable.objects.get(id=label_id)
                return self._has_permission(label.board.project_id, request)
            except GanttChartLable.DoesNotExist as e:
                return False
        if request.data.get('board'):
            try:
                board = Board.objects.get(id=request.data.get('board'))
                if board:
                    return self._has_permission(board.project_id, request)
            except Board.DoesNotExist as e:
                return False
        return True

    def has_object_permission(self, request, view, obj):
        return self._has_permission(obj.board.project_id, request)


class IsSuperUserOrProjectOrBoardPermission(IsSuperUserOrProjectAdminOrHasBoardPermission):

    def __init__(self, permission_code):
        self.permission_code = permission_code

    def has_permission(self, request, view):
        if view.action in ['create_gantt_task']:
            if request.data.get('project_id'):
                return self._has_permission(request.data.get('project_id'), request)
            if request.data.get('board_stage'):
                try:
                    board_stage = BoardStageMap.objects.get(id=request.data.get('board_stage'))
                    if board_stage:
                        return self._has_permission(board_stage.board.project_id, request)
                except BoardStageMap.DoesNotExist as e:
                    return False
            if request.data.get('task_labels'):
                try:
                    label = GanttChartLable.objects.get(id=request.data.get('task_labels'))
                    return self._has_permission(label.board.project_id, request)
                except BoardStageMap.DoesNotExist as e:
                    return False
            if request.data.get('parent_task_id'):
                try:
                    task = Task.objects.get(id=request.data.get('parent_task_id'))
                    board_stage = task.board_stage
                    if board_stage:
                        return self._has_permission(board_stage.board.project_id, request)
                    else:
                        board = self.check_task_board_stage(task)
                        return self._has_permission(board.project_id, request)
                except Task.DoesNotExist as e:
                    return False
        if view.action == 'create':
            try:
                board_stage = BoardStageMap.objects.get(id=request.data.get('board_stage'))
                return self._is_board_member_permission(board_stage.board, request)
            except BoardStageMap.DoesNotExist as e:
                return False
        if view.action in ['add_label', 'remove_label', ]:
            try:
                label = Label.objects.get(id=request.data.get('label_id'))
                return self._is_board_member_permission(label.board, request)
            except Label.DoesNotExist as e:
                return False
        if view.action in ['add_member', 'remove_member', 'copy_task', 'move_task']:
            try:
                task = Task.objects.get(id=view.kwargs.get('pk'))
                board = self.check_task_board_stage(task)
                return self._is_board_member_permission(board, request)
            except Task.DoesNotExist as e:
                return False
        if view.action in ['move_gantt_chart_task', 'remove_gantt_chart_task', 'update_gantt_chart_task']:
            try:
                task = Task.objects.get(id=view.kwargs.get('pk'))
                board = self.check_task_board_stage(task)
                return self._has_permission(board.project_id, request)
            except Task.DoesNotExist as e:
                return False
        else:
            return False

    def has_object_permission(self, request, view, obj):
        pass
