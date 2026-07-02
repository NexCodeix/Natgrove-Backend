import django.dispatch

# Sent when a manager/admin approves a challenge submission.
# kwargs: action (Action instance), participation (ChallengeParticipation), points (int)
# The rewards app listens for this to credit the user's wallet; the notifications
# app listens for this (and its rejection counterpart) to notify the user.
# Kept as a signal, not a direct import, so challenges/rewards/notifications don't
# need to depend on each other's models.
submission_approved = django.dispatch.Signal()

# kwargs: action (Action instance), participation (ChallengeParticipation)
submission_rejected = django.dispatch.Signal()
