from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Community
from apps.accounts.permissions import IsManagerOrAdmin

from . import services


class BaseReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAdmin]

    def _period(self, request, default='this_month'):
        period = request.query_params.get('period', default)
        if period not in services.PERIOD_CHOICES:
            return None, Response(
                {'period': f'Must be one of {", ".join(services.PERIOD_CHOICES)}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return period, None

    def _community(self, request):
        community_id = request.query_params.get('community')
        if not community_id:
            return None, None
        community = get_object_or_404(Community, pk=community_id, company_id=request.user.company_id)
        return community, None


def _challenges_tile(challenges_qs, start, end, prev_start, prev_end):
    def _count(qs, s, e):
        if s is None:
            return qs.count()
        return qs.filter(created_at__gte=s, created_at__lt=e).count()

    current = _count(challenges_qs, start, end)
    if prev_start is None:
        return {'value': current, 'change_percent': None}
    previous = _count(challenges_qs, prev_start, prev_end)
    return {'value': current, 'change_percent': services.percent_change(current, previous)}


class OverviewReportView(BaseReportView):
    """The 5 KPI tiles on the Reports overview dashboard."""

    def get(self, request):
        period, error = self._period(request)
        if error:
            return error
        community, error = self._community(request)
        if error:
            return error

        start, end = services.period_range(period)
        prev_start, prev_end = services.previous_period_range(start, end)

        logs = services.scoped_action_logs(request.user.company, community)
        challenges = services.challenges_queryset(request.user.company, community)

        return Response({
            'period': period,
            'actions_taken': services.compute_tile(logs, start, end, prev_start, prev_end),
            'carbon_emission_saved_kg': services.compute_tile(logs, start, end, prev_start, prev_end, 'co2_impact_kg'),
            'challenges': _challenges_tile(challenges, start, end, prev_start, prev_end),
            'water_recycled_kg': services.compute_tile(logs, start, end, prev_start, prev_end, 'waste_recycled_kg'),
            'water_usage_l': services.compute_tile(logs, start, end, prev_start, prev_end, 'water_saved_liters'),
        })


class CO2AndUsersTimeseriesView(BaseReportView):
    """Bar chart: daily CO2 saved + distinct active users."""

    def get(self, request):
        period, error = self._period(request, default='this_week')
        if error:
            return error
        community, error = self._community(request)
        if error:
            return error

        start, end = services.period_range(period)
        logs = services.scoped_action_logs(request.user.company, community)
        return Response({'period': period, 'results': services.daily_co2_and_users(logs, start, end)})


class CO2GrowthTimeseriesView(BaseReportView):
    """Area chart: daily CO2 saved. Reused by the Carbon Footprint and Challenges drill-downs."""

    def get(self, request):
        period, error = self._period(request, default='this_week')
        if error:
            return error
        community, error = self._community(request)
        if error:
            return error

        start, end = services.period_range(period)
        logs = services.scoped_action_logs(request.user.company, community)
        return Response({'period': period, 'results': services.daily_co2_growth(logs, start, end)})


class ParticipationTimeseriesView(BaseReportView):
    """Line chart: approved action counts per month for a given year. Reused by Actions Taken drill-down."""

    def get(self, request):
        year = request.query_params.get('year', str(timezone.now().year))
        if not year.isdigit():
            return Response({'year': 'Must be a 4-digit year.'}, status=status.HTTP_400_BAD_REQUEST)
        community, error = self._community(request)
        if error:
            return error

        logs = services.scoped_action_logs(request.user.company, community)
        return Response({'year': int(year), 'results': services.monthly_participation(logs, int(year))})


class ActionsHeatmapView(BaseReportView):
    """Action count by day-of-week x time-of-day."""

    def get(self, request):
        period, error = self._period(request, default='all_time')
        if error:
            return error
        community, error = self._community(request)
        if error:
            return error

        start, end = services.period_range(period)
        logs = services.scoped_action_logs(request.user.company, community)
        return Response({'period': period, 'results': services.actions_heatmap(logs, start, end)})
