from django.urls import path

from . import views

urlpatterns = [
    path('action-catalog/', views.ActionCatalogListView.as_view(), name='action-catalog-list'),
    path('company-actions/<uuid:pk>/', views.CompanyActionToggleView.as_view(), name='company-action-toggle'),

    path('', views.ChallengeListCreateView.as_view(), name='challenge-list-create'),
    path('<uuid:pk>/', views.ChallengeDetailView.as_view(), name='challenge-detail'),
    path('<uuid:pk>/join/', views.ChallengeJoinView.as_view(), name='challenge-join'),
    path('<uuid:pk>/log-action/', views.LogActionView.as_view(), name='challenge-log-action'),
    path('<uuid:pk>/participants/', views.ChallengeParticipantsView.as_view(), name='challenge-participants'),
    path('<uuid:pk>/action-logs/', views.ActionLogReviewQueueView.as_view(), name='challenge-action-logs'),

    path('my-participations/', views.MyParticipationsView.as_view(), name='my-participations'),
    path('action-logs/<uuid:pk>/review/', views.ActionLogReviewView.as_view(), name='action-log-review'),
]
