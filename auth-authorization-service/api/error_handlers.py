from django.http import HttpResponse

from rest_framework import status


def server_error(request):
    response = HttpResponse('{"message":"The server encountered an internal '
                            'error and was unable to complete your request"}', content_type="application/json",
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return response


def page_not_found(request, exception):
    response = HttpResponse('{"message":"The page you are looking for was not found"}', content_type="application/json",
                            status=status.HTTP_404_NOT_FOUND)
    return response
