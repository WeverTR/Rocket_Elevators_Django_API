from rest_framework import serializers
from .models import Employees

class EmployeesSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Employees
        fields = (
            'id',
            'last_name',
            'first_name',
            'title',
            'email',
            'created_at',
            'updated_at',
            'facial_keypoints'
        )