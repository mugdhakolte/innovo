import os
import random

from google.cloud import storage

from django.conf import settings


def get_dynamic_path(folder_name, file_name):
    base_name, file_extension = os.path.splitext(file_name)
    characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890'
    random_string = ''.join((random.choice(characters)) for x in range(30))
    return '{folder_name}/{randomstring}{ext}'.format(ext=file_extension,
                                                      folder_name=folder_name,
                                                      randomstring=random_string)


def get_images_dynamic_path(instance, file_name):
    return get_dynamic_path('images', file_name)


def get_attachments_dynamic_path(instance, file_name):
    return get_dynamic_path('attachments', file_name)


def delete_blob(blob_name):
    bucket_name = settings.GS_BUCKET_NAME
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.delete()

