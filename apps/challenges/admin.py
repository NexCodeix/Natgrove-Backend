from django.contrib import admin

from .models import Action, Challenge, ChallengeParticipation


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'department', 'challenge_type', 'status', 'point_reward', 'end_date']
    list_filter = ['company', 'status', 'challenge_type', 'difficulty']
    search_fields = ['title']


@admin.register(ChallengeParticipation)
class ChallengeParticipationAdmin(admin.ModelAdmin):
    list_display = ['user', 'challenge', 'status', 'joined_at', 'completed_at']
    list_filter = ['status', 'challenge']


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ['participation', 'action_type', 'status', 'submitted_at', 'reviewed_by']
    list_filter = ['status', 'action_type']
