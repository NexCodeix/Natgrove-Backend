from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserRole
from apps.accounts.permissions import IsManagerOrAdmin

from .models import Action, ActionStatus, Challenge, ChallengeParticipation, ParticipationStatus
from .serializers import (
    ChallengeParticipationSerializer,
    ChallengeSerializer,
    SubmissionReviewSerializer,
    SubmitProofSerializer,
)
from .signals import submission_approved, submission_rejected


class ChallengeListCreateView(generics.ListCreateAPIView):
    serializer_class = ChallengeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Challenge.objects.filter(company=user.company)
        if user.role == UserRole.EMPLOYEE:
            qs = qs.filter(Q(department__isnull=True) | Q(department=user.department))
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


class ChallengeDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ChallengeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Challenge.objects.filter(company=self.request.user.company)

    def get_permissions(self):
        if self.request.method in ('PATCH', 'PUT'):
            return [permissions.IsAuthenticated(), IsManagerOrAdmin()]
        return super().get_permissions()


class ChallengeJoinView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        challenge = get_object_or_404(Challenge, pk=pk, company=request.user.company)
        if challenge.status != 'ACTIVE':
            return Response({'detail': 'This challenge is not currently active.'}, status=status.HTTP_400_BAD_REQUEST)
        if challenge.department_id and challenge.department_id != request.user.department_id:
            return Response(
                {'detail': 'This challenge is scoped to a different department.'}, status=status.HTTP_403_FORBIDDEN
            )
        participation, created = ChallengeParticipation.objects.get_or_create(
            user=request.user, challenge=challenge
        )
        serializer = ChallengeParticipationSerializer(participation)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ChallengeSubmitView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        challenge = get_object_or_404(Challenge, pk=pk, company=request.user.company)
        participation = get_object_or_404(ChallengeParticipation, user=request.user, challenge=challenge)
        if participation.status not in (ParticipationStatus.JOINED, ParticipationStatus.REJECTED):
            return Response(
                {'detail': f'Cannot submit proof while participation is {participation.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = SubmitProofSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(participation=participation, action_type=challenge.challenge_type)
        participation.status = ParticipationStatus.SUBMITTED
        participation.save(update_fields=['status'])
        return Response(ChallengeParticipationSerializer(participation).data, status=status.HTTP_201_CREATED)


class ChallengeParticipationListView(generics.ListAPIView):
    """Manager/admin review queue for a challenge's submissions."""

    serializer_class = ChallengeParticipationSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAdmin]

    def get_queryset(self):
        challenge = get_object_or_404(Challenge, pk=self.kwargs['pk'], company=self.request.user.company)
        qs = ChallengeParticipation.objects.filter(challenge=challenge)
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs


class MyParticipationsView(generics.ListAPIView):
    serializer_class = ChallengeParticipationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChallengeParticipation.objects.filter(user=self.request.user)


class SubmissionReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAdmin]

    def patch(self, request, pk):
        action = get_object_or_404(Action, pk=pk, participation__challenge__company=request.user.company)
        if action.status != ActionStatus.PENDING:
            return Response(
                {'detail': 'This submission has already been reviewed.'}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SubmissionReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data['status']
        review_note = serializer.validated_data.get('review_note', '')

        participation = action.participation
        now = timezone.now()

        action.status = new_status
        action.reviewed_by = request.user
        action.reviewed_at = now
        action.review_note = review_note
        action.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note'])

        if new_status == ActionStatus.APPROVED:
            participation.status = ParticipationStatus.APPROVED
            participation.completed_at = now
            participation.save(update_fields=['status', 'completed_at'])
            submission_approved.send(
                sender=Action, action=action, participation=participation,
                points=participation.challenge.point_reward,
            )
        else:
            participation.status = ParticipationStatus.REJECTED
            participation.save(update_fields=['status'])
            submission_rejected.send(sender=Action, action=action, participation=participation)

        return Response(ChallengeParticipationSerializer(participation).data)
