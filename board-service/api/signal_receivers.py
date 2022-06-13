from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_save

from api.models import *
from api.inter_service_communicator import NotificationService


@receiver(post_save, sender=Board)
def create_board_stage(sender, instance, created, **kwargs):
    if created:
        all_boards = Board.objects.filter(project_id=instance.project_id)
        count = 0
        for board in all_boards:
            if board.board_stage_maps:
                count = count + board.board_stage_maps.all().count()
        stages = Stage.objects.filter(is_default_stage=True)
        for stage in stages:
            BoardStageMap.objects.create(board=instance, stage=stage,
                                         position=stage.default_position, gantt_chart_position=count+1)
            count=count+1
        for label in settings.LABELS:
            Label.objects.create(name=label.get('name'), color_code=label.get('color_code'), board=instance)


# @receiver(post_save, sender=BoardMember)
# def create_board_member_notification(sender, instance, created, **kwargs):
#     if created:
#         NotificationService().send_board_invitation_email(user=instance.user_id,
#                                                           board=instance.board)

#
# @receiver(post_save, sender=TaskMember)
# def create_task_member_notification(sender, instance, created, **kwargs):
#     if created:
#         NotificationService().send_task_invitation_email(user=instance.user_id,
#                                                          task=instance.task)
