import ast
import sys
import json
import datetime

from datetime import timedelta, date

from nested_lookup import nested_lookup

from django.db.models import *
from django.db import IntegrityError
from django.shortcuts import get_object_or_404

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny, IsAuthenticated

from api.utils import *
from api.models import *
from api.filters import *
from api.db_utils import *
from api.serializers import *
from api.permissions import *
from api.move_task_utils import *
from api import activity_constants
from api.action_permissions_maps import *
from api.get_ganttchart_task_stage_labels import *
from api.inter_service_communicator import AuthService

sys.setrecursionlimit(10 ** 6)


class ActivityViewSet(ModelViewSet):
    serializer_class = ActivitySerializer
    queryset = Activity.objects.all()
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ActivityFilter

    def get_permissions(self):
        if self.action == 'destroy':
            created_by = ast.literal_eval(self.request.innovo_user)
            activity = get_object_or_404(Activity, pk=self.kwargs.get('pk'))
            if activity.created_by == created_by.get('id'):
                return (CreatedByPermission(),)
            else:
                return (IsSuperUser(),)
        else:
            return (IsSuperUserOrProjectAdminOrBoardMember(),)

    def get_queryset(self):
        return Activity.objects.filter(parent_activity__isnull=True)

    @action(methods=["POST"], detail=False, url_name='', url_path='remove-reply')
    def remove_reply(self, request, pk=None):
        activity = get_object_or_404(Activity, id=request.data.get("activity_id"))
        activity.delete()
        return Response({'detail': 'reply removed successfully.'}, status=status.HTTP_204_NO_CONTENT)


class ChecklistItemViewSet(ModelViewSet):
    serializer_class = ChecklistItemSerializer
    queryset = ChecklistItem.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ChecklistItemFilter
    permission_classes = (IsSuperUserOrProjectAdminOrBoardMember,)

    def create(self, request):
        response = super(ChecklistItemViewSet, self).create(request)
        checklistitem = ChecklistItem.objects.get(id=response.data['id'])
        log_activity(checklistitem.checklist.task, activity_constants.CHECKLISTITEM_ADDED,
                     ast.literal_eval(request.innovo_user).get('id'))
        return Response(response.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        checklistitem = self.get_object()
        response = super(ChecklistItemViewSet, self).destroy(request, pk)
        log_activity(checklistitem.checklist.task, activity_constants.CHECKLISTITEM_REMOVED,
                     ast.literal_eval(request.innovo_user).get('id'))
        return Response(response.data, status=status.HTTP_204_NO_CONTENT)

    @action(methods=["POST"], detail=True, url_path='mark-completed')
    def complete_checklist_item(self, request, pk=None):
        user = ast.literal_eval(request.innovo_user).get('id')
        check_list_item = get_object_or_404(ChecklistItem, id=pk)
        check_list_item.is_completed = True
        check_list_item.completed_by = user
        check_list_item.save()
        serializer = ChecklistItemSerializer(check_list_item)
        log_activity(task=check_list_item.checklist.task, description=activity_constants.CHECKLIST_ITEM_COMPLETE,
                     created_by=ast.literal_eval(request.innovo_user).get('id'))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=["POST"], detail=True, url_path='mark-incompleted')
    def incomplete_checklist_item(self, request, pk=None):
        check_list_item = get_object_or_404(ChecklistItem, id=pk)
        check_list_item.is_completed = False
        check_list_item.save()
        serializer = ChecklistItemSerializer(check_list_item)
        log_activity(task=check_list_item.checklist.task, description=activity_constants.CHECKLIST_ITEM_INCOMPLETE,
                     created_by=ast.literal_eval(request.innovo_user).get('id'))
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChecklistViewSet(ModelViewSet):
    """This class is for REST APIs to Checklist."""

    serializer_class = ChecklistSerializer
    queryset = Checklist.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ChecklistFilter


    def get_permissions(self):
        return (ActivityCheckListPredecessorPermission(ACTION_PERMISSIONS_MAP[self.action]),)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ChecklistDetailSerializer
        return ChecklistSerializer

    def create(self, request):
        response = super(ChecklistViewSet, self).create(request)
        task = Task.objects.get(id=response.data['task'])
        log_activity(task, activity_constants.CHECKLIST_ADDED, ast.literal_eval(request.innovo_user).get('id'))
        return Response(response.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        checklist = self.get_object()
        response = super(ChecklistViewSet, self).destroy(request, pk)
        log_activity(checklist.task, activity_constants.CHECKLIST_REMOVED,
                     ast.literal_eval(request.innovo_user).get('id'))
        return Response(response.data, status=status.HTTP_204_NO_CONTENT)


class AttachmentViewSet(ModelViewSet):
    """This class is for REST APIs to Attachment."""
    serializer_class = AttachmentSerializer
    queryset = Attachment.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = AttachmentFilter


    def get_permissions(self):
        return (ActivityCheckListPredecessorPermission(ACTION_PERMISSIONS_MAP[self.action]),)

    def create(self, request):
        response = super(AttachmentViewSet, self).create(request)
        task = Task.objects.get(id=response.data['task'])
        log_activity(task, activity_constants.ATTACHMENT_ADDED, ast.literal_eval(request.innovo_user).get('id'))
        return Response(response.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        attachment = get_object_or_404(Attachment, id=pk)
        response = super(AttachmentViewSet, self).destroy(request, pk)
        delete_blob(str(attachment.attachment).encode('utf-8'))
        log_activity(attachment.task, activity_constants.ATTACHMENT_REMOVED,
                     ast.literal_eval(request.innovo_user).get('id'))
        return Response(response.data, status=status.HTTP_204_NO_CONTENT)


class TaskMemberViewSet(ModelViewSet):
    serializer_class = TaskMemberSerializer
    queryset = TaskMember.objects.all()
    http_method_names = ['get', 'post', 'delete']
    filter_backends = (DjangoFilterBackend,)
    filterset_class = TaskMemberFilter

    def get_permissions(self):
        return (ActivityCheckListPredecessorPermission(ACTION_PERMISSIONS_MAP[self.action]),)

    def create(self, request):
        response = super(TaskMemberViewSet, self).create(request)
        task = Task.objects.get(id=response.data['task'])
        log_activity(task, activity_constants.MEMBER_ADDED, ast.literal_eval(request.innovo_user).get('id'))
        return Response(response.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        member = TaskMember.objects.get(id=pk)
        response = super(TaskMemberViewSet, self).destroy(request, pk)
        log_activity(member.task, activity_constants.MEMBER_REMOVED, ast.literal_eval(request.innovo_user).get('id'))
        return Response(response.data, status=status.HTTP_204_NO_CONTENT)


class TaskViewSet(ModelViewSet):
    """This class is for REST APIs to Task."""
    serializer_class = TaskSerializer
    queryset = Task.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = TaskFilter


    def get_permissions(self):
        if self.action in ['create_product_task', 'update_product_task', 'remove_product_task', 'update_project_task',
                           ]:
            return (AllowAny(),)
        if self.action in ['create', 'create_gantt_task', 'remove_gantt_chart_task',
                           'update_gantt_chart_task', 'add_label', 'remove_label',
                           'add_member', 'remove_member', 'move_gantt_chart_task', 'copy_task',
                           'move_task']:
            return (IsSuperUserOrProjectOrBoardPermission(ACTION_PERMISSIONS_MAP[self.action]),)
        if self.action in ACTION_PERMISSIONS_MAP.keys():
            return (IsSuperUserOrProjectAdminOrHasBoardPermission(ACTION_PERMISSIONS_MAP[self.action]),)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TaskDetailSerializer
        return TaskSerializer

    def retrieve(self, request, pk=None):
        """
        Method for task detail
        :param request: None
        :param pk: task id or task secrete key
        :return: task detail..
        """
        if pk.isalnum() and not pk.isdigit():
            task = get_object_or_404(Task, share_key=pk)
            serializer = TaskDetailSerializer(task)
            activities = serializer.data.get("activities")
            users = self._get_user_info_from_ids(request, self._get_user_ids(activities))
            self._merge_user_info_in_activities(activities, users)
            return Response(serializer.data, status=status.HTTP_200_OK)
        response = super(TaskViewSet, self).retrieve(request, pk)
        response = response.data
        for task in response.get('task_dependencies'):
            task_dependancies = TaskDependencyMap.objects.filter(source=pk, target=task.get('id'))
            if task_dependancies:
                if len(task_dependancies) == 1:
                    task['type'] = task_dependancies[0].type
                else:
                    task['type'] = task_dependancies[0].type
                    continue
        activities = response.get('activities')
        users = self._get_user_info_from_ids(request, self._get_user_ids(activities))
        if users:
            response['activities'] = self._merge_user_info_in_activities(activities, users)
        response['product_category_name'] = None
        if response.get('product_category_id'):
            response['product_category_name'] = get_product_category_name(product_category_id = response.get('product_category_id'),
                                                                          headers = {"Authorization": request.headers.get('Authorization')})

        return Response(response, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        """remove stage from board"""
        headers = {"Authorization": request.headers.get('Authorization')}
        product = ProcurementService()
        task_to_remove = get_object_or_404(Task, id=kwargs.get('pk'))
        # task_to_remove = self.get_object()
        task_end_date = task_to_remove.end_date
        board_stage = task_to_remove.board_stage
        project_id = board_stage.board.project_id
        response_data = get_project_details(project_id, headers)
        task_name = response_data.get('name') + "_" + str(response_data.get('id'))
        project_task = Task.objects.filter(title=response_data.get('name'), task_type=task_name).first()

        child_tasks = Task.objects.filter(parent_task_id=task_to_remove.id)
        predecessors = task_to_remove.predecessors.all()

        if task_to_remove.sub_tasks.all():
            self.child_task_updade(task_to_remove, headers)
        for predecessor in predecessors:
            predecessor.delete()
        for successor in task_to_remove.successors.all():
            if successor.target:
                prdecessor_cretical_task(successor.target, headers)
            successor.delete()
        if task_to_remove.procurement_id:
            try:
                pay_load = {'is_display_in_ganttchart': False, 'is_critical_path_item': False}
                product.update_product(pay_load, product_id=task_to_remove.procurement_id,
                                       headers={"Authorization": request.headers.get('Authorization')})
                response = super(TaskViewSet, self).destroy(request, *args, **kwargs)
                if response.status_code == 204:
                    self._update_another_stage_cretical_path_tasks(task_to_remove, predecessors, child_tasks,
                                                                   project_task, headers)
                    self._update_critical_path_tasks(board_stage, task_end_date, headers)
                return Response(response.data, status=status.HTTP_204_NO_CONTENT)
            except Exception as e:
                return Response({"Message": "Please try again"}, status=status.HTTP_400_BAD_REQUEST)
        if task_to_remove.parent_task_id:
            response = super(TaskViewSet, self).destroy(request, *args, **kwargs)
            if response.status_code == 204:
                current_stage = task_to_remove.board_stage
                tasks = current_stage.tasks.filter(is_display_in_board=True).exclude(id__in=[project_task.id, task_to_remove.id])
                task_to_remove.move_task_or_stage_from_board(tasks)
                if task_to_remove.parent_task_id and task_to_remove.parent_task_id.id != project_task.id:
                    tasks = task_to_remove.parent_task_id.sub_tasks.all().exclude(id__in=[project_task.id,task_to_remove.id])
                    task_to_remove.move_task_or_stage_from_gantt_chart(tasks)
                else:
                    boards = Board.objects.filter(project_id=current_stage.board.project_id)
                    stages = [stage for board in boards for stage in board.board_stage_maps.all() if stage]
                    tasks = [task for stage in stages for task in stage.tasks.filter(
                        Q(display_in_gantt_chart=True, parent_task_id=project_task.id) | Q(display_in_gantt_chart=True,
                                                                                           parent_task_id__isnull=True)).exclude(
                        id__in=[project_task.id, task_to_remove.id]) if task]
                    task_to_remove.move_task_or_stage_from_gantt_chart(tasks)
                self._update_another_stage_cretical_path_tasks(task_to_remove, predecessors, child_tasks,
                                                               project_task, headers)
                self._update_critical_path_tasks(board_stage, task_end_date, headers)
            return Response(response.data, status=status.HTTP_204_NO_CONTENT)
        serializer = TaskSerializer(task_to_remove)
        if not serializer.data.get('board_stage'):
            task_to_remove.delete()
            return Response({}, status=status.HTTP_204_NO_CONTENT)
        current_stage = get_object_or_404(BoardStageMap, id=serializer.data.get('board_stage'))
        if serializer.data.get('is_display_in_board') and serializer.data.get('display_in_gantt_chart'):
            """update board stage position"""
            if current_stage.tasks:
                tasks = current_stage.tasks.filter(is_display_in_board=True).exclude(id__in=[project_task.id, task_to_remove.id])
                task_to_remove.move_task_or_stage_from_board(tasks)
                if task_to_remove.parent_task_id:
                    tasks = task_to_remove.parent_task_id.sub_tasks.all()
                    task_to_remove.move_task_or_stage_from_gantt_chart(tasks)
                else:
                    boards = Board.objects.filter(project_id=current_stage.board.project_id)
                    stages = [stage for board in boards for stage in board.board_stage_maps.all() if stage]
                    tasks = [task for stage in stages for task in stage.tasks.filter(
                        Q(display_in_gantt_chart=True, parent_task_id=project_task.id) | Q(display_in_gantt_chart=True,
                                                                                           parent_task_id__isnull=True)).exclude(
                        id__in=[project_task.id, task_to_remove.id]) if task]
                    task_to_remove.move_task_or_stage_from_gantt_chart(tasks)
            response = super(TaskViewSet, self).destroy(request, *args, **kwargs)
            if response.status_code == 204:
                self._update_another_stage_cretical_path_tasks(task_to_remove, predecessors, child_tasks,
                                                               project_task, headers)
                self._update_critical_path_tasks(board_stage, task_end_date, headers)
            return Response(response.data, status=status.HTTP_204_NO_CONTENT)
        elif serializer.data.get('is_display_in_board') and not serializer.data.get('display_in_gantt_chart'):
            tasks = current_stage.tasks.filter(is_display_in_board=True,
                                               display_in_gantt_chart=False).exclude(id=task_to_remove.id)
            if tasks:
                task_to_remove.move_task_or_stage_from_board(tasks)
            response = super(TaskViewSet, self).destroy(request, *args, **kwargs)
            if response.status_code == 204:
                self._update_critical_path_tasks(current_stage, task_end_date, headers)
            return Response(response.data, status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({"detail": "Task already removed from board"}, status=status.HTTP_204_NO_CONTENT)

    def _update_another_stage_cretical_path_tasks(self, task_to_remove, predecessors, child_tasks, project_task, headers):

        if child_tasks:
            for task in child_tasks:
                update_child_tasks_false(task, headers)
        if predecessors:
            counter_var = None
            for predecessor in predecessors:
                if predecessor.source.is_critical_path_task:
                    stge_max_end_date = predecessor.target.board_stage.tasks.exclude(
                        id__in=[task_to_remove.id, project_task.id]).aggregate(Max('end_date')).get(
                        'end_date__max')
                    if predecessor.target.end_date == stge_max_end_date:
                        counter_var = True
                        if predecessor.target.is_critical_path_task:
                            pass
                        else:
                            if predecessor.target.display_in_gantt_chart:
                                predecessor.target.is_critical_path_task = True
                                predecessor.target.save()
                                update_child_tasks_true(predecessor.target, headers)
                                prdecessor_cretical_task_true(predecessor.target, headers)
                                if predecessor.target.procurement_id:
                                    try:
                                        update_product_from_board_gant_chart(predecessor.target, headers)
                                    except Exception as e:
                                        pass
                    if predecessor.target.parent_task_id and predecessor.target.parent_task_id.id != \
                            project_task.id and predecessor.taregt.parent_task_id.is_critical_path_task:
                        counter_var = True
                        if predecessor.target.is_critical_path_task:
                            pass
                        else:
                            if predecessor.target.display_in_gantt_chart:
                                predecessor.target.is_critical_path_task = True
                                predecessor.target.save()
                                update_child_tasks_true(predecessor.target, headers)
                                prdecessor_cretical_task_true(predecessor.target, headers)
                                if predecessor.target.procurement_id:
                                    try:
                                        update_product_from_board_gant_chart(predecessor.target, headers)
                                    except Exception as e:
                                        pass
                if not counter_var:
                    if predecessor.target.successors.filter(target=predecessor.target.id).exclude(source=task_to_remove.id):
                        for target_successor in predecessor.target.successors.filter(target=predecessor.target.id).exclude(source=task_to_remove.id):
                            if target_successor.source.is_critical_path_task:
                                counter_var = True
                                if predecessor.target.is_critical_path_task:
                                    pass
                                else:
                                    if predecessor.target.display_in_gantt_chart:
                                        predecessor.target.is_critical_path_task = True
                                        predecessor.target.save()
                                        update_child_tasks_true(predecessor.target, headers)
                                        prdecessor_cretical_task_true(predecessor.target, headers)
                    if predecessor.target.parent_task_id and predecessor.target.parent_task_id.id != project_task.id \
                            and predecessor.target.parent_task_id.is_critical_path_task:
                        counter_var = True
                        if predecessor.target.is_critical_path_task:
                            pass
                        else:
                            if predecessor.target.display_in_gantt_chart:
                                predecessor.target.is_critical_path_task = True
                                predecessor.target.save()
                                update_child_tasks_true(predecessor.target, headers)
                                prdecessor_cretical_task_true(predecessor.target, headers)
                    if not counter_var:
                        if not predecessor.target.is_critical_path_task:
                            pass
                        else:
                            predecessor.target.is_critical_path_task = False
                            predecessor.target.save()
                            update_child_tasks_false(predecessor.target, headers)
                            prdecessor_cretical_task(predecessor.target, headers)
                    if predecessor.target.procurement_id:
                        try:
                            update_product_from_board_gant_chart(predecessor.target, headers)
                        except Exception as e:
                            pass

    def _update_critical_path_tasks(self, board_stage, task_end_date, headers):
        project_id = board_stage.board.project_id
        response_data = get_project_details(project_id, headers)
        task_name = response_data.get('name') + "_" + str(response_data.get('id'))
        project_task = Task.objects.filter(title=response_data.get('name'), task_type=task_name).first()
        try:
            max_date = board_stage.tasks.all().exclude(id=project_task.id).aggregate(Max('end_date')).get('end_date__max')
            tasks = board_stage.tasks.filter(end_date=max_date, display_in_gantt_chart=True).exclude(id=project_task.id)
        except Exception as e:
            max_date = board_stage.tasks.all().aggregate(Max('end_date')).get('end_date__max')
            tasks = board_stage.tasks.filter(end_date=max_date, display_in_gantt_chart=True)
        if max_date:
            for task in tasks:
                if task.end_date == max_date and task.display_in_gantt_chart:
                    if task.is_critical_path_task:
                        pass
                    else:
                        if task.display_in_gantt_chart:
                            task.is_critical_path_task = True
                            task.save()
                            update_child_tasks_true(task, headers)
                            prdecessor_cretical_task_true(task, headers)
                            if task.procurement_id:
                                update_product_from_board_gant_chart(task, headers)
                else:
                    if task.parent_task_id and task.parent_task_id.is_critical_path_task:
                        if task.is_critical_path_task:
                            pass
                        else:
                            if task.display_in_gantt_chart:
                                task.is_critical_path_task = True
                                task.save()
                                update_child_tasks_true(task, headers)
                                prdecessor_cretical_task_true(task, headers)
                                if task.procurement_id:
                                    update_product_from_board_gant_chart(task, headers)
                    elif task.predecessors.all():
                        for predecessor in task.predecessors.all():
                            if predecessor.source.is_critical_path_task:
                                if task.is_critical_path_task:
                                    pass
                                else:
                                    if task.display_in_gantt_chart:
                                        task.is_critical_path_task = True
                                        task.save()
                                        update_child_tasks_true(task, headers)
                                        prdecessor_cretical_task_true(task, headers)
                                        if task.procurement_id:
                                            update_product_from_board_gant_chart(task, headers)
                                        break
                    else:
                        if not task.is_critical_path_task:
                            pass
                        else:
                            task.is_critical_path_task = False
                            task.save()
                            update_child_tasks_false(task, headers)
                            prdecessor_cretical_task(task, headers)
                            if task.procurement_id:
                                update_product_from_board_gant_chart(task, headers)

    def child_task_updade(self, parent_task, headers):
        project_id=None
        update_child_tasks_false(parent_task, headers)
        if parent_task.board_stage:
            project_id = parent_task.board_stage.board.project_id
        boards = Board.objects.filter(project_id=project_id)
        for task in parent_task.sub_tasks.all():
            gant_position = task_gantchart_position(boards)
            task.parent_task_id = None
            task.gantt_chart_position = gant_position+1
            task.save()
        if parent_task.gantt_chart_labels.all():
            for label in parent_task.gantt_chart_labels.all():
                gant_position = task_gantchart_position(boards)
                label.position = gant_position+1
                label.tasks = None
                label.save()
        return True

    @action(methods=['POST'], detail=False, url_path='update-project-task')
    def update_project_task(self, request, pk=None):
        old_title = request.data.get('old_title')
        project_id = request.data.get('project_id')
        task_type = old_title + '_' + project_id
        task = self.queryset.filter(title=old_title, task_type=task_type).first()
        serializer = GanttTaskSerializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'id': serializer.data.get('id'),
                         'title': serializer.data.get('title')}, status=status.HTTP_202_ACCEPTED)


    @action(methods=['POST'], detail=True, url_path='update-gantt-chart-task')
    def update_gantt_chart_task(self, request, pk=None):
        headers = {"Authorization": request.headers.get('Authorization')}
        try:
            db_task = Task.objects.get(id=pk)
        except ObjectDoesNotExist as e:
            return Response({"id": pk,
                             "title": request.data.get('title'),
                             "start_date": request.data.get('start_date'),
                             "end_date": request.data.get('end_date'),
                             "progress": request.data.get('progress')}, status=status.HTTP_202_ACCEPTED)

        project_task = self._get_project_task(db_task.board_stage, headers=headers)
        if db_task:
            if request.data.get('selectedStage'):
                board_stage_obj = request.data.get('selectedStage').get('id')
                requested_stage = get_object_or_404(BoardStageMap, id=board_stage_obj)
                if requested_stage.id == db_task.board_stage_id:
                    pass
                else:
                    old_stage = db_task.board_stage
                    old_stage_tasks = old_stage.tasks.all().exclude(id=db_task.id)
                    max_end_date = old_stage.tasks.all().exclude(id=db_task.id).aggregate(Max('end_date')).get('end_date__max')
                    tasks = old_stage.tasks.filter(end_date=max_end_date).exclude(id=db_task.id)
                    for task in tasks:
                        if task.display_in_gantt_chart:
                            task.is_critical_path_task = True
                            task.save()
                    db_task.move_task_or_stage_from_board(old_stage_tasks)
                    max_position = requested_stage.tasks.all().aggregate(Max('position')).get('position__max')
                    critical_path_tasks(requested_stage,
                                        db_task,
                                        project_task=project_task,
                                        headers=headers)
                    db_task.board_stage = requested_stage
                    db_task.position = max_position + 1 if max_position else 1
                    db_task.save()
            serializers = GanttTaskSerializer(db_task, request.data, partial=True)
            if not serializers.is_valid():
                if 'end_date' in serializers.errors.keys() or 'start_date' in serializers.errors.keys():
                    return Response({'detail': 'Error, please try again with correct date format YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)
                return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)
            serializers.save()
            task = get_object_or_404(Task, id=serializers.data.get('id'))
            if request.data.get('duration'):
                end_date = task.start_date + timedelta(int(request.data.get('duration')))
                task.end_date = end_date
                task.save()
            if request.data.get('end_date') or request.data.get('duration'):
                if task.due_date and task.end_date <= task.due_date:
                    pass
                else:
                    task.due_date = task.end_date
                    task.delay = (task.end_date - task.due_date).days
                if task.is_display_in_board:
                    board_stage = task.board_stage
                    critical_path_tasks(board_stage,
                                        task,
                                        project_task=project_task,
                                        headers={"Authorization": request.headers.get('Authorization')})
                task.save()
                if task.procurement_id:
                    update_product_from_board_gant_chart(task,
                                                         headers={"Authorization": request.headers.get('Authorization')})
                serializers = GanttTaskSerializer(task)
                return Response(serializers.data, status=status.HTTP_202_ACCEPTED)
            return Response(serializers.data, status=status.HTTP_202_ACCEPTED)

    @action(methods=['DELETE'], detail=True, url_path='remove-gantt-chart-task')
    def remove_gantt_chart_task(self, request, pk=None):
        headers = {"Authorization": request.headers.get('Authorization')}
        product = ProcurementService()
        task_to_remove = get_object_or_404(Task, id=pk)

        if task_to_remove.sub_tasks.all():
            self.child_task_updade(task_to_remove, headers)
        serializer = TaskSerializer(task_to_remove)
        for predecessor in task_to_remove.predecessors.all():
            if predecessor.target:
                prdecessor_cretical_task(task_to_remove, headers)
            predecessor.delete()
        for successor in task_to_remove.successors.all():
            if successor.target:
                prdecessor_cretical_task(successor.target, headers)
            successor.delete()
        if task_to_remove.procurement_id:
            try:
                pay_load = {'is_display_in_ganttchart': False}
                product.update_product(pay_load, product_id=task_to_remove.procurement_id,
                                       headers= {"Authorization": request.headers.get('Authorization')})
                destroy_task_util(task_to_remove, task_to_remove.end_date, headers)
                task_to_remove.delete()
                return Response({}, status=status.HTTP_204_NO_CONTENT)
            except Exception as e:
                return Response({'detail': 'Error, Please try again.'}, status=status.HTTP_204_NO_CONTENT)

        parent_stage, parent_task, parent_label = None, None, None
        if serializer.data.get('board_stage'):
            parent_stage = get_object_or_404(BoardStageMap, id=serializer.data.get('board_stage'))
        elif serializer.data.get('task_labels'):
            parent_label = get_object_or_404(GanttChartLable, id=serializer.data.get('task_labels'))
        else:
            parent_task = get_object_or_404(Task, id=serializer.data.get('parent_task_id'))
        if serializer.data.get('is_display_in_board') and serializer.data.get('display_in_gantt_chart'):
            if parent_stage:
                if parent_stage.tasks:
                    tasks = parent_stage.tasks.filter(is_display_in_board=True,
                                                      display_in_gantt_chart=True).exclude(id=task_to_remove.id)
                    if tasks:
                        task_to_remove.move_task_or_stage_from_gantt_chart(tasks)
                if parent_stage.gantt_chart_labels:
                    labels = parent_stage.gantt_chart_labels.all()
                    if labels:
                        task_to_remove.move_task_or_stage_from_board(labels)
            elif parent_label:
                if parent_label.taskss:
                    tasks = parent_label.taskss.filter(is_display_in_board=True,
                                                       display_in_gantt_chart=True).exclude(id=task_to_remove.id)
                    if tasks:
                        task_to_remove.move_task_or_stage_from_gantt_chart(tasks)
                if parent_label.sub_labels:
                    labels = parent_label.sub_labels.all()
                    if labels:
                        task_to_remove.move_task_or_stage_from_board(labels)
                if parent_label.board_stage_map:
                    stages = parent_label.board_stage_map.filter(is_display_in_board=True, display_in_gantt_chart=True)
                    if stages:
                        task_to_remove.move_task_or_stage_from_gantt_chart(stages)
            elif parent_task:
                if parent_task.sub_tasks:
                    tasks = parent_task.sub_tasks.filter(is_display_in_board=True,
                                                         display_in_gantt_chart=True).exclude(id=task_to_remove.id)
                    if tasks:
                        task_to_remove.move_task_or_stage_from_gantt_chart(tasks)
                if parent_task.gantt_chart_labels:
                    labels = parent_task.gantt_chart_labels.all()
                    if labels:
                        task_to_remove.move_task_or_stage_from_board(labels)
            task_to_remove.display_in_gantt_chart = False
            if task_to_remove.is_critical_path_task:
                task_to_remove.is_critical_path_task = False
                if task_to_remove.procurement_id:
                    try:
                        update_product_from_board_gant_chart(task_to_remove, headers)
                    except Exception as e:
                        pass
            task_to_remove.gantt_chart_position = 0
            task_to_remove.save()
            return Response({}, status=status.HTTP_204_NO_CONTENT)
        elif not serializer.data.get('is_display_in_board') and serializer.data.get('display_in_gantt_chart'):
            if parent_stage:
                if parent_stage.tasks:
                    tasks = parent_stage.tasks.filter(is_display_in_board=False,
                                                      display_in_gantt_chart=True).exclude(id=task_to_remove.id)
                    if tasks:
                        task_to_remove.move_task_or_stage_from_gantt_chart(tasks)
                if parent_stage.gantt_chart_labels:
                    labels = parent_stage.gantt_chart_labels.all()
                    if labels:
                        task_to_remove.move_task_or_stage_from_board(labels)
            elif parent_label:
                if parent_label.taskss:
                    tasks = parent_label.taskss.filter(is_display_in_board=False,
                                                       display_in_gantt_chart=True).exclude(id=task_to_remove.id)
                    if tasks:
                        task_to_remove.move_task_or_stage_from_gantt_chart(tasks)
                if parent_label.sub_labels:
                    labels = parent_label.sub_labels.all()
                    if labels:
                        task_to_remove.move_task_or_stage_from_board(labels)
                if parent_label.board_stage_map:
                    stages = parent_label.board_stage_map.filter(is_display_in_board=False, display_in_gantt_chart=True)
                    if stages:
                        task_to_remove.move_task_or_stage_from_gantt_chart(stages)
            elif parent_task:
                if parent_task.sub_tasks:
                    tasks = parent_task.sub_tasks.filter(is_display_in_board=False,
                                                         display_in_gantt_chart=True).exclude(id=task_to_remove.id)
                    if tasks:
                        task_to_remove.move_task_or_stage_from_gantt_chart(tasks)
                if parent_task.gantt_chart_labels:
                    labels = parent_task.gantt_chart_labels.all()
                    if labels:
                        task_to_remove.move_task_or_stage_from_board(labels)
            task_to_remove.delete()
            return Response({}, status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({"detail": "Task already removed from ganttchart"}, status=status.HTTP_204_NO_CONTENT)

    def _get_user_ids(self, activities):
        users = set(nested_lookup('created_by', activities))
        users = list(users)
        return users

    def _merge_user_info_in_activities(self, activities, users):
        """
        merge user information in activities.
        """
        for activity in activities:
            if not activity.get('replies'):
                for user in users:
                    if activity.get('created_by') == user.get('id'):
                        activity['user_name'] = user.get('full_name')
                        activity['user_profile_pic'] = user.get('profile_pic')
            else:
                for user in users:
                    if activity.get('created_by') == user.get('id'):
                        activity['user_name'] = user.get('full_name')
                        activity['user_profile_pic'] = user.get('profile_pic')
                        self._merge_user_info_in_activities(activity.get('replies'), users)
        return activities

    def _get_user_info_from_ids(self, request, user_ids):
        auth_service = AuthService()
        data = []
        for user_id in user_ids:
            response = auth_service.get_user_from_id_s(user_id, {"Authorization": request.headers.get('Authorization')})
            data.append(json.loads(response.text))
        return data

    @action(methods=["POST"], detail=True, url_path='move-task')
    def move_task(self, request, pk=None):
        headers = {"Authorization": request.headers.get('Authorization')}
        serializer = MoveTaskSerializer(data=request.data)
        if serializer.is_valid():
            board_stage_request = serializer.data["board_stage"]
            new_position = serializer.data["position"]
            task_to_move = Task.objects.get(id=pk)
            task_end_date = task_to_move.end_date
            current_stage = task_to_move.board_stage
            project_task = self._get_project_task(current_stage, headers)
            board_stage_obj = get_object_or_404(BoardStageMap, id=board_stage_request)
            if board_stage_obj.id == task_to_move.board_stage_id:
                """board is same, stage same"""
                task_to_move.move(new_position)
            else:
                """board is same, stage different."""
                current_stage_tasks = Task.objects.filter(board_stage=task_to_move.board_stage_id,
                                                          is_display_in_board=True)
                # current_stage
                self._update_critical_path_tasks(current_stage, task_end_date, headers)
                for task in current_stage_tasks.exclude(id=task_to_move.id):
                    old_position = task_to_move.position
                    position = task.position
                    if old_position < position:
                        task.position = task.position - 1
                        task.save()
                    else:
                        pass
                task_to_move.board_stage_id = board_stage_request
                task_to_move.position = new_position
                task_to_move.save()
                self._update_critical_path_tasks(current_stage, task_end_date, headers)
                new_stage_tasks = Task.objects.filter(board_stage=task_to_move.board_stage_id,
                                                      is_display_in_board=True)
                for task in new_stage_tasks.exclude(id=task_to_move.id):
                    position = task.position
                    if position >= new_position:
                        task.position = task.position + 1
                        task.save()
                task_to_move = critical_path_tasks(board_stage_obj, task_to_move,
                                                   project_task=project_task,
                                                   headers={"Authorization": request.headers.get('Authorization')})
            serializer = TaskSerializer(get_object_or_404(Task, id=task_to_move.id))
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)

    def _get_project_task(self, board_stage, headers):
        project_id = board_stage.board.project_id
        response_data = get_project_details(project_id, headers)
        task_name = response_data.get('name') + "_" + str(response_data.get('id'))
        project_task = Task.objects.filter(title=response_data.get('name'), task_type=task_name).first()
        return project_task


    @action(methods=["POST"], detail=True, url_path='move-gantt-chart-task')
    def move_gantt_chart_task(self, request, pk=None):
        """
        Move gantt chart task
        :param request:
        :param pk:
        :return:
        """
        headers = {"Authorization": request.headers.get('Authorization')}
        task_to_move = get_object_or_404(Task, id=pk)
        project_id = task_to_move.board_stage.board.project_id
        response_data = get_project_details(project_id, headers)
        task_name = response_data.get('name') + "_" + str(response_data.get('id'))
        project_task = Task.objects.filter(title=response_data.get('name'), task_type=task_name).first()
        """task move at project level"""
        if request.data.get('position') and \
                not request.data.get('board_stage') and not request.data.get('parent_task_id') and \
                not request.data.get('label_id'):
            old_position = task_to_move.gantt_chart_position
            new_position = int(request.data.get('position'))
            board = check_task_board(task_to_move)
            boards = Board.objects.filter(project_id=board.project_id)
            stages = [stage for board in boards for stage in board.board_stage_maps.all() if stage]
            labels = [label for board in boards for label in board.gantt_chart_labels.filter \
                (tasks__isnull=True, parent_label_id__isnull=True)]
            if not task_to_move.task_labels and not task_to_move.parent_task_id:
                task_to_move.move_gantt_chart_task(new_position)
            else:
                for stage in stages:
                    tasks = stage.tasks.filter(parent_task_id__isnull=True,
                                               task_labels__isnull=True,
                                               display_in_gantt_chart=True).exclude(id=task_to_move.id)
                    self._move_to_stage_task(new_position, tasks)
                if labels:
                    self._move_to_labels(new_position, labels)
                if task_to_move.parent_task_id:
                    """form parent task"""
                    from_task_tasks_gantt_chart_position(task_to_move)
                    task_to_move.parent_task_id = None
                if task_to_move.task_labels:
                    """move labels and tasks from parent label"""
                    move_task_from_label(task_to_move)
                    task_to_move.task_labels = None
            task_to_move.gantt_chart_position = request.data.get('position')
            task_to_move.save()
            update_critical_path_tasks(task_to_move.board_stage, task_to_move, task_to_move.end_date,
                                       project_task=project_task,
                                       headers=headers)
            serializer = TaskSerializer(task_to_move)
            return Response(serializer.data, status=status.HTTP_200_OK)
        """task move in parent task"""
        if request.data.get('parent_task_id'):
            serializer = MoveParentTaskSerializer(data=request.data)
            if serializer.is_valid():
                new_position = serializer.data["position"]
                requested_task = get_object_or_404(Task, id=int(serializer.data["parent_task_id"]))
                "task move in task"
                if task_to_move.parent_task_id:
                    """from task to task"""
                    if task_to_move.parent_task_id.id == requested_task.id:
                        """move task from same task"""
                        task_to_move.move_gantt_chart_task(new_position)
                    else:
                        """move task from different task"""
                        parent_task = task_to_move.parent_task_id
                        labels = parent_task.gantt_chart_labels.all()
                        if labels:
                            self._move_labels(task_to_move, labels)
                        tasks = parent_task.sub_tasks.filter(display_in_gantt_chart=True).exclude(id=task_to_move.id)
                        if tasks:
                            self._move_stage_task(task_to_move, tasks)
                        """parent task to task"""
                        labels = requested_task.gantt_chart_labels.all()
                        if labels:
                            self._move_to_labels(new_position, labels)
                        if requested_task.id != project_task.id:
                            if requested_task.is_critical_path_task:
                                task_to_move.is_critical_path_task = True
                                task_to_move.save()
                                if task_to_move.procurement_id:
                                    try:
                                        update_product_from_board_gant_chart(task_to_move, headers)
                                    except Exception as e:
                                        pass
                                update_child_tasks_true(task_to_move, headers)
                                prdecessor_cretical_task_true(task_to_move, headers=headers)
                            else:
                                task_to_move.parent_task_id = requested_task
                                task_to_move.save()
                                update_critical_path_tasks(task_to_move.board_stage, task_to_move,
                                                           project_task=project_task, headers=headers)
                        else:
                            task_to_move.parent_task_id = requested_task
                            task_to_move.save()
                            update_critical_path_tasks(task_to_move.board_stage, task_to_move,
                                                       project_task=project_task, headers=headers)
                        tasks = requested_task.sub_tasks.filter(display_in_gantt_chart=True).exclude(id=task_to_move.id)
                        if tasks:
                            self._move_to_stage_task(new_position, tasks)
                if task_to_move.task_labels:
                    """task move from label"""
                    parent_label = task_to_move.task_labels
                    if parent_label.taskss:
                        tasks = parent_label.taskss.filter(display_in_gantt_chart=True).exclude(id=task_to_move.id)
                        if tasks:
                            self._move_stage_task(task_to_move, tasks)
                    if parent_label.sub_labels:
                        labels = parent_label.sub_labels.all()
                        if labels:
                            self._move_labels(task_to_move, labels)
                    """move task and labels from requested task"""
                    if requested_task.sub_tasks:
                        tasks = requested_task.sub_tasks.all()
                        if tasks:
                            self._move_to_stage_task(new_position, tasks)
                    if requested_task.gantt_chart_labels:
                        labels = requested_task.gantt_chart_labels.all()
                        if labels:
                            self._move_to_labels(new_position, labels)
                elif not task_to_move.parent_task_id and not task_to_move.task_labels:
                    """from project"""
                    board = check_task_board(task_to_move)
                    boards = Board.objects.filter(project_id=board.project_id)
                    stages = [stage for board in boards for stage in board.board_stage_maps.all() if stage]
                    labels = [label for board in boards for label in board.gantt_chart_labels.filter \
                        (tasks__isnull=True, parent_label_id__isnull=True)]
                    for stage in stages:
                        tasks = stage.tasks.filter(parent_task_id__isnull=True, task_labels__isnull=True).exclude(
                            id=task_to_move.id)
                        self._move_stage_task(task_to_move, tasks)
                    if labels:
                        self._move_labels(task_to_move, labels)
                    """to task"""
                    if requested_task.sub_tasks:
                        tasks = requested_task.sub_tasks.filter(display_in_gantt_chart=True)
                        if tasks:
                            self._move_to_stage_task(new_position, tasks)
                    if requested_task.gantt_chart_labels:
                        labels = requested_task.gantt_chart_labels.all()
                        if labels:
                            self._move_to_labels(new_position, labels)
                if task_to_move.task_labels:
                    task_to_move.task_labels = None
                task_to_move.parent_task_id = requested_task
                task_to_move.gantt_chart_position = new_position
                task_to_move.save()
                serializer = TaskSerializer(task_to_move)
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response({'detail': 'Error, please try gain.'}, status=status.HTTP_400_BAD_REQUEST)
        if request.data.get('label_id'):
            serializer = MoveLabelTaskSerializer(data=request.data)
            if serializer.is_valid():
                label_to_move = serializer.data["label_id"]
                new_position = serializer.data["position"]
                requested_label = get_object_or_404(GanttChartLable, id=int(label_to_move))
                """from label to label move"""
                if task_to_move.task_labels:
                    if task_to_move.task_labels.id == int(request.data.get('label_id')):
                        """label is same"""
                        task_to_move.move_gantt_chart_task(new_position)
                    else:
                        """label is different"""
                        """from label"""
                        labels = task_to_move.task_labels.sub_labels.all() if task_to_move.task_labels else None
                        if labels:
                            self._move_labels(task_to_move, labels)
                        tasks = task_to_move.task_labels.taskss.filter(display_in_gantt_chart=True).exclude(
                            id=task_to_move.id)
                        if tasks:
                            self._move_stage_task(task_to_move, tasks)
                        """to label"""
                        labels = requested_label.sub_labels.all() if requested_label.sub_labels else None
                        if labels:
                            self._move_to_labels(new_position, labels)
                        tasks = requested_label.taskss.filter(display_in_gantt_chart=True).exclude(id=task_to_move.id)
                        if tasks:
                            self._move_to_stage_task(new_position, tasks)
                """from parent task move task"""
                if task_to_move.parent_task_id:
                    """from parent task, task move in label"""
                    parent_task = task_to_move.parent_task_id
                    labels = parent_task.gantt_chart_labels.all()
                    tasks = parent_task.sub_tasks.filter(display_in_gantt_chart=True).exclude(id=task_to_move.id)
                    if tasks:
                        self._move_stage_task(task_to_move, tasks)
                    if labels:
                        self._move_labels(task_to_move, labels)
                    """to label"""
                    tasks = requested_label.taskss.filter(display_in_gantt_chart=True)
                    labels = requested_label.sub_labels.all()
                    if tasks:
                        self._move_to_stage_task(new_position, tasks)
                    if labels:
                        self._move_to_labels(new_position, labels)
                elif not task_to_move.parent_task_id and not task_to_move.task_labels:
                    """from project"""
                    board = check_task_board(task_to_move)
                    boards = Board.objects.filter(project_id=board.project_id)
                    stages = [stage for board in boards for stage in board.board_stage_maps.all() if stage]
                    labels = [label for board in boards for label in board.gantt_chart_labels.filter \
                        (tasks__isnull=True, parent_label_id__isnull=True)]
                    for stage in stages:
                        tasks = stage.tasks.filter(parent_task_id__isnull=True, task_labels__isnull=True).exclude(
                            id=task_to_move.id)
                        self._move_stage_task(task_to_move, tasks)
                    if labels:
                        self._move_labels(task_to_move, labels)
                    """to label"""
                    tasks = requested_label.taskss.filter(display_in_gantt_chart=True)
                    labels = requested_label.sub_labels.all()
                    if tasks:
                        self._move_to_stage_task(new_position, tasks)
                    if labels:
                        self._move_to_labels(new_position, labels)
                if task_to_move.parent_task_id:
                    task_to_move.parent_task_id = None
                task_to_move.task_labels = requested_label
                task_to_move.gantt_chart_position = new_position
                task_to_move.save()
                serializer = TaskSerializer(task_to_move)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            pass

    def _move_labels(self, task_to_move, labels):
        for label in labels:
            if label.position > task_to_move.gantt_chart_position:
                label.position = label.position - 1
                label.save()

    def _move_stage_task(self, task_to_move, stages_tasks):
        for stage_task in stages_tasks:
            if stage_task.gantt_chart_position > task_to_move.gantt_chart_position:
                stage_task.gantt_chart_position = stage_task.gantt_chart_position - 1
                stage_task.save()

    def _move_to_labels(self, new_position, labels):
        for label in labels:
            if label.position >= new_position:
                label.position = label.position + 1
                label.save()

    def _move_to_stage_task(self, new_position, stages_tasks):
        for stage_task in stages_tasks:
            if stage_task.gantt_chart_position >= new_position:
                stage_task.gantt_chart_position = stage_task.gantt_chart_position + 1
                stage_task.save()

    @action(methods=["POST"], detail=True, url_path='copy-task')
    def copy_task(self, request, pk=None):
        serializer = CopyTaskSerializer(data=request.data)
        if serializer.is_valid():
            task_title = serializer.data['title']
            board_stage_id = serializer.data['board_stage']
            position = int(serializer.data['position'])
            checklists = serializer.data['copy_checklists']
            labels = serializer.data['copy_labels']
            attachments = serializer.data['copy_attchments']
            # comments = serializer.data['copy_comments']
            task = get_object_or_404(Task, id=pk)
            board_stage = get_object_or_404(BoardStageMap, id=board_stage_id)
            copied_task = task.copy(board_stage, task_title, checklists, labels, attachments)
            copied_task.move(position)
            if task.display_in_gantt_chart:
                boards = Board.objects.filter(project_id = board_stage.board.project_id)
                gantt_chart_position = task_gantchart_position(boards)
                copied_task.gantt_chart_position = gantt_chart_position+1
            copied_task.save()
            serializer = TaskSerializer(copied_task)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["POST"], detail=True, url_path='archive-task')
    def archive_task(self, request, pk=None):
        task = get_object_or_404(Task, id=pk)
        task.is_archived = True
        task.save()
        serializer = TaskSerializer(task)
        log_activity(task=task, description=activity_constants.TASK_ARCHIVED,
                     created_by=ast.literal_eval(request.innovo_user).get('id'))
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(methods=["POST"], detail=True, url_path='unarchive-task')
    def unarchive_task(self, request, pk=None):
        task = get_object_or_404(Task, id=pk)
        task.is_archived = False
        task.save()
        serializer = TaskSerializer(task)
        log_activity(task=task, description=activity_constants.TASK_UNARCHIVED,
                     created_by=ast.literal_eval(request.innovo_user).get('id'))
        return Response(serializer.data, status=status.HTTP_201_CREATED)


    @action(detail=True, url_path='get-labels')
    def get_labels(self, request, pk=None):
        task = get_object_or_404(Task, id=pk)
        task_labels = task.labels.all()
        labels = LabelSerializer(instance=task_labels, many=True)
        return Response(labels.data, status=status.HTTP_200_OK)

    @action(methods=["POST"], detail=True, url_path='add-label')
    def add_label(self, request, pk=None):
        serializer = TaskLabelSerializer(data=request.data)
        if serializer.is_valid():
            task = get_object_or_404(Task, id=pk)
            label = get_object_or_404(Label, id=serializer.data['label_id'])
            task.labels.add(label)
            task_labels = task.labels.all()
            labels = LabelSerializer(instance=task_labels, many=True)
            log_activity(task=task, description=activity_constants.LABEL_ADDED,
                         created_by=ast.literal_eval(request.innovo_user).get('id'))
            return Response(labels.data, status=status.HTTP_200_OK)
        else:
            return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["POST"], detail=True, url_path='remove-label')
    def remove_label(self, request, pk=None):
        serializer = TaskLabelSerializer(data=request.data)
        if serializer.is_valid():
            task = get_object_or_404(Task, id=pk)
            label = get_object_or_404(Label, id=serializer.data['label_id'])
            task.labels.remove(label)
            task_labels = task.labels.all()
            labels = LabelSerializer(instance=task_labels, many=True)
            log_activity(task=task, description=activity_constants.LABEL_REMOVE,
                         created_by=ast.literal_eval(request.innovo_user).get('id'))
            return Response(labels.data, status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["GET"], detail=True, url_path='get-members')
    def get_members(self, request, pk=None):
        task = get_object_or_404(Task, id=pk)
        task_members = task.task_members.all()
        serializer = TaskMemberSerializer(instance=task_members, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=["POST"], detail=True, url_path='add-member')
    def add_member(self, request, pk=None):
        serializer = TaskMemberSerializer(data={'user_id': request.data['user_id'],
                                                'task': pk,
                                                'created_by': ast.literal_eval(request.innovo_user).get('id')})
        if not serializer.is_valid():
            return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        log_activity(task=get_object_or_404(Task, id=pk), description=activity_constants.MEMBER_ADDED,
                     created_by=ast.literal_eval(request.innovo_user).get('id'))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=["POST"], detail=True, url_path='remove-member')
    def remove_member(self, request, pk=None):
        try:
            task_member = TaskMember.objects.get(user_id=request.data.get("user_id"),
                                                 task=get_object_or_404(Task, id=pk))
            task_member.delete()
            log_activity(task=get_object_or_404(Task, id=pk),
                         description=activity_constants.MEMBER_REMOVED,
                         created_by=ast.literal_eval(request.innovo_user).get('id'))
            return Response({'detail': 'Task member removed successfully.'}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({'detail': 'user id does not exists.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["POST"], detail=False, url_path='create-product-task')
    def create_product_task(self, request, pk=None):
        task_data = {}
        task_data['created_by'] = ast.literal_eval(request.innovo_user).get('id')
        allowed_chars = ''.join((string.ascii_letters, string.digits))
        task_data['share_key'] = ''.join(random.choice(allowed_chars) for _ in range(16))
        gantt_positions = [0]
        boards = Board.objects.filter(project_id=request.data.get('project_id'))
        if boards:
            board = Board.objects.filter(project_id=request.data.get('project_id')).aggregate(Min('id')).get('id__min')
            board_stage = BoardStageMap.objects.filter(board_id=board).aggregate(Min('id')).get('id__min')
            stage = get_object_or_404(BoardStageMap, id=board_stage)
            if board_stage:
                gantt_positions.append(task_gantchart_position(boards))
                task_data['board_stage'] = board_stage
                task_position = stage.tasks.filter(is_display_in_board=True).aggregate(Max('position')).get(
                    'position__max')
                task_data['position'] = task_position + 1 if task_position else 1
                if request.data.get('is_display_in_board'):
                    task_data['is_display_in_board'] = True
                if request.data.get('product_id'):
                    task_data['procurement_id'] = request.data.get('product_id')
                    task_data['is_display_in_board'] = True
                task_data['gantt_chart_position'] = max(gantt_positions) + 1 if gantt_positions else 1
                task_data['display_in_gantt_chart'] = True
                task_data['title'] = request.data.get('title')
                task_data['description'] = request.data.get('description')
                task_data['start_date'] = request.data.get('start_date') if request.data.get('start_date') else date.today()
                task_data['end_date'] = request.data.get('end_date') if request.data.get('end_date') else date.today()
                task_data['due_date'] = request.data.get('due_date') if request.data.get('due_date') else task_data[
                    'end_date']
                task_data['is_display_in_dashboard'] = request.data.get('is_display_in_dashboard') \
                    if request.data.get('is_display_in_dashboard') else False

                serializer = GanttTaskSerializer(data=task_data)
                if not serializer.is_valid():
                    return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)
                serializer.save()
                new_task = get_object_or_404(Task, pk=serializer.data.get('id'))
                end_date = new_task.end_date
                max_date = new_task.board_stage.tasks.exclude(id=serializer.data['id']).aggregate(Max('end_date')).get(
                    'end_date__max')
                if max_date:
                    if end_date > max_date:
                        new_task.is_critical_path_task = True
                        tasks = new_task.board_stage.tasks.filter(end_date__lte=max_date).exclude(id=new_task.id)
                        for task in tasks:
                            # Todo: task with target
                            task_dependancies = TaskDependencyMap.objects.filter(target = task.id)
                            if task_dependancies:
                                for dependancy in task_dependancies:
                                    if dependancy.source:
                                        if dependancy.source.is_critical_path_task:
                                            task.is_critical_path_task = True
                                            task.save()
                            else:
                                task.is_critical_path_task = False
                                task.save()
                            if task.procurement_id:
                                try:
                                    update_product_from_board_gant_chart(task, {'Authorization': request.headers.get('Authorization')})
                                except Exception as e:
                                    pass
                    if end_date == max_date:
                        new_task.is_critical_path_task = True
                else:
                    new_task.is_critical_path_task = True
                new_task.save()
                serializer = GanttTaskSerializer(new_task)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response({'message': 'please try again.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["POST"], detail=True, url_path='update-product-task')
    def update_product_task(self, request, pk=None):
        product_task = get_object_or_404(Task, id=pk)
        serializer = GanttTaskSerializer(product_task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        project_task = self._get_project_task(product_task.board_stage,
                                              headers={"Authorization": request.headers.get('Authorization')})
        updated_task = critical_path_tasks(product_task.board_stage,
                                           product_task,
                                           project_task=project_task,
                                           headers={'Authorization': request.headers.get('Authorization')})
        serializer = GanttTaskSerializer(updated_task)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

    @action(methods=["DELETE"], detail=True, url_path='remove-product-task')
    def remove_product_task(self, request, pk=None):
        """Remove task from product."""
        headers = {"Authorization": request.headers.get('Authorization')}
        task = get_object_or_404(Task, id=pk)
        baord_stage = task.board_stage
        task_end_date = task.end_date
        for predecessor in task.predecessors.all():
            if predecessor.target:
                prdecessor_cretical_task(task, headers)
            predecessor.delete()
        for successor in task.successors.all():
            if successor.target:
                prdecessor_cretical_task(successor.target, headers)
            successor.delete()
        task.delete()
        self._update_critical_path_tasks(baord_stage, task_end_date,
                                         headers={'Authorization': request.headers.get('Authorization')})
        return Response(status=status.HTTP_204_NO_CONTENT)


    @action(methods=["POST"], detail=False, url_path='create-ganttchart-task')
    def create_gantt_task(self, request, pk=None):
        """
        create task from ganttchart.
        """
        headers = {'Authorization': request.headers.get('Authorization')}
        task_data = {}
        task_data['created_by'] = ast.literal_eval(request.innovo_user).get('id')
        allowed_chars = ''.join((string.ascii_letters, string.digits))
        task_data['share_key'] = ''.join(random.choice(allowed_chars) for _ in range(16))
        gantt_positions = [0]
        project_task = None
        pay_load = {}
        task_ids = [0]
        board_stage = get_object_or_404(BoardStageMap, id=request.data.get('board_stage'))
        if request.data.get('project_id'):
            response_data = get_project_details(request.data.get('project_id'), headers)
            if response_data:
                task_name = response_data.get('name') + "_" + str(response_data.get('id'))
                project_task = Task.objects.filter(title=response_data.get('name'), task_type=task_name).first()
            boards = Board.objects.filter(project_id=request.data.get('project_id'))
            board = Board.objects.filter(project_id=request.data.get('project_id')).aggregate(Min('id')).get('id__min')
            if board:
                board_stage = BoardStageMap.objects.filter(board_id=board).aggregate(Min('id')).get('id__min')
                if board_stage:
                    gantt_positions.append(task_gantchart_position(boards))
                    for board in boards:
                        if project_task:
                            position = board.gantt_chart_labels.filter(tasks=project_task.id).aggregate(Max('position')).get('position__max')
                            if position:
                                gantt_positions.append(position)
                    task_data['board_stage'] = board_stage
                    board_stage = get_object_or_404(BoardStageMap, pk=board_stage)
                    task_position = board_stage.tasks.filter(is_display_in_board=True).aggregate(Max('position')).get(
                        'position__max')
                    task_data['position'] = task_position + 1 if task_position else 1
                    if request.data.get('is_display_in_board'):
                        task_data['is_display_in_board'] = True
                    if request.data.get('product_id'):
                        task_data['procurement_id'] = request.data.get('product_id')
                        task_data['is_display_in_board'] = True
                else:
                    return Response({'message': 'please try again.'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({'message': 'please try again.'},status=status.HTTP_400_BAD_REQUEST)
        if not project_task:
            project_id = board_stage.board.project_id
            response_data = get_project_details(project_id, headers)
            task_name = response_data.get('name') + "_" + str(response_data.get('id'))
            project_task = Task.objects.filter(title=response_data.get('name'), task_type=task_name).first()
            task_ids.append(project_task.id)
        if request.data.get('board_stage') and not request.data.get('task_labels') and not request.data.get('parent_task_id'):
            """tasks created from ganttchart but its parent is stage."""
            boards = Board.objects.filter(project_id=board_stage.board.project_id)
            max_position = task_gantchart_position(boards)
            if max_position:
                gantt_positions.append(max_position)
            for board in boards:
                position = GanttChartLable.objects.filter(board=board.id).aggregate(Max('position')).get('position__max')
                if position:
                    gantt_positions.append(position)
            task_data['is_display_in_board'] = True
            position = board_stage.tasks.aggregate(Max('position')).get('position__max')
            task_data['position'] = position + 1 if position else 1
            task_data['is_display_in_board'] = True
            task_data['board_stage'] = request.data.get('board_stage')
        elif request.data.get('task_labels') and request.data.get('board_stage') and not request.data.get('parent_task_id'):
            """task is created from ganttchart but parent is label"""
            gantchart_label = get_object_or_404(GanttChartLable, pk=int(request.data.get('task_labels')))
            task_position = gantchart_label.taskss.aggregate(Max('gantt_chart_position')).get('gantt_chart_position__max')
            if task_position:
                gantt_positions.append(task_position)
            label_max_position = gantchart_label.sub_labels.aggregate(Max('position')).get('position__max')
            if label_max_position:
                gantt_positions.append(label_max_position)
            position = Task.objects.filter(board_stage=request.data.get('board_stage'), is_display_in_board=True)\
                .aggregate(Max('position')).get('position__max')
            task_data['position'] = position + 1 if position else 1
            task_data['is_display_in_board'] = True
            task_data['board_stage'] = request.data.get('board_stage')
            task_data['task_labels'] = request.data.get('task_labels')
        elif request.data.get('parent_task_id') and request.data.get('board_stage') and not request.data.get('task_labels'):
            """create task with task as parent."""
            parent_task = get_object_or_404(Task, pk=int(request.data.get('parent_task_id')))
            stage_position = board_stage.tasks.aggregate(Max('position')).get('position__max')
            task_data['position'] = stage_position + 1 if stage_position else 1
            task_data['is_display_in_board'] = True
            task_data['board_stage'] = request.data.get('board_stage')
            task_position = parent_task.sub_tasks.aggregate(Max('gantt_chart_position')).get('gantt_chart_position__max')
            label_position = parent_task.gantt_chart_labels.aggregate(Max('position')).get('position__max')
            if task_position:
                gantt_positions.append(task_position)
            if label_position:
                gantt_positions.append(label_position)
            task_data['parent_task_id'] = request.data.get('parent_task_id')
        else:
            return Response({"detail": "please provide 'stage id' and 'task id' or 'label id' as parent."},
                            status=status.HTTP_400_BAD_REQUEST)
        task_data['start_date'] = request.data.get('start_date') if request.data.get('start_date') else date.today()
        task_data['end_date'] = request.data.get('end_date') if request.data.get('end_date') else task_data['start_date']
        if request.data.get('duration'):
            end_date = datetime.datetime.strptime(task_data['start_date'], '%Y-%m-%d') + timedelta(int(request.data.get('duration')))
            task_data['end_date'] = str(end_date.date())
        else:
            if not request.data.get('end_date'):
                task_data['end_date'] = task_data['start_date']
        task_data['gantt_chart_position'] = max(gantt_positions) + 1 if gantt_positions else 1
        task_data['display_in_gantt_chart'] = True
        task_data['title'] = request.data.get('title')
        task_data['description'] = request.data.get('description')
        task_data['progress'] = request.data.get('progress') if request.data.get('progress') else 0.0
        task_data['due_date'] = request.data.get('due_date') if request.data.get('due_date') else task_data['end_date']
        task_data['is_display_in_dashboard'] = request.data.get('is_display_in_dashboard') \
            if request.data.get('is_display_in_dashboard') else False
        serializer = GanttTaskSerializer(data=task_data)
        if not serializer.is_valid():
            return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        # ToDo: below part for critical path
        new_task = Task.objects.get(id=serializer.data.get('id'))
        if request.data.get('is_display_in_board') or task_data.get('is_display_in_board'):
            end_date = new_task.end_date
            task_ids.append(new_task.id)
            max_date = new_task.board_stage.tasks.exclude(id__in=task_ids).aggregate(Max('end_date')).get('end_date__max')
            if max_date:
                if end_date > max_date:
                    new_task.is_critical_path_task = True
                    tasks = new_task.board_stage.tasks.filter(end_date__lte=max_date).exclude(id=new_task.id)
                    for task in tasks:
                        task.is_critical_path_task = False
                        task.save()
                        update_child_tasks_false(task, headers)
                        prdecessor_cretical_task(task, headers)
                if end_date == max_date:
                    new_task.is_critical_path_task = True

            else:
                new_task.is_critical_path_task = True
            new_task.save()
        start_date = datetime.datetime.strptime(serializer.data.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(serializer.data.get('end_date'), '%Y-%m-%d').date()
        response_data = {
            "text": serializer.data.get('title'),
            "duration": (end_date - start_date).days,
            "end_date": end_date,
            "start_date": start_date,
            "position": serializer.data.get('gantt_chart_position'),
            "progress": serializer.data.get('progress'),
            "parent": 0,
            "is_display_in_dashboard": serializer.data.get('is_display_in_dashboard'),
            "description": serializer.data.get('description'),
            "id": serializer.data.get('id')
        }
        if serializer.data.get('parent_task_id') and serializer.data.get('board_stage'):
            response_data['parent'] = "task-" + str(serializer.data.get('parent_task_id'))
        if serializer.data.get('task_labels') and serializer.data.get('board_stage'):
            response_data['parent'] = "label-" + str(serializer.data.get('task_labels'))
        if new_task.is_critical_path_task:
            response_data['is_critical_path_item'] = True
        return Response(serializer.errors if serializer.errors else response_data, status=status.HTTP_201_CREATED)


class CategoryViewSet(ModelViewSet):
    """This class is for REST APIs to Category."""
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CategoryFilter

    def get_permissions(self):
        if self.action in 'list':
            return (AllowAny(),)
        else:
            return (IsSuperUser(),)


class LabelViewSet(ModelViewSet):
    """This class is for REST APIs to label."""
    serializer_class = LabelSerializer
    queryset = Label.objects.all()
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']
    filter_backends = (DjangoFilterBackend,)
    filterset_class = LabelFilter
    filterset_fields = ['board', 'project_id']
    permission_classes = (AllowAny,)


    def create(self, request, *args, **kwargs):
        project_id = request.data.get('project_id')
        color_code = request.data.get('color_code')
        if not color_code:
            color_code = '#eb5a46'
        if not project_id:
            board = get_object_or_404(Board, id=request.data.get('board'))
            project_id = board.project_id
        data = {'name': request.data.get('name'),
                'color_code': color_code,
                'board': request.data.get('board'),
                'project_id': project_id}
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def list(self, request, *args, **kwargs):
        board_id = request.query_params.get('board', None)
        if board_id:
            board = get_object_or_404(Board, id=board_id)
            project_id = board.project_id
            labels = self.queryset.filter(Q(board=board_id) | Q(project_id=project_id))
            serializer = self.get_serializer(labels, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            labels = self.queryset.all()
            serializer = self.get_serializer(labels, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)



    @action(methods=['GET'], detail=False, url_path='project-labels')
    def project_labels(self, request, pk=None):
        project_id = request.query_params.get('project_id', None)
        if project_id:
            labels = self.queryset.filter(Q(board__project_id__contains=project_id) | Q(project_id=project_id)).distinct('name')
            serializer = self.get_serializer(labels, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response({"Message": "Please try again with project id"}, status=status.HTTP_400_BAD_REQUEST)



class BoardMemberViewSet(ModelViewSet):
    """This class is for REST APIs to BoardMember."""
    serializer_class = BoardMemberSerializer
    queryset = BoardMember.objects.all()
    http_method_names = ['get', 'post', 'delete']
    filter_backends = (DjangoFilterBackend,)
    filterset_class = BoardMemberFilter

    def get_permissions(self):
        if self.action == 'remove_project_member':
            return (AllowAny(), )
        return (IsSuperUserOrProjectAdminOrHasBoardPermission(ACTION_PERMISSIONS_MAP[self.action]),)

    @action(methods=['POST'], detail=False, url_path='remove-project-member')
    def remove_project_member(self, request, pk=None):
        project_id = request.data.get('project_id')
        user_id = request.data.get('user_id')
        boards = Board.objects.filter(project_id=project_id)
        board_members = [board_member for board in boards for board_member in self.queryset.filter(user_id=int(user_id), board=board.id) if board_member]
        for board_member in board_members:
            board_member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BoardStageViewSet(ModelViewSet):
    """This class is for REST APIs to BoardStageMap.."""
    serializer_class = BoardStageSerializer
    queryset = BoardStageMap.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = BoardStageMapFilter

    def get_permissions(self):
        if self.action == 'get_gantt_chart_tasks':
            return (ProjectAdminOrBoardMemberOrBoardPrmission('can_view_ganttchart'),)
        else:
            return (IsSuperUserOrProjectAdminOrBoardMember(),)

    def get_serializer_class(self):

        if self.action == 'create':
            return CreateBoardStageSerializer
        return BoardStageSerializer

    def create(self, request):
        serializer = CreateBoardStageSerializer(data=request.data)
        if serializer.is_valid():
            board_id = serializer.data['board_id']
            stage_name = serializer.data['stage_name']
            stage = get_or_create_stage(stage_name)
            position = BoardStageMap.objects.filter(board_id=board_id).aggregate(Max('position')).get('position__max')
            max_position = position + 1 if position else 1
            board_stage_map = BoardStageMap.objects.create(board_id=board_id, stage=stage, position=max_position)
            serialize = BoardStageSerializer(board_stage_map)
            return Response(serialize.data, status=status.HTTP_201_CREATED)
        else:
            return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """remove stage from board ."""
        header = request.headers.get('Authorization')
        stage_to_remove = self.get_object()
        stages = stage_to_remove.board.board_stage_maps.filter().exclude(id=stage_to_remove.id)
        for task in stage_to_remove.tasks.all():
            remove_task(task, header)
        self._remove_stage_from_board(stage_to_remove, stages)
        return super(BoardStageViewSet, self).destroy(request, *args, **kwargs)

    def _remove_stage_from_board(self, stage_to_remove, stages):
        for stage in stages:
            if stage.position > stage_to_remove.position:
                stage.position = stage.position - 1
                stage.save()

    @action(methods=["POST"], detail=True, url_path='update-stage-name')
    def update_stage_name(self, request, pk=None):
        board_stage_map = get_object_or_404(BoardStageMap, id=pk)
        board_stage_map.stage.name = request.data.get('name')
        board_stage_map.stage.save()
        return Response({}, status=status.HTTP_202_ACCEPTED)

    @action(methods=["POST"], detail=True, url_path='archive-board-stage')
    def archive_board_stage(self, request, pk=None):
        board_stage = BoardStageMap.objects.get(id=pk)
        board_stage.is_archived = True
        board_stage.save()
        return Response({}, status=status.HTTP_201_CREATED)

    @action(methods=["POST"], detail=True, url_path='unarchive-board-stage')
    def unarchive_board_stage(self, request, pk=None):
        board_stage = BoardStageMap.objects.get(id=pk)
        board_stage.is_archived = False
        board_stage.save()
        return Response({}, status=status.HTTP_201_CREATED)

    @action(methods=["POST"], detail=True, url_path='copy-board-stage')
    def copy_board_stage(self, request, pk=None):
        serializer = CopyBoardStageSerializer(data=request.data)
        if serializer.is_valid():
            position = serializer.data['position']
            stage_name = serializer.data['stage_name']
            board_stage_to_copy = BoardStageMap.objects.get(id=pk)
            stage = get_or_create_stage(stage_name)
            try:
                copied_board_stage = BoardStageMap.objects.create(stage=stage, board=board_stage_to_copy.board,
                                                                  position=position)
                copied_board_stage.copy(position)
                for task in board_stage_to_copy.tasks.all():
                    task.copy(copied_board_stage, task.title, task.checklists, task.labels,
                              task.attachments, task.activities)
                serializer = BoardStageSerializer(copied_board_stage)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except IntegrityError as e:
                return Response({'detail': 'Stage with this name already exist'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["POST"], detail=True, url_path='move-board-stage')
    def move_board_stage(self, request, pk=None):
        serializer = MoveBoardStageSerializer(data=request.data)
        if serializer.is_valid():
            board_state_to_move = BoardStageMap.objects.get(id=pk)
            new_position = int(serializer.data["position"])
            board_state_to_move.move(new_position)
            serializer = BoardStageSerializer(board_state_to_move)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["GET"], detail=True, url_path='get-gantt-chart-tasks')
    def get_gantt_chart_tasks(self, request, pk=None):
        data = []
        links = []
        stage_list = []
        task_data = {}
        auth = AuthService()
        response = auth.get_project_dtails_by_id(pk, {'Authorization': request.headers.get('Authorization')})
        project_level_task = None
        all_progress = []

        if response.status_code == 200:
            response_data = json.loads(response.text)
            task_name = response_data.get('name') + "_" + str(response_data.get('id'))
            project_task = Task.objects.filter(title=response_data.get('name'), task_type=task_name).first()
            if not project_task:
                task_data['created_by'] = ast.literal_eval(request.innovo_user).get('id')
                allowed_chars = ''.join((string.ascii_letters, string.digits))
                task_data['share_key'] = ''.join(random.choice(allowed_chars) for _ in range(16))

                task_data['title'] = response_data.get('name')
                task_data['description'] = response_data.get('name')
                task_data['display_in_gantt_chart'] = True
                task_data['is_display_in_board'] = False
                task_data['gantt_chart_position'] = 1
                task_data['task_type'] = task_name
                task_data['start_date'] = response_data.get('start_date') if response_data.get(
                    'start_date') else date.today()
                task_data['end_date'] = response_data.get('estimated_completion_date') if response_data.get(
                    'estimated_completion_date') else date.today()
                task_data['due_date'] = task_data['end_date']
                ser = GanttTaskSerializer(data=task_data)
                if ser.is_valid():
                    ser.save()
                else:
                    return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)
                project_level_task = ser.data.get('id')
            else:
                project_task.progress = 0.0
                project_task.gantt_chart_position = 1
                project_task.start_date = date.today()
                project_task.end_date = date.today()
                project_task.save()
                project_level_task = project_task.id
            project_task = Task.objects.get(id=project_level_task)
            board = Board.objects.filter(project_id=pk).aggregate(Min('id')).get('id__min')
            if board:
                board_stage = BoardStageMap.objects.filter(board_id=board).aggregate(Min('id')).get('id__min')
                bsm = BoardStageMap.objects.get(id=board_stage)
                project_task.board_stage = bsm
                project_task.save()
            boards = Board.objects.filter(project_id=pk)
            if boards:
                stages = [stage for board in boards for stage in board.board_stage_maps.all() if stage]
                tasks = [task for stage in stages for task in stage.tasks.filter(display_in_gantt_chart=True)\
                    .exclude(id=project_task.id) if task]
                stage_list = [{'id': stage.id,
                               'name': stage.stage.name,
                               'board_name': stage.board.name,
                               'board_id': stage.board.id} for board in boards for stage in \
                              board.board_stage_maps.all() if stage]
                for task in tasks:
                    if task:
                        if not task.parent_task_id and not task.task_labels:
                            position = []
                            gant_chart_position = project_task.sub_tasks.all().aggregate(Max('gantt_chart_position')).get('gantt_chart_position__max')
                            if gant_chart_position:
                                position.append(gant_chart_position)
                            label_position = GanttChartLable.objects.filter(tasks=project_level_task, board=task.board_stage.board.id).aggregate(Max('position')).get('position__max')
                            if label_position:
                                position.append(label_position)
                            task.parent_task_id = project_task
                            task.gantt_chart_position = max(position) + 1 if position else 1
                            task.save()
                        task_datas = get_tasks(task)
                        if task_datas:
                            for task_data in task_datas:
                                if task_data.get('parent') == 'task-' + str(project_task.id):
                                    all_progress.append(task_data.get('progress'))
                                if task_data:
                                    data.append(task_data)

                labels = [label for board in boards for label in board.gantt_chart_labels.all() if label]
                for label in labels:
                    if label:
                        if not label.tasks and not label.parent_label_id:
                            position = []
                            gant_chart_position = task_gantchart_position(boards)
                            if gant_chart_position:
                                position.append(gant_chart_position)
                            label_position = GanttChartLable.objects.filter(tasks=project_level_task).aggregate(
                                Max('position')).get('position__max')
                            if label_position:
                                position.append(label_position)
                            label.tasks = project_task
                            label.position = max(position) + 1 if position else 1
                            label.save()
                        label_datas = get_labels(label)
                        if label_datas:
                            for label_data in label_datas:
                                if label_data.get('parent') == 'task-' + str(project_task.id):
                                    all_progress.append(label_data.get('progress'))
                                data.append(label_data)
                for data_dict in data:
                    predecessor = data_dict.pop('links', None)
                    if predecessor:
                        for link in predecessor:
                            links.append(link)
                progress_avg = round(sum(all_progress)/len(all_progress), 3) if all_progress else 0.00
                start_dates = nested_lookup('start_date', data)
                start_date = min(start_dates) if start_dates else project_task.start_date
                end_dates = nested_lookup('end_date', data)
                end_date = max(end_dates) if end_dates else project_task.end_date
                progress = round(progress_avg, 3) if progress_avg else project_task.progress
                project_task.progress = progress
                project_task.end_date = end_date if end_date > project_task.end_date else project_task.end_date
                project_task.start_date = start_date if start_date < project_task.start_date else project_task.start_date
                project_task.save()
                gantt_chart = self._get_project_level_task(project_task)
                data.append(gantt_chart)
                return Response({'data': data, 'links': links, 'stages': stage_list}, status=status.HTTP_200_OK)
            gantt_chart = self._get_project_level_task(project_task)
            data.append(gantt_chart)
            return Response({"data": data, 'links': links, 'stages': stage_list}, status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({'detail': 'Given project does not exists'}, status=status.HTTP_400_BAD_REQUEST)

    def _get_project_level_task(self, project_task):
        gantt_chart = {'id': 'task-' + str(project_task.id),
                       'text': project_task.title,
                       'start_date': project_task.start_date,
                       'end_date': project_task.end_date,
                       "duration": (project_task.end_date - project_task.start_date).days,
                       'progress': project_task.progress,
                       'parent': 0,
                       'position': project_task.gantt_chart_position,
                       'board_id': 0,
                       'stage_id': project_task.board_stage.id if project_task.board_stage else 0,
                       'board_name': 0,
                       'description': project_task.description,
                       'is_display_in_dashboard': project_task.is_display_in_dashboard
                       }
        return gantt_chart


class BoardViewSet(ModelViewSet):
    """This class is for REST APIs to Board."""
    serializer_class = BoardSerializer
    queryset = Board.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = BoardFilter

    def get_permissions(self):
        action_permission_map = {
            'list': 'can_view_board',
            'retrieve': 'can_view_board',
            'destroy': 'can_delete_board',
            'create': 'can_add_board',
            'update': 'can_edit_board',
            'partial_update': 'can_edit_board',
            'get_members': 'can_view_board',
            'add_member': 'can_add_board',
            'add_board_members': 'can_add_board',
            'remove_member': 'can_delete_board',
            'get_key_tasks': 'can_view_project_details',
            'get_project_cmpletion_status': 'can_view_project_details',
            'get_task_schudels': 'can_view_project_details',
            'get_cretical_path_tasks': 'can_view_project_details',
        }
        if self.action in ('add_to_favourite', 'remove_from_favourite', 'add_member'):
            return (IsSuperUserOrProjectAdminOrBoardMember(),)
        if self.action in action_permission_map.keys():
            return (ProjectAdminOrBoardMemberOrBoardPrmission(action_permission_map[self.action]),)
        if self.action == 'board_detail':
            return (AllowAny(),)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BoardDetailSerializer
        elif self.action == 'board_detail':
            return BoardLabelDetailSerializer
        else:
            return BoardSerializer

    def list(self, request, *args, **kwargs):
        context = {'request': request}
        user = ast.literal_eval(request.innovo_user)
        project_id = self.request.query_params.get('project_id', None)
        boards = Board.objects.filter(project_id=project_id)
        if user.get('is_superuser'):
            serializer = BoardSerializer(boards, many=True, context=context)
            return Response(serializer.data, status=status.HTTP_200_OK)
        elif user.get('is_active') or user.get('is_staff'):
            boards = boards.filter(board_members__user_id=user.get('id'))
            serializer = BoardSerializer(boards, many=True, context=context)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            Response([], status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        """
        Remove
        :param request:
        :param args: board id
        :param kwargs:
        :return: null
        """
        header = request.headers.get('Authorization')
        board = self.get_object()
        stages = board.board_stage_maps.all()
        for stage in stages:
            tasks = stage.tasks.all()
            for task in tasks:
                response = remove_task(task, header)
                if not response:
                    return Response({'Message': 'please try again'})
            stage.delete()
        return super(BoardViewSet, self).destroy(request, *args, **kwargs)

    @action(methods=["POST"], detail=True, url_path='board-detail')
    def board_detail(self, request, pk=None):
        """
        :param request: title test of label ids
        :param pk:
        :return: filtered board object
        """
        context = {'request': request}
        try:
            board = get_object_or_404(Board, id=pk)
            serializer = BoardLabelDetailSerializer(board, context=context)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'detail': 'Error, No Board tasks with Label or title matches. please try again.'},
                status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["POST"], detail=False, url_path='add-board-members')
    def add_board_members(self, request, pk=None):
        created_by = ast.literal_eval(request.innovo_user).get('id')
        user_id = request.data.get('user_id')
        board_list = request.data.getlist('boards')
        if board_list:
            board_member_boards = BoardMember.objects.filter(user_id=user_id)
            for board_member in board_member_boards:
                if board_member.board.id not in board_list:
                    if board_member.board.project_id == int(request.data.get('project_id')):
                        board_member.delete()
            for board in board_list:
                data = {'created_by': created_by,
                        'user_id': user_id,
                        'board': board
                        }
                serializer = BoardMemberSerializer(data=data)
                if serializer.is_valid():
                    serializer.save()
                else:
                    Response({'detail': 'Error, please try again.'},
                             status=status.HTTP_400_BAD_REQUEST)
            return Response({'detail': 'created successfully'}, status=status.HTTP_200_OK)
        return Response({'detail': 'Error, please try again.'},
                        status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["POST"], detail=True, url_path='add-to-favourite')
    def add_to_favourite(self, request, pk=None):
        auth_service = AuthService()
        auth_service.add_board_to_favourites({'Authorization': request.headers.get('Authorization')}, pk)
        return Response({}, status=status.HTTP_200_OK)

    @action(methods=["POST"], detail=True, url_path='remove-from-favourite')
    def remove_from_favourite(self, request, pk=None):
        auth_service = AuthService()
        auth_service.remove_board_from_favourites({'Authorization': request.headers.get('Authorization')}, pk)
        return Response({}, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=True, url_path='get-members')
    def get_members(self, request, pk=None):
        board = get_object_or_404(Board, id=pk)
        board_members = board.board_members.all()
        serializer = BoardMemberSerializer(instance=board_members, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=["POST"], detail=True, url_path='add-member')
    def add_member(self, request, pk=None):
        serializer = BoardMemberSerializer(data={'user_id': request.data['user_id'],
                                                 'board': pk,
                                                 'created_by': ast.literal_eval(request.innovo_user).get('id')})
        if not serializer.is_valid():
            return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        log_activity(task=get_object_or_404(Task, id=pk), description=activity_constants.MEMBER_ADDED,
                     created_by=ast.literal_eval(request.innovo_user).get('id'))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=["POST"], detail=True, url_path='remove-member')
    def remove_member(self, request, pk=None):
        try:
            board_member = BoardMember.objects.get(user_id=request.data.get("user_id"),
                                                   board=get_object_or_404(Board, id=pk))
            board_member.delete()
            return Response({'detail': 'Task member removed successfully.'}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({'detail': 'user id does not exists.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['GET'], detail=True, url_path='get-key-tasks')
    def get_key_tasks(self, request, pk=None):
        """get all key tasks."""
        boards = Board.objects.filter(project_id=pk)
        serializer = GanttBoardDetailSerializer(boards, many=True)
        task_list = [tasks for tasks in list(nested_lookup('tasks', serializer.data)) if tasks]
        all_task = [{"id": task.get('id'),
                     "title": task.get('title'),
                     "description": task.get('description'),
                     "due_date": task.get('due_date')} for tasks in task_list for task in tasks if \
                    task.get('is_key_task')]
        return Response(all_task, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=True, url_path='get-project-completion-status')
    def get_project_cmpletion_status(self, request, pk=None):
        auth = AuthService()
        response = auth.get_project_dtails_by_id(pk, {'Authorization': request.headers.get('Authorization')})
        project_level_task = None
        if response.status_code == 200:
            response_data = json.loads(response.text)
            task_name = response_data.get('name') + "_" + str(response_data.get('id'))
            project_task = Task.objects.filter(title=response_data.get('name'), task_type=task_name).first()
            if project_task:
                return Response({"progress": round(project_task.progress * 100)}, status=status.HTTP_200_OK)
            else:
                return Response({"progress": 0.0}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"progress": 0.0}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["GET"], detail=True, url_path='get-task-schedule')
    def get_task_schudels(self, request, pk=None):
        """
        Task scheudule's for the dashboard.
        """
        data = []
        boards = Board.objects.filter(project_id=pk)
        if boards:
            stages = [stage for board in boards for stage in board.board_stage_maps.all() if stage]
            tasks = [task for stage in stages for task in stage.tasks.filter(display_in_gantt_chart=True) if task]
            for task in tasks:
                progress_list = []
                task_detail = {}
                progress = self._task_progress(progress_list, task)
                task_detail['progress'] = int((sum(progress) / len(progress)) * 100)
                if task.is_display_in_dashboard and task_detail['progress'] < 100:
                    task_detail['id'] = task.id
                    task_detail['task'] = task.title
                    task_detail['start_date'] = task.start_date
                    task_detail['end_date'] = task.end_date
                    # progress = self._task_progress(progress_list, task)
                    # task_detail['progress'] = int((sum(progress) / len(progress)) * 100)
                    try:
                        from itertools import chain
                        task_detail['task_members'] = list(chain(*task.task_members.all().values_list('user_id')))
                    except Exception as e:
                        pass
                    for label in task.labels.all():
                        task_detail['color_code'] = label.color_code if label else "#61bd4f"
                        break
                    else:
                        task_detail['color_code'] = "#61bd4f"
                    data.append(task_detail)
        return Response(data, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=False, url_path='get-cretical-path-tasks')
    def get_cretical_path_tasks(self, request, pk=None):
        """
        Task cretical tasks for the dashboard...
        """
        procurement_service = ProcurementService()
        project_id = request.query_params.get('project_id')
        data = []
        boards = Board.objects.filter(project_id=project_id)
        if boards:
            stages = [stage for board in boards for stage in board.board_stage_maps.all() if stage]
            tasks = [task for stage in stages for task in stage.tasks.filter(display_in_gantt_chart=True) if task]
            for task in tasks:
                task_detail = {}
                if task.is_critical_path_task:
                    task_detail['id'] = task.id
                    task_detail['task'] = task.title
                    task_detail['start_date'] = task.start_date
                    task_detail['end_date'] = task.end_date
                    task_detail['status'] = False
                    if task.procurement_id:
                        try:
                            response = procurement_service.get_cretical_path_item(task.procurement_id, {
                                "Authorization": request.headers.get('Authorization')})
                            if response.status_code == 200:
                                response_data = json.loads(response.text)
                                for resp_data in response_data:
                                    task_detail['status'] = resp_data.get('is_purchased')
                        except Exception as e:
                            pass
                    data.append(task_detail)
        return Response(data, status=status.HTTP_200_OK)


    def _task_progress(self, progress_list, task):
        for task in task.sub_tasks.all():
            progress_list.append(task.progress)
            self._task_progress(progress_list, task)
        progress_list.append(task.progress)
        return progress_list


class TaskDependancyViewSet(ModelViewSet):
    """
    TaskDependancyViewSet for predecessor and successors.
    """

    serializer_class = TaskDependencyMapSerializer
    queryset = TaskDependencyMap.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filterset_fields = ('source', 'target')

    def get_permissions(self):
        action_permissions_map = {
            'list': 'can_view_board',
            'retrieve': 'can_view_board',
            'destroy': 'can_delete_board',
            'create': 'can_add_board',
            'update': 'can_edit_board',
            'partial_update': 'can_edit_board',
            'ganttchart_task_predecessor': 'can_edit_ganttchart',
        }
        return (ActivityCheckListPredecessorPermission(action_permissions_map[self.action]),)

    def create(self, request, *args, **kwargs):
        """
        Create task dependancymap.
        """
        headers = {"Authorization": request.headers.get('Authorization')}
        delay = int(request.data.get('delay'))
        source_task_list = []
        serializer = TaskDependencyMapSerializer(data=request.data)
        if serializer.is_valid():
            source_tasks = self._source_target(int(request.data.get('source')),
                                               int(request.data.get('target')))
            task_dependancy = TaskDependencyMap.objects.filter(source=request.data.get('source'),
                                                               target=request.data.get('target'),
                                                               type=request.data.get('type'))
            if task_dependancy or source_tasks:
                return Response({"detail": "Same type predecessor is available, please try again with different"},
                                status=status.HTTP_400_BAD_REQUEST)
            else:
                serializer.save()
                task_dependancy = TaskDependencyMap.objects.get(id=serializer.data.get('id'))
                delay = is_critical_path_delay_task_dependancy(task_dependancy, delay, headers)
                data = {"id": serializer.data.get('id'),
                        'source': serializer.data.get('source'),
                        'target': serializer.data.get('target'),
                        'type': serializer.data.get('type'),
                        'source_delay': delay}
                return Response(data, status=status.HTTP_201_CREATED)
        else:
            return Response({'detail': 'Error, please try again.'},
                            status=status.HTTP_400_BAD_REQUEST)


    def _source_target(self, source, target):
        task_dependancies = TaskDependencyMap.objects.filter(target=source)
        if task_dependancies:
            for task_dependancy in task_dependancies:
                if task_dependancy.source.id == target:
                    return True
                return self._source_target(task_dependancy.source.id,target)
        else:
            return False


    def destroy(self, request, *args, **kwargs):
        id = kwargs.get('pk')
        headers = {"Authorization": request.headers.get('Authorization')}
        task_dependancy = get_object_or_404(TaskDependencyMap, id=id)
        project_id = task_dependancy.target.board_stage.board.project_id
        response_data = get_project_details(project_id, headers)
        task_name = response_data.get('name') + "_" + str(response_data.get('id'))
        project_task = Task.objects.filter(title=response_data.get('name'), task_type=task_name).first()
        task_ids = [project_task.id]
        max_end_date = task_dependancy.target.board_stage.tasks.all().exclude(id__in=task_ids).aggregate(
            Max('end_date')).get('end_date__max')
        if task_dependancy.source.is_critical_path_task:
            if task_dependancy.target.parent_task_id and task_dependancy.target.parent_task_id != project_task.id and task_dependancy.target.parent_task_id.is_critical_path_task:
                if not task_dependancy.target.is_critical_path_task:
                    pass
                else:
                    if task_dependancy.target.end_date == max_end_date and task_dependancy.target.display_in_gantt_chart:
                        task_dependancy.target.is_critical_path_task = True
                        task_dependancy.target.save()
                        update_child_tasks_true(task_dependancy.target, headers)
                        prdecessor_cretical_task_true(task_dependancy.target, headers)
                    else:
                        task_dependancy.target.is_critical_path_task = False
                        task_dependancy.target.save()
                        update_child_tasks_false(task_dependancy.target, headers)
                        prdecessor_cretical_task(task_dependancy.target, headers)
                    if task_dependancy.target.procurement_id:
                        try:
                            update_product_from_board_gant_chart(task_dependancy.target, headers)
                        except Exception as e:
                            pass
            else:
                if not task_dependancy.target.is_critical_path_task:
                    pass
                else:
                    if task_dependancy.target.end_date == max_end_date and task_dependancy.target.display_in_gantt_chart:
                        task_dependancy.target.is_critical_path_task = True
                        task_dependancy.target.save()
                        update_child_tasks_true(task_dependancy.target, headers)
                        prdecessor_cretical_task_true(task_dependancy.target, headers)
                    else:
                        task_dependancy.target.is_critical_path_task = False
                        task_dependancy.target.save()
                        update_child_tasks_false(task_dependancy.target, headers)
                        prdecessor_cretical_task(task_dependancy.target, headers)
                    if task_dependancy.target.procurement_id:
                        try:
                            update_product_from_board_gant_chart(task_dependancy.target, headers)
                        except Exception as e:
                            pass
        return super(TaskDependancyViewSet, self).destroy(request, *args, **kwargs)

    @action(methods=["POST"], detail=False, url_path='ganttchart-task-predecessor')
    def ganttchart_task_predecessor(self, request):
        source_task_list = []
        headers = {"Authorization": request.headers.get('Authorization')}
        source = Task.objects.get(id=request.data.get('source'))
        target = Task.objects.get(id=request.data.get('target'))
        source_tasks = self._source_target(int(request.data.get('source')),
                                           int(request.data.get('target')))
        task_dependancy = TaskDependencyMap.objects.filter(source=request.data.get('source'),
                                                           target=request.data.get('target'),
                                                           type=request.data.get('type'))
        if task_dependancy or source_tasks:
            return Response({"detail": "Same type predecessor is available, please try again with different"},
                            status=status.HTTP_400_BAD_REQUEST)
        else:
            if source and target:
                serializer = TaskDependencyMapSerializer(data=request.data)
                if not serializer.is_valid():
                    return Response({'detail': 'Error, please try again.'},
                                    status=status.HTTP_400_BAD_REQUEST)
                serializer.save()
                task_dependancy = TaskDependencyMap.objects.get(id=serializer.data.get('id'))
                delay = 0
                if task_dependancy.source:
                    delay = task_dependancy.source.delay
                is_critical_path_delay_task_dependancy(task_dependancy, delay, headers)
                return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _update_task_end_date_and_delay(self, delay, task):
        """
        Save delay and end date.
        """
        task = Task.objects.get(id=task)
        task.end_date = task.end_date + timedelta(delay)
        if not task.due_date:
            task.due_date = date.today()
        if task.end_date > task.due_date:
            task.delay = (task.end_date - task.due_date).days
        elif task.end_date <= task.due_date:
            task.delay = 0
        task.save()
        return task.delay


class GanttChartLableViewSet(ModelViewSet):
    queryset = GanttChartLable.objects.all()
    serializer_class = GanttChartLableSerializer
    filter_backends = (DjangoFilterBackend,)

    def get_permissions(self):
        action_permission_map = {
            'list': 'can_view_ganttchart',
            'retrieve': 'can_view_ganttchart',
            'destroy': 'can_delete_ganttchart',
            'create': 'can_add_ganttchart',
            'update': 'can_edit_ganttchart',
            'partial_update': 'can_edit_ganttchart',
            'move_ganttchart_label': 'can_edit_ganttchart'
        }
        return (IsSuperUserOrProjectGanttLabelPermission(action_permission_map[self.action]),)

    def create(self, request, *args, **kwargs):

        gantt_positions = []
        label_data = {}
        label_data['board'] = request.data.get('board')
        if all([request.data.get('board'), request.data.get('parent_label_id')]):
            label_data['parent_label_id'] = request.data.get('parent_label_id')
            parent_label = get_object_or_404(GanttChartLable, pk=int(request.data.get('parent_label_id')))
            label_position = parent_label.sub_labels.aggregate(Max('position')).get('position__max')
            if label_position:
                gantt_positions.append(label_position)
            task_position = parent_label.taskss.aggregate(Max('gantt_chart_position')).get('gantt_chart_position__max')
            if task_position:
                gantt_positions.append(task_position)
        if all([request.data.get('board'), request.data.get('tasks')]):
            """create task level label"""
            label_data['tasks'] = request.data.get('tasks')
            task = get_object_or_404(Task, pk=int(request.data.get('tasks')))
            task_position = task.sub_tasks.aggregate(Max('gantt_chart_position')).get(
                'gantt_chart_position__max')
            label_position = task.gantt_chart_labels.aggregate(Max('position')).get('position__max')
            if task_position:
                gantt_positions.append(task_position)
            if label_position:
                gantt_positions.append(label_position)
        label_data['start_date'] = date.today()
        label_data['end_date'] = date.today()
        label_data['position'] = max(gantt_positions) + 1 if gantt_positions else 1
        label_data['name'] = request.data.get('name')
        serializer = GanttChartLableSerializer(data=label_data)
        if serializer.is_valid():
            serializer.save()
            start_date = datetime.strptime(serializer.data.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(serializer.data.get('end_date'), '%Y-%m-%d').date()
            response_data = {
                "text": serializer.data.get('name'),
                "duration": (end_date - start_date).days,
                "end_date": end_date,
                "start_date": start_date,
                "position": serializer.data.get('position'),
                "progress": serializer.data.get('progress'),
                "parent": 0,
                "board": serializer.data.get('board'),
                "id": serializer.data.get('id')
            }
            if serializer.data.get('tasks'):
                response_data['parent'] = "task-" + str(serializer.data.get('tasks'))
            elif serializer.data.get('parent_label_id'):
                response_data['parent'] = "label-" + str(serializer.data.get('parent_label_id'))
            elif serializer.data.get('stages'):
                response_data['parent'] = "stage-" + str(serializer.data.get('stages'))
            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response({'detail': 'Error, please try again.'}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        label_to_remove = self.get_object()
        serializer = GanttChartLableSerializer(label_to_remove)
        for task in label_to_remove.taskss.all():
            remove_gantchart_task(task)
        for label in label_to_remove.sub_labels.all():
            remve_labels(label)
        if serializer.data.get('tasks'):
            parent_task = get_object_or_404(Task, id=serializer.data.get('tasks'))
            response = super(GanttChartLableViewSet, self).destroy(request, *args, **kwargs)
            if response.status_code == 204:
                if parent_task:
                    labels = parent_task.gantt_chart_labels.all().exclude(id=label_to_remove.id)
                    if labels:
                        self._from_label_move(label_to_remove, labels)
                    tasks = parent_task.sub_tasks.filter(display_in_gantt_chart=True)
                    if tasks:
                        self._from_task_move(label_to_remove, tasks)
            return Response(response.data, status=status.HTTP_204_NO_CONTENT)
        elif serializer.data.get('parent_label_id'):
            parent_label = get_object_or_404(GanttChartLable, id=serializer.data.get('parent_label_id'))
            """label has stages, tasks,labels"""
            labels = parent_label.sub_labels.all().exclude(id=label_to_remove.id)
            tasks = parent_label.taskss.filter(display_in_gantt_chart=True)
            stages = parent_label.board_stage_map.filter(display_in_gantt_chart=True)
            response = super(GanttChartLableViewSet, self).destroy(request, *args, **kwargs)
            if response.status_code == 204:
                if labels:
                    self._from_label_move(label_to_remove, labels)
                if tasks:
                    self._from_task_move(label_to_remove, tasks)
                if stages:
                    self._from_stage_move(label_to_remove, stages)
            return Response(response.data, status=status.HTTP_204_NO_CONTENT)
        else:
            project_id = label_to_remove.board.project_id
            boards = Board.objects.filter(project_id=project_id)
            response = super(GanttChartLableViewSet, self).destroy(request, *args, **kwargs)
            if response.status_code == 204:
                for board in boards:
                    labels = GanttChartLable.objects.filter(board=board,
                                                            stages__isnull=True,
                                                            tasks__isnull=True,
                                                            parent_label_id__isnull=True).exclude(id=label_to_remove.id)
                    stages = BoardStageMap.objects.filter(board=board,
                                                          display_in_gantt_chart=True,
                                                          board_stage_label__isnull=True)
                    if labels:
                        self._from_label_move(label_to_remove, labels)
                    if stages:
                        self._from_stage_move(label_to_remove, stages)
                return Response(response.data, status=status.HTTP_204_NO_CONTENT)
            return Response(response.data, status=status.HTTP_204_NO_CONTENT)

    @action(methods=["POST"], detail=True, url_path='move-ganttchart-label')
    def move_ganttchart_label(self, request, pk=None):
        label_to_move = self.get_object()
        serializer = MoveGanttChartLabelSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'detail': 'Error, please try again'}, status=status.HTTP_400_BAD_REQUEST)
        new_position = serializer.data.get('position')
        if serializer.data.get('parent_label_id'):
            label_requested = get_object_or_404(GanttChartLable, id=serializer.data['parent_label_id'])
            if label_to_move.parent_label_id:
                if label_to_move.parent_label_id_id == int(serializer.data['parent_label_id']):
                    """within same label, label as parent"""
                    old_position = label_to_move.position
                    labels = label_to_move.parent_label_id.sub_labels.all().exclude(id=label_to_move.id)
                    if labels:
                        self._move_labels(new_position, old_position, labels)
                    tasks = label_to_move.parent_label_id.taskss.filter(display_in_gantt_chart=True)
                    if tasks:
                        self._move_task(new_position, old_position, tasks)
                    stages = label_to_move.parent_label_id.board_stage_map.filter(display_in_gantt_chart=True)
                    if stages:
                        self._move_stages(new_position, old_position, stages)
                else:
                    """within different label, label as parent"""
                    """from label"""
                    labels = label_to_move.parent_label_id.sub_labels.all().exclude(id=label_to_move.id)
                    if labels:
                        self._from_label_move(label_to_move, labels)
                    tasks = label_to_move.parent_label_id.taskss.filter(display_in_gantt_chart=True)
                    if tasks:
                        self._from_task_move(label_to_move, tasks)
                    stages = label_to_move.parent_label_id.board_stage_map.filter(display_in_gantt_chart=True)
                    if stages:
                        self._from_stage_move(label_to_move, stages)
                    """to label"""
                    labels = label_requested.sub_labels.all()
                    if labels:
                        self._to_label_move(new_position, labels)
                    tasks = label_requested.taskss.filter(display_in_gantt_chart=True)
                    if tasks:
                        self._to_task_move(new_position, tasks)
                    stages = label_requested.board_stage_map.filter(display_in_gantt_chart=True)
                    if stages:
                        self._to_stage_move(new_position, stages)
                label_to_move.position = new_position
                label_to_move.parent_label_id = label_requested
                label_to_move.save()
                return Response({}, status=status.HTTP_200_OK)
            else:
                """within differnt label that does have stage or task as parent"""
                if label_to_move.tasks and not label_to_move.stages:
                    if label_to_move.tasks.sub_tasks:
                        tasks = label_to_move.tasks.sub_tasks.all()
                        if tasks:
                            self._from_task_move(label_to_move, tasks)
                    if label_to_move.tasks.gantt_chart_labels:
                        labels = label_to_move.tasks.gantt_chart_labels.all()
                        if labels:
                            self._from_label_move(label_to_move, labels)
                if label_to_move.stages and not label_to_move.tasks:
                    if label_to_move.stages.tasks:
                        tasks = label_to_move.stages.tasks.filter(display_in_gantt_chart=True)
                        if tasks:
                            self._from_task_move(label_to_move, tasks)
                    if label_to_move.stages.gantt_chart_labels:
                        labels = label_to_move.stages.gantt_chart_labels.all()
                        if labels:
                            self._from_label_move(label_to_move, labels)
                """to different label from task, stage"""
                if label_requested.sub_labels:
                    labels = label_requested.sub_labels.all()
                    if labels:
                        self._to_label_move(new_position, labels)
                if label_requested.taskss:
                    tasks = label_requested.taskss.filter(display_in_gantt_chart=True)
                    if tasks:
                        self._to_task_move(new_position, tasks)
                if label_requested.board_stage_map:
                    stages = label_requested.board_stage_map.filter(display_in_gantt_chart=True)
                    if stages:
                        self._to_stage_move(new_position, stages)
            if label_to_move.stages:
                label_to_move.stages = None
            if label_to_move.tasks:
                label_to_move.tasks = None
            label_to_move.position = new_position
            label_to_move.parent_label_id = label_requested
            label_to_move.save()
            return Response({}, status=status.HTTP_200_OK)
        if serializer.data.get('tasks_id'):
            task_requested = get_object_or_404(Task, id=serializer.data['tasks_id'])
            old_position = label_to_move.position
            if label_to_move.tasks:
                if label_to_move.tasks.id == int(serializer.data['tasks_id']):
                    """within same task"""
                    if task_requested.sub_tasks:
                        tasks = task_requested.sub_tasks.filter(display_in_gantt_chart=True)
                        if tasks:
                            self._move_task(new_position, old_position, tasks)
                    if task_requested.gantt_chart_labels:
                        labels = task_requested.gantt_chart_labels.all().exclude(id=label_to_move.id)
                        if labels:
                            self._move_labels(new_position, old_position, labels)
                else:
                    """within different tasks"""
                    """from task"""
                    if label_to_move.tasks.sub_tasks:
                        tasks = label_to_move.tasks.sub_tasks.filter(display_in_gantt_chart=True)
                        if tasks:
                            self._from_task_move(label_to_move, tasks)
                    if label_to_move.tasks.gantt_chart_labels:
                        labels = label_to_move.tasks.gantt_chart_labels.all().exclude(id=label_to_move.id)
                        if labels:
                            self._from_label_move(label_to_move, labels)
                    """to task"""
                    if task_requested.sub_tasks:
                        tasks = task_requested.sub_tasks.filter(display_in_gantt_chart=True)
                        if tasks:
                            self._to_task_move(new_position, tasks)
                    if task_requested.gantt_chart_labels:
                        labels = task_requested.gantt_chart_labels.all()
                        if labels:
                            self._to_label_move(new_position, labels)
                label_to_move.tasks = task_requested
                label_to_move.position = new_position
                label_to_move.save()
                return Response({}, status=status.HTTP_200_OK)
            else:
                """within different tasks"""
                """from label, stage"""
                if label_to_move.parent_label_id:
                    parent_label = label_to_move.parent_label_id
                    if parent_label.sub_labels:
                        labels = label_to_move.parent_label_id.sub_labels.all()
                        if labels:
                            self._from_label_move(label_to_move, labels)
                    if parent_label.board_stage_map:
                        stages = label_to_move.board_stage_map.filter(display_in_gantt_chart=True)
                        if stages:
                            self._from_stage_move(label_to_move, stages)
                    if parent_label.taskss:
                        tasks = label_to_move.taskss.filter(display_in_gantt_chart=True)
                        if tasks:
                            self._from_task_move(label_to_move, tasks)
                if label_to_move.stages:
                    parent_stage = label_to_move.stages
                    if parent_stage.tasks:
                        tasks = parent_stage.tasks.filter(display_in_gantt_chart=True)
                        if tasks:
                            self._from_task_move(label_to_move, tasks)
                    if parent_stage.gantt_chart_labels:
                        labels = parent_stage.gantt_chart_labels.all()
                        if labels:
                            self._from_label_move(label_to_move, labels)
                """to task"""
                if task_requested.sub_tasks:
                    tasks = task_requested.sub_tasks.filter(display_in_gantt_chart=True)
                    if tasks:
                        self._to_task_move(new_position, tasks)
                if task_requested.gantt_chart_labels:
                    labels = task_requested.gantt_chart_labels.all()
                    if labels:
                        self._to_label_move(new_position, labels)
            if label_to_move.stages:
                label_to_move.stages = None
            if label_to_move.parent_label_id:
                label_to_move.parent_label_id = None
            label_to_move.tasks = task_requested
            label_to_move.position = new_position
            label_to_move.save()
            return Response({}, status=status.HTTP_200_OK)
        else:
            """move board level label."""
            old_position = label_to_move.position
            boards = Board.objects.filter(project_id=label_to_move.board.project_id)
            stages = [stage for board in boards for stage in board.board_stage_maps.all() if stage]
            labels = [label for board in boards for label in board.gantt_chart_labels.filter \
                (stages__isnull=True, tasks__isnull=True) if label.id != label_to_move.id]
            for stage in stages:
                tasks = stage.tasks.filter(parent_task_id__isnull=True, task_labels__isnull=True)
                self._to_task_move(new_position, tasks)
            if labels:
                self._move_labels(new_position, old_position, labels)
            label_to_move.position = new_position
            if label_to_move.tasks:
                label_to_move.tasks = None
            if label_to_move.stages:
                label_to_move.stages = None
            if label_to_move.parent_label_id:
                label_to_move.parent_label_id = None
            label_to_move.save()
            return Response({}, status=status.HTTP_200_OK)

    def _to_task_move(self, new_position, tasks):
        for task in tasks:
            if task.gantt_chart_position >= int(new_position):
                task.gantt_chart_position = task.gantt_chart_position + 1
                task.save()

    def _to_stage_move(self, new_position, stages):
        for stage in stages:
            if stage.gantt_chart_position >= int(new_position):
                stage.gantt_chart_position = stage.gantt_chart_position + 1
                stage.save()

    def _to_label_move(self, new_position, labels):
        for label in labels:
            if label.position >= int(new_position):
                label.position = label.position + 1
                label.save()

    def _from_task_move(self, label_to_move, tasks):
        for task in tasks:
            if task.gantt_chart_position >= label_to_move.position:
                task.gantt_chart_position = task.gantt_chart_position - 1
                task.save()

    def _from_label_move(self, label_to_move, labels):
        for label in labels:
            if label.position >= label_to_move.position:
                label.position = label.position - 1
                label.save()

    def _from_stage_move(self, label_to_move, stages):
        for stage in stages:
            if stage.gantt_chart_position >= label_to_move.position:
                stage.gantt_chart_position = stage.gantt_chart_position - 1
                stage.save()

    def _move_task(self, new_position, old_position, tasks):
        for task in tasks:
            position = int(task.gantt_chart_position)
            if old_position > position >= new_position:
                task.gantt_chart_position = position + 1
                task.save()
            if old_position < position <= new_position:
                task.gantt_chart_position = position - 1
                task.save()

    def _move_stages(self, new_position, old_position, stages):
        for stage in stages:
            position = int(stage.gantt_chart_position)
            if old_position > position >= new_position:
                stage.gantt_chart_position = stage.gantt_chart_position + 1
                stage.save()
            if old_position < position <= new_position:
                stage.gantt_chart_position = stage.gantt_chart_position - 1
                stage.save()

    def _move_labels(self, new_position, old_position, labels):
        for label in labels:
            position = int(label.position)
            if old_position > position >= new_position:
                label.position = label.position + 1
                label.save()
            if old_position < position <= new_position:
                label.position = label.position - 1
                label.save()
