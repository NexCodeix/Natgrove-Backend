from django.urls import path

from . import views

urlpatterns = [
    path('', views.ChallengeListCreateView.as_view(), name='challenge-list-create'),
    path('<uuid:pk>/', views.ChallengeDetailView.as_view(), name='challenge-detail'),
    path('<uuid:pk>/join/', views.ChallengeJoinView.as_view(), name='challenge-join'),
    path('<uuid:pk>/submit/', views.ChallengeSubmitView.as_view(), name='challenge-submit'),
    path('<uuid:pk>/participations/', views.ChallengeParticipationListView.as_view(), name='challenge-participations'),
    path('my-participations/', views.MyParticipationsView.as_view(), name='my-participations'),
    path('submissions/<uuid:pk>/review/', views.SubmissionReviewView.as_view(), name='submission-review'),
]
