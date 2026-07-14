from django.urls import path

from . import views

urlpatterns = [
    path('overview/', views.OverviewReportView.as_view(), name='report-overview'),
    path('timeseries/co2-and-users/', views.CO2AndUsersTimeseriesView.as_view(), name='report-co2-and-users'),
    path('timeseries/co2-growth/', views.CO2GrowthTimeseriesView.as_view(), name='report-co2-growth'),
    path('timeseries/participation/', views.ParticipationTimeseriesView.as_view(), name='report-participation'),
    path('heatmap/actions/', views.ActionsHeatmapView.as_view(), name='report-actions-heatmap'),

    path('actions-taken/summary/', views.ActionsTakenSummaryView.as_view(), name='report-actions-taken-summary'),
    path('carbon/summary/', views.CarbonSummaryView.as_view(), name='report-carbon-summary'),
    path('challenges/summary/', views.ChallengesSummaryView.as_view(), name='report-challenges-summary'),

    path('category-breakdown/', views.CategoryBreakdownView.as_view(), name='report-category-breakdown'),
    path('actions-log/', views.ActionsLogView.as_view(), name='report-actions-log'),

    path('members/summary/', views.MembersSummaryView.as_view(), name='report-members-summary'),
    path('members/', views.MembersListView.as_view(), name='report-members-list'),
]
