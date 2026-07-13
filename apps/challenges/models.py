from django.conf import settings
from django.db import models
from django.db.models import Sum

from apps.core.models import BaseModel


class ChallengeType(models.TextChoices):
    RECYCLING = 'RECYCLING', 'Recycling'
    TREE_PLANTING = 'TREE_PLANTING', 'Tree Planting'
    WATER_SAVING = 'WATER_SAVING', 'Water Saving'
    ENERGY_SAVING = 'ENERGY_SAVING', 'Energy Saving'
    WASTE_REDUCTION = 'WASTE_REDUCTION', 'Waste Reduction'
    SUSTAINABLE_TRANSPORT = 'SUSTAINABLE_TRANSPORT', 'Sustainable Transport'
    COMMUNITY_SERVICE = 'COMMUNITY_SERVICE', 'Community Service'
    SUSTAINABLE_DIET = 'SUSTAINABLE_DIET', 'Sustainable Diet'
    OTHER = 'OTHER', 'Other'


class ChallengeFormat(models.TextChoices):
    GOAL = 'GOAL', 'Goal Achieve'
    TIMELINE = 'TIMELINE', 'Timeline'


class GoalMetric(models.TextChoices):
    TOTAL_ACTIONS = 'TOTAL_ACTIONS', 'Total Actions Logged'
    TOTAL_POINTS = 'TOTAL_POINTS', 'Total Points Earned'


class ChallengeStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    UPCOMING = 'UPCOMING', 'Upcoming'
    ACTIVE = 'ACTIVE', 'Active'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class PrizeType(models.TextChoices):
    VOUCHER = 'VOUCHER', 'Voucher'
    BADGE = 'BADGE', 'Badge'
    PHYSICAL_ITEM = 'PHYSICAL_ITEM', 'Physical Item'
    BONUS_POINTS = 'BONUS_POINTS', 'Bonus Points'


class ParticipationStatus(models.TextChoices):
    JOINED = 'JOINED', 'Joined'
    LEFT = 'LEFT', 'Left'


class ActionStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'


class ActionCatalogItem(BaseModel):
    """
    Platform-wide library of loggable sustainability actions (e.g. "Reuse a
    cup"). Company admins attach items from this shared catalog to their
    challenges rather than each company inventing its own action set.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to='action_icons/', null=True, blank=True)
    category = models.CharField(max_length=30, choices=ChallengeType.choices)
    default_points = models.PositiveIntegerField()
    co2_impact_kg = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    water_saved_liters = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    waste_recycled_kg = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class CompanyActionSetting(BaseModel):
    """
    Per-company override on the shared, platform-wide action catalog. Absence
    of a row means enabled (opt-out model) - a brand-new company immediately
    has the full catalog available without any setup, and just disables the
    handful of actions it doesn't want to offer.
    """

    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='action_settings')
    action_catalog_item = models.ForeignKey(ActionCatalogItem, on_delete=models.CASCADE, related_name='company_settings')
    is_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ('company', 'action_catalog_item')

    def __str__(self):
        return f'{self.action_catalog_item.name} for {self.company.name}: {"enabled" if self.is_enabled else "disabled"}'


class Challenge(BaseModel):
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='challenges')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='created_challenges'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    how_to_play = models.TextField(blank=True)
    rules = models.TextField(blank=True)
    image = models.ImageField(upload_to='challenge_images/', null=True, blank=True)
    challenge_type = models.CharField(max_length=30, choices=ChallengeType.choices)

    actions = models.ManyToManyField(ActionCatalogItem, related_name='challenges', blank=True)
    communities = models.ManyToManyField('accounts.Community', related_name='challenges', blank=True)

    challenge_format = models.CharField(max_length=10, choices=ChallengeFormat.choices, default=ChallengeFormat.TIMELINE)
    goal_metric = models.CharField(max_length=20, choices=GoalMetric.choices, null=True, blank=True)
    goal_title = models.CharField(max_length=255, blank=True)
    goal_count = models.PositiveIntegerField(null=True, blank=True)

    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=10, choices=ChallengeStatus.choices, default=ChallengeStatus.DRAFT)
    is_archived = models.BooleanField(default=False)

    prize_type = models.CharField(max_length=20, choices=PrizeType.choices, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def approved_action_logs(self):
        return ActionLog.objects.filter(participation__challenge=self, status=ActionStatus.APPROVED)

    @property
    def participant_count(self):
        return self.participations.count()

    @property
    def estimated_audience_count(self):
        """Deduplicated headcount across all communities this challenge is scoped to."""
        user_ids = set()
        for community in self.communities.all():
            user_ids.update(community.member_queryset().values_list('id', flat=True))
        return len(user_ids)

    @property
    def estimated_co2_impact_kg(self):
        """Sum of the CO2 impact of each selected action, before anyone has actually logged one."""
        return self.actions.aggregate(total=Sum('co2_impact_kg'))['total'] or 0

    @property
    def actual_co2_saved_kg(self):
        return self.approved_action_logs.aggregate(total=Sum('co2_impact_kg'))['total'] or 0

    @property
    def goal_progress(self):
        if self.challenge_format != ChallengeFormat.GOAL or not self.goal_count:
            return None
        if self.goal_metric == GoalMetric.TOTAL_POINTS:
            current = self.approved_action_logs.aggregate(total=Sum('points_awarded'))['total'] or 0
        else:
            current = self.approved_action_logs.count()
        return {'current': current, 'target': self.goal_count, 'percent': min(100, round(current / self.goal_count * 100, 2))}


class ChallengePrize(BaseModel):
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='prizes')
    rank = models.PositiveIntegerField(help_text='1 = first prize, 2 = second prize, etc.')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='prize_images/', null=True, blank=True)

    class Meta:
        unique_together = ('challenge', 'rank')
        ordering = ['rank']

    def __str__(self):
        return f'#{self.rank} {self.title} ({self.challenge.title})'


class ChallengeParticipation(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='challenge_participations'
    )
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='participations')
    status = models.CharField(max_length=10, choices=ParticipationStatus.choices, default=ParticipationStatus.JOINED)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'challenge')
        ordering = ['-joined_at']

    def __str__(self):
        return f'{self.user.email} -> {self.challenge.title}'

    @property
    def points_earned(self):
        return self.submissions.filter(status=ActionStatus.APPROVED).aggregate(total=Sum('points_awarded'))['total'] or 0

    @property
    def actions_completed_count(self):
        return self.submissions.filter(status=ActionStatus.APPROVED).count()


class ActionLog(BaseModel):
    """A single instance of a participant performing one of the challenge's catalog actions."""

    participation = models.ForeignKey(ChallengeParticipation, on_delete=models.CASCADE, related_name='submissions')
    action_catalog_item = models.ForeignKey(ActionCatalogItem, on_delete=models.PROTECT, related_name='logs')
    points_awarded = models.PositiveIntegerField(help_text='Snapshot of the catalog item points at submission time.')
    co2_impact_kg = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text='Snapshot of the catalog item CO2 impact at submission time.',
    )
    water_saved_liters = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text='Snapshot of the catalog item water-saved impact at submission time.',
    )
    waste_recycled_kg = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text='Snapshot of the catalog item waste-recycled impact at submission time.',
    )
    proof_image = models.ImageField(upload_to='action_proofs/')
    caption = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=ActionStatus.choices, default=ActionStatus.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_action_logs'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.action_catalog_item.name} for {self.participation} [{self.status}]'
