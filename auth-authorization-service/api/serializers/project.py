"""For project related serializers."""
import requests
import collections

from django.conf import settings
from django.utils.crypto import get_random_string
from django.core.exceptions import ValidationError

from rest_framework import serializers

from api.models import *
from api.serializers.user import *


class ProjectTypeSerializer(serializers.ModelSerializer):
    """Serializer class for Project types APIs."""

    created_by_user_name = serializers.SerializerMethodField()

    def get_created_by_user_name(self, instance):
        return instance.created_by.full_name

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super(ProjectTypeSerializer, self).create(validated_data)

    class Meta:
        """Meta class for Project Type."""

        model = ProjectType
        fields = '__all__'


class CountrySerializer(serializers.ModelSerializer):

    class Meta:
        model = Country
        fields = '__all__'


class CitySerializer(serializers.ModelSerializer):

    class Meta:
        model = City
        fields = '__all__'


class StateSerializer(serializers.ModelSerializer):
    cities = CitySerializer(many=True, read_only=True)

    class Meta:
        model = State
        fields = '__all__'


class ProjectDetailSerializer(serializers.ModelSerializer):

    class Meta:
        model = Project
        fields = '__all__'


class ProjectSerializer(serializers.ModelSerializer):
    """Serializer class for Project types APIs."""
    weather_forecast = serializers.SerializerMethodField()

    def validate(self, data):
        if data.get('estimated_completion_date') and data.get('start_date'):
            if data['estimated_completion_date'] <= data['start_date']:
                raise ValidationError('Estimated Completion date must be grater than start date')
        return data

    class Meta:
        """Meta class for Project Type."""

        model = Project
        fields = "__all__"

    def get_weather_forecast(self, instance):
        weather_data_response = {}
        weather_main_data = []
        try:
            city_name = instance.city.name.capitalize()
        except Exception as e:
            return weather_data_response
        url = "{0}?q={1}&appid={2}".format(settings.WEATHER_APP_URL, city_name, settings.WEATHER_APP_ID)
        weather_data_re = requests.get(url).json()
        if weather_data_re['message'] == "city not found" or weather_data_re['cod'] == 404:
            return weather_main_data
        else:
            weather_data_list = weather_data_re.get('list')
            list_unique_date = []
            for weather_data in weather_data_list:
                if weather_data['dt_txt'].split()[0] not in list_unique_date:
                    weather_data_response['date'] = weather_data['dt_txt'].split()[0]
                    weather_data_response['temp_min'] = round((weather_data['main']['temp_min']-273.15)*9/5+32, 2)
                    weather_data_response['temp_max'] = round((weather_data['main']['temp_max']-273.15)*9/5+32, 2)
                    weather_data_response['humidity'] = weather_data['main']['humidity']
                    weather_data_response['icon'] = weather_data['weather'][0]['icon']
                    weather_data_response['description'] = weather_data['weather'][0]['description']
                    weather_main_data.append(weather_data_response.copy())
                    list_unique_date.append(weather_data_response['date'])
            return weather_main_data


class ProjectMemberSerializer(serializers.ModelSerializer):
    """Serializer for project member APIs."""

    permissions = serializers.SlugRelatedField(queryset=Permission.objects.all(), slug_field='code', many=True)
    is_admin = serializers.BooleanField(default=False)

    class Meta:
        """Meta class for project member."""

        fields = "__all__"
        model = ProjectMember


class GetProjectMemberSerializer(serializers.ModelSerializer):
    """Serializer for project member APIs."""

    user = UserSerializer()
    project = ProjectSerializer()
    permissions = serializers.SlugRelatedField(queryset=Permission.objects.all(), slug_field='code', many=True)

    class Meta:
        """Meta class for project member."""

        fields = "__all__"
        model = ProjectMember


class PageSerializer(serializers.ModelSerializer):
    class Meta:
        """Meta class for project member."""

        fields = "__all__"
        model = Page


class SendEmailSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=148, required=True)
    description = serializers.CharField(max_length=248, required=True)
    file = serializers.FileField(required=False)

