from django.contrib import admin

from .models import ActionCatalogItem, ActionLog, Challenge, ChallengeParticipation, ChallengePrize


@admin.register(ActionCatalogItem)
class ActionCatalogItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'default_points', 'co2_impact_kg', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name']


class ChallengePrizeInline(admin.TabularInline):
    model = ChallengePrize
    extra = 0


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'challenge_type', 'challenge_format', 'status', 'start_date', 'end_date']
    list_filter = ['company', 'status', 'challenge_type', 'challenge_format']
    search_fields = ['title']
    filter_horizontal = ['actions', 'communities']
    inlines = [ChallengePrizeInline]


@admin.register(ChallengeParticipation)
class ChallengeParticipationAdmin(admin.ModelAdmin):
    list_display = ['user', 'challenge', 'status', 'joined_at']
    list_filter = ['status', 'challenge']


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ['participation', 'action_catalog_item', 'points_awarded', 'status', 'submitted_at', 'reviewed_by']
    list_filter = ['status', 'action_catalog_item']
