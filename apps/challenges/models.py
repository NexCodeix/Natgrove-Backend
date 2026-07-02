from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class ChallengeType(models.TextChoices):
    WATERSAVE = 'WATERSAVE', 'Water Save'
    TREEPLANT = 'TREEPLANT', 'Tree Plant'


class ChallengeDifficulty(models.TextChoices):
    EASY = 'EASY', 'Easy'
    MEDIUM = 'MEDIUM', 'Medium'
    HARD = 'HARD', 'Hard'


class ChallengeStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    ACTIVE = 'ACTIVE', 'Active'
    COMPLETED = 'COMPLETED', 'Completed'


class ParticipationStatus(models.TextChoices):
    JOINED = 'JOINED', 'Joined'
    SUBMITTED = 'SUBMITTED', 'Submitted'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'


class ActionStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'


class Challenge(BaseModel):
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='challenges')
    department = models.ForeignKey(
        'accounts.Department', null=True, blank=True, on_delete=models.SET_NULL, related_name='challenges',
        help_text='Leave blank for a company-wide challenge.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='created_challenges'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    challenge_type = models.CharField(max_length=20, choices=ChallengeType.choices)
    difficulty = models.CharField(max_length=10, choices=ChallengeDifficulty.choices, default=ChallengeDifficulty.MEDIUM)
    point_reward = models.PositiveIntegerField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(max_length=10, choices=ChallengeStatus.choices, default=ChallengeStatus.DRAFT)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class ChallengeParticipation(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='challenge_participations'
    )
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='participations')
    status = models.CharField(max_length=10, choices=ParticipationStatus.choices, default=ParticipationStatus.JOINED)
    joined_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'challenge')
        ordering = ['-joined_at']

    def __str__(self):
        return f'{self.user.email} -> {self.challenge.title} [{self.status}]'


class Action(BaseModel):
    """A proof-of-completion submission made against a challenge participation."""

    participation = models.ForeignKey(ChallengeParticipation, on_delete=models.CASCADE, related_name='submissions')
    action_type = models.CharField(max_length=20, choices=ChallengeType.choices)
    proof_image = models.ImageField(upload_to='challenge_proofs/')
    caption = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=ActionStatus.choices, default=ActionStatus.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_submissions'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'Submission for {self.participation} [{self.status}]'
