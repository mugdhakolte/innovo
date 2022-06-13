from api.models import Stage, Activity


def log_activity(task, description, created_by):
    Activity.objects.create(task=task, content=description, created_by=created_by, is_activity=True)

    
def get_or_create_stage(stage_name):
    try:
        stage = Stage.objects.get(name=stage_name)
    except Stage.DoesNotExist as e:
        stage = Stage.objects.create(name=stage_name)
    return stage
