import django.dispatch

# Sent when a manager/admin approves a logged action.
# kwargs: action_log (ActionLog instance), participation (ChallengeParticipation), points (int)
# The rewards app listens for this to credit the user's wallet; the notifications
# app listens for this (and its rejection counterpart) to notify the user.
# Kept as a signal, not a direct import, so challenges/rewards/notifications don't
# need to depend on each other's models.
submission_approved = django.dispatch.Signal()

# kwargs: action_log (ActionLog instance), participation (ChallengeParticipation)
submission_rejected = django.dispatch.Signal()

# Sent when a challenge's goal target is reached and it auto-transitions to COMPLETED.
# kwargs: challenge (Challenge instance)
challenge_goal_reached = django.dispatch.Signal()
