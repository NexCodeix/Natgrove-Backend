from rest_framework import serializers

from .models import Action, Challenge, ChallengeParticipation


class ChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = [
            'id', 'company', 'department', 'created_by', 'title', 'description',
            'challenge_type', 'difficulty', 'point_reward', 'start_date', 'end_date',
            'status', 'created_at',
        ]
        read_only_fields = ['id', 'company', 'created_by', 'created_at']

    def validate_department(self, department):
        request = self.context['request']
        if department and department.company_id != request.user.company_id:
            raise serializers.ValidationError('Department must belong to your own company.')
        return department


class ActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Action
        fields = [
            'id', 'participation', 'action_type', 'proof_image', 'caption',
            'status', 'submitted_at', 'reviewed_by', 'reviewed_at', 'review_note',
        ]
        read_only_fields = ['id', 'participation', 'action_type', 'status', 'submitted_at', 'reviewed_by', 'reviewed_at']


class SubmitProofSerializer(serializers.ModelSerializer):
    class Meta:
        model = Action
        fields = ['id', 'proof_image', 'caption']
        read_only_fields = ['id']


class ChallengeParticipationSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    challenge_title = serializers.CharField(source='challenge.title', read_only=True)
    submissions = ActionSerializer(many=True, read_only=True)

    class Meta:
        model = ChallengeParticipation
        fields = [
            'id', 'user', 'user_email', 'challenge', 'challenge_title',
            'status', 'joined_at', 'completed_at', 'submissions',
        ]
        read_only_fields = fields


class SubmissionReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['APPROVED', 'REJECTED'])
    review_note = serializers.CharField(required=False, allow_blank=True, default='')
