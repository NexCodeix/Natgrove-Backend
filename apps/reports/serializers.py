from rest_framework import serializers

from apps.challenges.models import ActionLog


class ActionsLogEntrySerializer(serializers.ModelSerializer):
    action_name = serializers.CharField(source='action_catalog_item.name', read_only=True)
    completed_by = serializers.CharField(source='participation.user.full_name', read_only=True)

    class Meta:
        model = ActionLog
        fields = ['id', 'action_name', 'completed_by', 'submitted_at', 'co2_impact_kg', 'points_awarded']
        read_only_fields = fields
