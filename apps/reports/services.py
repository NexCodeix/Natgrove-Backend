from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import ExtractMonth, TruncDate
from django.utils import timezone

from apps.challenges.models import ActionLog, ActionStatus, Challenge

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
