import json
import requests
from django.conf import settings
from api.models import Activity

def log_activity(task, description, created_by, activity_type, parent_activity=None):
    created_by = str(created_by) # new activity type, and created by name
    created_by_name = requests.get(settings.AUTH_MICRO_SERVICE_URL + "/" + created_by + "/").json()['full_name']
    if parent_activity:
        Activity.objects.create(task=task,
                                activity=description,
                                created_by=created_by,
                                activity_type=activity_type,
                                created_by_name=created_by_name,
                                parent_activity=parent_activity)
    else:
        Activity.objects.create(task=task,
                                activity=description,
                                created_by=created_by,
                                activity_type=activity_type,
                                created_by_name=created_by_name)

