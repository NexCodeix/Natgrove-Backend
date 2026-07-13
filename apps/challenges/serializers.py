from django.db.models import Avg
from rest_framework import serializers

from apps.accounts.models import Community, CommunityScope

from .models import (
    ActionCatalogItem,
    ActionLog,
    ActionStatus,
    Challenge,
    ChallengeFormat,
    ChallengeParticipation,
    ChallengePrize,
    CompanyActionSetting,
)


class ActionCatalogItemSerializer(serializers.ModelSerializer):
    is_enabled = serializers.SerializerMethodField()
    times_completed = serializers.SerializerMethodField()
    avg_co2_saved_kg = serializers.SerializerMethodField()
    challenges_count = serializers.SerializerMethodField()

    class Meta:
        model = ActionCatalogItem
        fields = [
            'id', 'name', 'description', 'icon', 'category', 'default_points', 'co2_impact_kg',
            'water_saved_liters', 'waste_recycled_kg', 'is_active',
            'is_enabled', 'times_completed', 'avg_co2_saved_kg', 'challenges_count',
        ]
        read_only_fields = ['id']

    def _company(self):
        request = self.context.get('request')
        if request and getattr(request, 'user', None) and request.user.is_authenticated:
            return request.user.company
        return None

    def get_is_enabled(self, obj):
        company = self._company()
        if not company:
            return obj.is_active
        setting = next((s for s in obj.company_settings.all() if s.company_id == company.id), None)
        return setting.is_enabled if setting else True

    def get_times_completed(self, obj):
        company = self._company()
        qs = obj.logs.filter(status=ActionStatus.APPROVED)
        if company:
            qs = qs.filter(participation__challenge__company=company)
        return qs.count()

    def get_avg_co2_saved_kg(self, obj):
        company = self._company()
        qs = obj.logs.filter(status=ActionStatus.APPROVED)
        if company:
            qs = qs.filter(participation__challenge__company=company)
        avg = qs.aggregate(avg=Avg('co2_impact_kg'))['avg']
        return avg if avg is not None else obj.co2_impact_kg

    def get_challenges_count(self, obj):
        company = self._company()
        qs = obj.challenges.all()
        if company:
            qs = qs.filter(company=company)
        return qs.count()


class CompanyActionToggleSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField()


class ChallengePrizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChallengePrize
        fields = ['id', 'rank', 'title', 'description', 'image']
        read_only_fields = ['id']


class ChallengeSerializer(serializers.ModelSerializer):
    actions = serializers.PrimaryKeyRelatedField(
        many=True, queryset=ActionCatalogItem.objects.filter(is_active=True), required=False
    )
    communities = serializers.PrimaryKeyRelatedField(many=True, queryset=Community.objects.all(), required=False)
    prizes = ChallengePrizeSerializer(many=True, required=False)
    goal_progress = serializers.ReadOnlyField()
    participant_count = serializers.ReadOnlyField()
    estimated_audience_count = serializers.ReadOnlyField()
    estimated_co2_impact_kg = serializers.ReadOnlyField()
    actual_co2_saved_kg = serializers.ReadOnlyField()

    class Meta:
        model = Challenge
        fields = [
            'id', 'company', 'created_by', 'title', 'description', 'how_to_play', 'rules', 'image',
            'challenge_type', 'actions', 'communities', 'challenge_format', 'goal_metric', 'goal_title',
            'goal_count', 'start_date', 'end_date', 'status', 'is_archived', 'prize_type', 'prizes',
            'goal_progress', 'participant_count', 'estimated_audience_count', 'estimated_co2_impact_kg',
            'actual_co2_saved_kg', 'created_at',
        ]
        read_only_fields = ['id', 'company', 'created_by', 'created_at']

    def validate(self, attrs):
        challenge_format = attrs.get('challenge_format', getattr(self.instance, 'challenge_format', None))
        goal_count = attrs.get('goal_count', getattr(self.instance, 'goal_count', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if challenge_format == ChallengeFormat.GOAL and not goal_count:
            raise serializers.ValidationError({'goal_count': 'Required when challenge_format is GOAL.'})
        if challenge_format == ChallengeFormat.TIMELINE and not end_date:
            raise serializers.ValidationError({'end_date': 'Required when challenge_format is TIMELINE.'})
        return attrs

    def validate_communities(self, communities):
        request = self.context['request']
        for community in communities:
            if community.company_id != request.user.company_id:
                raise serializers.ValidationError('All communities must belong to your own company.')
        return communities

    def validate_actions(self, actions):
        request = self.context['request']
        disabled_names = CompanyActionSetting.objects.filter(
            company_id=request.user.company_id, action_catalog_item__in=actions, is_enabled=False,
        ).values_list('action_catalog_item__name', flat=True)
        if disabled_names:
            raise serializers.ValidationError(
                f'These actions have been disabled for your company: {", ".join(disabled_names)}.'
            )
        return actions

    def create(self, validated_data):
        prizes_data = validated_data.pop('prizes', [])
        actions = validated_data.pop('actions', [])
        communities = validated_data.pop('communities', [])

        challenge = Challenge.objects.create(**validated_data)

        if actions:
            challenge.actions.set(actions)
        if communities:
            challenge.communities.set(communities)
        else:
            company_community = Community.objects.filter(
                company=challenge.company, scope=CommunityScope.COMPANY
            ).first()
            if company_community:
                challenge.communities.set([company_community])
        for prize in prizes_data:
            ChallengePrize.objects.create(challenge=challenge, **prize)
        return challenge

    def update(self, instance, validated_data):
        prizes_data = validated_data.pop('prizes', None)
        actions = validated_data.pop('actions', None)
        communities = validated_data.pop('communities', None)

        instance = super().update(instance, validated_data)

        if actions is not None:
            instance.actions.set(actions)
        if communities is not None:
            instance.communities.set(communities)
        if prizes_data is not None:
            instance.prizes.all().delete()
            for prize in prizes_data:
                ChallengePrize.objects.create(challenge=instance, **prize)
        return instance


class ActionLogSerializer(serializers.ModelSerializer):
    action_name = serializers.CharField(source='action_catalog_item.name', read_only=True)

    class Meta:
        model = ActionLog
        fields = [
            'id', 'participation', 'action_catalog_item', 'action_name', 'points_awarded', 'co2_impact_kg',
            'water_saved_liters', 'waste_recycled_kg', 'proof_image', 'caption', 'status', 'submitted_at',
            'reviewed_by', 'reviewed_at', 'review_note',
        ]
        read_only_fields = [
            'id', 'participation', 'points_awarded', 'co2_impact_kg', 'water_saved_liters', 'waste_recycled_kg',
            'status', 'submitted_at', 'reviewed_by', 'reviewed_at',
        ]


class LogActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActionLog
        fields = ['id', 'action_catalog_item', 'proof_image', 'caption']
        read_only_fields = ['id']


class ChallengeParticipationSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    challenge_title = serializers.CharField(source='challenge.title', read_only=True)
    points_earned = serializers.ReadOnlyField()
    actions_completed_count = serializers.ReadOnlyField()
    submissions = ActionLogSerializer(many=True, read_only=True)

    class Meta:
        model = ChallengeParticipation
        fields = [
            'id', 'user', 'user_email', 'challenge', 'challenge_title', 'status', 'joined_at',
            'points_earned', 'actions_completed_count', 'submissions',
        ]
        read_only_fields = fields


class SubmissionReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['APPROVED', 'REJECTED'])
    review_note = serializers.CharField(required=False, allow_blank=True, default='')
