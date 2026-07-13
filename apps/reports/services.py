from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import ExtractMonth, TruncDate
from django.utils import timezone

from apps.challenges.models import ActionLog, ActionStatus, Challenge, ChallengeParticipation

PERIOD_CHOICES = ('this_week', 'this_month', 'this_year', 'all_time')

MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
]

WEEKDAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

# (label, start_hour_inclusive, end_hour_exclusive) - Night wraps midnight.
TIME_SLOTS = [
    ('Morning', 5, 11),
    ('Noon', 11, 13),
    ('Afternoon', 13, 17),
    ('Evening', 17, 21),
    ('Night', 21, 5),
]


def period_range(period):
    """Returns (start, end) for the given period, start=None means all_time."""
    now = timezone.now()
    if period == 'this_week':
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'this_month':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == 'this_year':
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = None
    return start, now


def previous_period_range(start, end):
    """The immediately preceding window of the same duration, for computing % change."""
    if start is None:
        return None, None
    duration = end - start
    return start - duration, start


def percent_change(current, previous):
    if not previous:
        return None
    return round((current - previous) / previous * 100, 2)


def scoped_action_logs(company, community=None):
    qs = ActionLog.objects.filter(participation__challenge__company=company, status=ActionStatus.APPROVED)
    if community:
        member_ids = community.member_queryset().values_list('id', flat=True)
        qs = qs.filter(participation__user_id__in=member_ids)
    return qs


def _in_window(qs, start, end):
    if start is None:
        return qs
    return qs.filter(submitted_at__gte=start, submitted_at__lt=end)


def compute_tile(qs, start, end, prev_start, prev_end, agg_field=None):
    """Returns {'value': ..., 'change_percent': ...} for a count or Sum(agg_field) over the window vs the prior one."""
    current_qs = _in_window(qs, start, end)
    if agg_field:
        current = float(current_qs.aggregate(total=Sum(agg_field))['total'] or 0)
    else:
        current = current_qs.count()

    if prev_start is None:
        return {'value': current, 'change_percent': None}

    previous_qs = _in_window(qs, prev_start, prev_end)
    if agg_field:
        previous = float(previous_qs.aggregate(total=Sum(agg_field))['total'] or 0)
    else:
        previous = previous_qs.count()

    return {'value': current, 'change_percent': percent_change(current, previous)}


def challenges_queryset(company, community=None):
    qs = Challenge.objects.filter(company=company)
    if community:
        qs = qs.filter(communities=community)
    return qs.distinct()


def daily_co2_and_users(logs_qs, start, end):
    qs = _in_window(logs_qs, start, end)
    rows = (
        qs.annotate(day=TruncDate('submitted_at'))
        .values('day')
        .annotate(carbon_saved_kg=Sum('co2_impact_kg'), users=Count('participation__user', distinct=True))
        .order_by('day')
    )
    return [
        {'date': r['day'].isoformat(), 'carbon_saved_kg': float(r['carbon_saved_kg'] or 0), 'users': r['users']}
        for r in rows
    ]


def daily_co2_growth(logs_qs, start, end):
    qs = _in_window(logs_qs, start, end)
    rows = (
        qs.annotate(day=TruncDate('submitted_at'))
        .values('day')
        .annotate(carbon_saved_kg=Sum('co2_impact_kg'))
        .order_by('day')
    )
    return [{'date': r['day'].isoformat(), 'carbon_saved_kg': float(r['carbon_saved_kg'] or 0)} for r in rows]


def monthly_participation(logs_qs, year):
    qs = logs_qs.filter(submitted_at__year=year)
    counts = dict(
        qs.annotate(month=ExtractMonth('submitted_at')).values('month').annotate(c=Count('id')).values_list(
            'month', 'c'
        )
    )
    return [
        {'month': MONTH_NAMES[m - 1], 'employee_action_count': counts.get(m, 0)}
        for m in range(1, 13)
    ]


def _time_slot_for_hour(hour):
    for name, start_h, end_h in TIME_SLOTS:
        if start_h < end_h:
            if start_h <= hour < end_h:
                return name
        elif hour >= start_h or hour < end_h:
            return name
    return 'Night'


def actions_heatmap(logs_qs, start, end):
    qs = _in_window(logs_qs, start, end)
    counts = {}
    for submitted_at in qs.values_list('submitted_at', flat=True):
        local_dt = timezone.localtime(submitted_at)
        day = WEEKDAY_NAMES[local_dt.weekday()]
        slot = _time_slot_for_hour(local_dt.hour)
        key = (day, slot)
        counts[key] = counts.get(key, 0) + 1

    return [
        {'day': day, 'time_slot': slot, 'count': counts.get((day, slot), 0)}
        for slot, _, _ in TIME_SLOTS
        for day in WEEKDAY_NAMES
    ]


def distinct_user_count(logs_qs, start, end):
    return _in_window(logs_qs, start, end).values('participation__user').distinct().count()


def most_popular_action(logs_qs, start, end):
    row = (
        _in_window(logs_qs, start, end)
        .values('action_catalog_item__name')
        .annotate(c=Count('id'))
        .order_by('-c')
        .first()
    )
    return row['action_catalog_item__name'] if row else None


def highest_single_day_co2(logs_qs, start, end):
    row = (
        _in_window(logs_qs, start, end)
        .annotate(day=TruncDate('submitted_at'))
        .values('day')
        .annotate(total=Sum('co2_impact_kg'))
        .order_by('-total')
        .first()
    )
    if not row:
        return None
    return {'date': row['day'].isoformat(), 'carbon_saved_kg': float(row['total'] or 0)}


def top_performing_challenge(challenges_qs, start, end):
    """Ranks by approved action-log count. Re-queries by id to avoid a fan-out with any M2M community filter
    already applied to challenges_qs, which would otherwise inflate the Count annotation."""
    ids = list(challenges_qs.values_list('id', flat=True))
    qs = Challenge.objects.filter(id__in=ids)
    if start is not None:
        qs = qs.filter(created_at__gte=start, created_at__lt=end)

    best = (
        qs.annotate(
            completed_count=Count(
                'participations__submissions',
                filter=Q(participations__submissions__status=ActionStatus.APPROVED),
            )
        )
        .order_by('-completed_count')
        .first()
    )
    if not best:
        return None
    return {'title': best.title, 'completed_count': best.completed_count}


def participation_rate_percent(company, community, start, end):
    from apps.accounts.models import User

    qs = ChallengeParticipation.objects.filter(challenge__company=company)
    member_ids = None
    if community:
        member_ids = community.member_queryset().values_list('id', flat=True)
        qs = qs.filter(user_id__in=member_ids)
    if start is not None:
        qs = qs.filter(joined_at__gte=start, joined_at__lt=end)
    participant_count = qs.values('user').distinct().count()

    total_qs = User.objects.filter(company=company, is_active=True)
    if member_ids is not None:
        total_qs = total_qs.filter(id__in=member_ids)
    total = total_qs.count()

    return round(participant_count / total * 100, 2) if total else 0.0
