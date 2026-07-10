from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserRole
from apps.accounts.permissions import IsManagerOrAdmin

from .models import (
    ActionCatalogItem,
    ActionLog,
    ActionStatus,
    Challenge,
    ChallengeFormat,
    ChallengeParticipation,
    ChallengeStatus,
)
from .serializers import (
    ActionCatalogItemSerializer,
    ActionLogSerializer,
    ChallengeParticipationSerializer,
    ChallengeSerializer,
    LogActionSerializer,
    SubmissionReviewSerializer,
)
from .signals import challenge_goal_reached, submission_approved, submission_rejected


class ActionCatalogListView(generics.ListAPIView):
    """Platform-wide library of loggable actions, for the challenge builder to pick from."""

    serializer_class = ActionCatalogItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = ActionCatalogItem.objects.filter(is_active=True)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs


class ChallengeListCreateView(generics.ListCreateAPIView):
    serializer_class = ChallengeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        archived_param = self.request.query_params.get('archived', 'false')
        is_archived = archived_param.lower() in ('true', '1')
        qs = Challenge.objects.filter(company=user.company, is_archived=is_archived)
        if user.role not in (UserRole.COMPANY_ADMIN, UserRole.MANAGER):
            qs = qs.filter(Q(communities__id__in=user.community_ids()) | Q(communities__isnull=True)).distinct()
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), IsManagerOrAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company, created_by=self.request.user)


class ChallengeDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ChallengeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Challenge.objects.filter(company=self.request.user.company)

    def get_permissions(self):
        if self.request.method in ('PATCH', 'PUT', 'DELETE'):
            return [permissions.IsAuthenticated(), IsManagerOrAdmin()]
        return super().get_permissions()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status not in (ChallengeStatus.DRAFT, ChallengeStatus.CANCELLED):
            return Response(
                {'detail': 'Only draft or cancelled challenges can be deleted. Cancel it first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class ChallengeJoinView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        challenge = get_object_or_404(Challenge, pk=pk, company=request.user.company)
        if challenge.status not in (ChallengeStatus.ACTIVE, ChallengeStatus.UPCOMING):
            return Response({'detail': 'This challenge is not open for joining.'}, status=status.HTTP_400_BAD_REQUEST)
        if challenge.communities.exists() and not challenge.communities.filter(
            id__in=request.user.community_ids()
        ).exists():
            return Response(
                {'detail': 'You are not part of a community this challenge is scoped to.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        participation, created = ChallengeParticipation.objects.get_or_create(
            user=request.user, challenge=challenge
        )
        serializer = ChallengeParticipationSerializer(participation)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class LogActionView(APIView):
    """Employee logs proof of having performed one of the challenge's catalog actions."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        challenge = get_object_or_404(Challenge, pk=pk, company=request.user.company)
        participation = get_object_or_404(ChallengeParticipation, user=request.user, challenge=challenge)

        serializer = LogActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action_item = serializer.validated_data['action_catalog_item']

        if not challenge.actions.filter(id=action_item.id).exists():
            return Response(
                {'action_catalog_item': 'This action is not part of this challenge.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action_log = serializer.save(
            participation=participation, points_awarded=action_item.default_points,
            co2_impact_kg=action_item.co2_impact_kg,
        )
        return Response(ActionLogSerializer(action_log).data, status=status.HTTP_201_CREATED)


class ChallengeParticipantsView(generics.ListAPIView):
    serializer_class = ChallengeParticipationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        challenge = get_object_or_404(Challenge, pk=self.kwargs['pk'], company=self.request.user.company)
        return ChallengeParticipation.objects.filter(challenge=challenge)


class ActionLogReviewQueueView(generics.ListAPIView):
    """Manager/admin review queue of logged actions for a challenge."""

    serializer_class = ActionLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAdmin]

    def get_queryset(self):
        challenge = get_object_or_404(Challenge, pk=self.kwargs['pk'], company=self.request.user.company)
        qs = ActionLog.objects.filter(participation__challenge=challenge)
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs


class MyParticipationsView(generics.ListAPIView):
    serializer_class = ChallengeParticipationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChallengeParticipation.objects.filter(user=self.request.user)


class ActionLogReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAdmin]

    def patch(self, request, pk):
        action_log = get_object_or_404(
            ActionLog, pk=pk, participation__challenge__company=request.user.company
        )
        if action_log.status != ActionStatus.PENDING:
            return Response(
                {'detail': 'This submission has already been reviewed.'}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SubmissionReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data['status']
        review_note = serializer.validated_data.get('review_note', '')

        participation = action_log.participation
        challenge = participation.challenge
        now = timezone.now()

        action_log.status = new_status
        action_log.reviewed_by = request.user
        action_log.reviewed_at = now
        action_log.review_note = review_note
        action_log.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note'])

        if new_status == ActionStatus.APPROVED:
            submission_approved.send(
                sender=ActionLog, action_log=action_log, participation=participation,
                points=action_log.points_awarded,
            )
            if challenge.challenge_format == ChallengeFormat.GOAL and challenge.status == ChallengeStatus.ACTIVE:
                progress = challenge.goal_progress
                if progress and progress['current'] >= progress['target']:
                    challenge.status = ChallengeStatus.COMPLETED
                    challenge.save(update_fields=['status'])
                    challenge_goal_reached.send(sender=Challenge, challenge=challenge)
        else:
            submission_rejected.send(sender=ActionLog, action_log=action_log, participation=participation)

        return Response(ActionLogSerializer(action_log).data)
