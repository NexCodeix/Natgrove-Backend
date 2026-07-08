from django.core.management.base import BaseCommand

from apps.challenges.models import ActionCatalogItem, ChallengeType

ACTIONS = [
    # (name, category, default_points, co2_impact_kg)
    ('Recycle a plastic bottle', ChallengeType.RECYCLING, 10, 0.08),
    ('Recycle a paper bag', ChallengeType.RECYCLING, 8, 0.05),
    ('Recycle e-waste', ChallengeType.RECYCLING, 25, 1.20),

    ('Plant a tree', ChallengeType.TREE_PLANTING, 100, 21.00),
    ('Plant a sapling at home', ChallengeType.TREE_PLANTING, 60, 10.00),

    ('Reuse a cup', ChallengeType.WATER_SAVING, 15, 0.02),
    ('Fix a leaking tap', ChallengeType.WATER_SAVING, 30, 0.50),
    ('Take a 5-minute shower', ChallengeType.WATER_SAVING, 15, 0.30),
    ('Collect rainwater', ChallengeType.WATER_SAVING, 40, 0.40),

    ('Switch to LED bulbs', ChallengeType.ENERGY_SAVING, 20, 5.00),
    ('Unplug idle electronics', ChallengeType.ENERGY_SAVING, 10, 1.00),
    ('Use natural light for a day', ChallengeType.ENERGY_SAVING, 15, 1.50),

    ('Avoid single-use plastic for a day', ChallengeType.WASTE_REDUCTION, 20, 0.30),
    ('Compost food waste', ChallengeType.WASTE_REDUCTION, 25, 2.00),
    ('Bring your own bag for shopping', ChallengeType.WASTE_REDUCTION, 10, 0.10),

    ('Carpool to work', ChallengeType.SUSTAINABLE_TRANSPORT, 30, 3.00),
    ('Bike to work', ChallengeType.SUSTAINABLE_TRANSPORT, 35, 4.00),
    ('Use public transport', ChallengeType.SUSTAINABLE_TRANSPORT, 25, 2.50),

    ('Donate old clothes', ChallengeType.COMMUNITY_SERVICE, 20, 3.00),
    ('Volunteer for a cleanup drive', ChallengeType.COMMUNITY_SERVICE, 50, 0.00),
    ('Donate to an environmental NGO', ChallengeType.COMMUNITY_SERVICE, 30, 0.00),

    ('Eat a plant-based meal', ChallengeType.SUSTAINABLE_DIET, 15, 2.00),
    ('Skip meat for a day', ChallengeType.SUSTAINABLE_DIET, 25, 3.50),
]


class Command(BaseCommand):
    help = 'Seeds the platform-wide action catalog with a starter set of loggable sustainability actions.'

    def handle(self, *args, **options):
        created_count = 0
        for name, category, points, co2 in ACTIONS:
            _, created = ActionCatalogItem.objects.get_or_create(
                name=name, defaults={'category': category, 'default_points': points, 'co2_impact_kg': co2}
            )
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(f'Seeded {created_count} new action catalog items ({len(ACTIONS)} total defined).'))
