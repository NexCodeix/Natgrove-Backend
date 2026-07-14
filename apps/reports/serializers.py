from django.db.models import Sum
from rest_framework import serializers

from apps.accounts.models import User
from apps.challenges.models import ActionLog, ActionStatus


class ActionsLogEntrySerializer(serializers.ModelSerializer):
    action_name = serializers.CharField(source='action_catalog_item.name', read_only=True)
    completed_by = serializers.CharField(source='participation.user.full_name', read_only=True)

    class Meta:
        model = ActionLog
        fields = ['id', 'action_name', 'completed_by', 'submitted_at', 'co2_impact_kg', 'points_awarded']
        read_only_fields = fields


class MemberSerializer(serializers.ModelSerializer):
    department_name = serializers.SerializerMethodField()
    actions_completed_count = serializers.SerializerMethodField()
    points_earned = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'role', 'department_name',
            'actions_completed_count', 'points_earned', 'created_at',
        ]
        read_only_fields = fields

    def get_department_name(self, obj):
        return obj.department.name if obj.department_id else None

    def _approved_logs(self, obj):
        return ActionLog.objects.filter(participation__user=obj, status=ActionStatus.APPROVED)

    def get_actions_completed_count(self, obj):
        return self._approved_logs(obj).count()

    def get_points_earned(self, obj):
        return self._approved_logs(obj).aggregate(total=Sum('points_awarded'))['total'] or 0
