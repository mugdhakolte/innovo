from rest_framework.routers import DefaultRouter

from api.viewsets import *


ROUTER = DefaultRouter()

handler404 = 'api.error_handlers.page_not_found'

handler500 = 'api.error_handlers.server_error'

ROUTER.register('categories', CategoryViewSet, base_name='categories')

ROUTER.register('boards', BoardViewSet, base_name='boards')

ROUTER.register('board-labels', LabelViewSet, base_name='labels')

ROUTER.register('board-stages', BoardStageViewSet, base_name='board_stages')

ROUTER.register('board-members', BoardMemberViewSet, base_name='board_members')

ROUTER.register('tasks', TaskViewSet, base_name='tasks')

ROUTER.register('task-members', TaskMemberViewSet, base_name='task_members')

ROUTER.register('task-attachments', AttachmentViewSet, base_name='attachments')

ROUTER.register('task-checklists', ChecklistViewSet, base_name='checklists')

ROUTER.register('check-list-items', ChecklistItemViewSet, base_name='check_list_items')

ROUTER.register('task-activities', ActivityViewSet, base_name='activities')

ROUTER.register('task-dependancies', TaskDependancyViewSet, base_name='task_dependancies')

ROUTER.register('gantt-labels', GanttChartLableViewSet, base_name='gantt-labels')


urlpatterns = ROUTER.urls


