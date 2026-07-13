from django.core.management.base import BaseCommand

from apps.challenges.models import ActionCatalogItem, ChallengeType

# (name, category, default_points, co2_impact_kg, water_saved_liters, waste_recycled_kg)
# water/waste figures are illustrative estimates for demo purposes, not measured data.
ACTIONS = [
    ('Recycle a plastic bottle', ChallengeType.RECYCLING, 10, 0.08, 0, 0.05),
    ('Recycle a paper bag', ChallengeType.RECYCLING, 8, 0.05, 0, 0.02),
    ('Recycle e-waste', ChallengeType.RECYCLING, 25, 1.20, 0, 1.50),

    ('Plant a tree', ChallengeType.TREE_PLANTING, 100, 21.00, 0, 0),
    ('Plant a sapling at home', ChallengeType.TREE_PLANTING, 60, 10.00, 0, 0),

    ('Reuse a cup', ChallengeType.WATER_SAVING, 15, 0.02, 0.5, 0),
    ('Fix a leaking tap', ChallengeType.WATER_SAVING, 30, 0.50, 50, 0),
    ('Take a 5-minute shower', ChallengeType.WATER_SAVING, 15, 0.30, 40, 0),
    ('Collect rainwater', ChallengeType.WATER_SAVING, 40, 0.40, 100, 0),

    ('Switch to LED bulbs', ChallengeType.ENERGY_SAVING, 20, 5.00, 0, 0),
    ('Unplug idle electronics', ChallengeType.ENERGY_SAVING, 10, 1.00, 0, 0),
    ('Use natural light for a day', ChallengeType.ENERGY_SAVING, 15, 1.50, 0, 0),

    ('Avoid single-use plastic for a day', ChallengeType.WASTE_REDUCTION, 20, 0.30, 0, 0.30),
    ('Compost food waste', ChallengeType.WASTE_REDUCTION, 25, 2.00, 0, 1.00),
    ('Bring your own bag for shopping', ChallengeType.WASTE_REDUCTION, 10, 0.10, 0, 0.10),

    ('Carpool to work', ChallengeType.SUSTAINABLE_TRANSPORT, 30, 3.00, 0, 0),
    ('Bike to work', ChallengeType.SUSTAINABLE_TRANSPORT, 35, 4.00, 0, 0),
    ('Use public transport', ChallengeType.SUSTAINABLE_TRANSPORT, 25, 2.50, 0, 0),

    ('Donate old clothes', ChallengeType.COMMUNITY_SERVICE, 20, 3.00, 0, 2.00),
    ('Volunteer for a cleanup drive', ChallengeType.COMMUNITY_SERVICE, 50, 0.00, 0, 5.00),
    ('Donate to an environmental NGO', ChallengeType.COMMUNITY_SERVICE, 30, 0.00, 0, 0),

    ('Eat a plant-based meal', ChallengeType.SUSTAINABLE_DIET, 15, 2.00, 500, 0),
    ('Skip meat for a day', ChallengeType.SUSTAINABLE_DIET, 25, 3.50, 1000, 0),
]


class Command(BaseCommand):
    help = 'Seeds/updates the platform-wide action catalog with a starter set of loggable sustainability actions.'

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        for name, category, points, co2, water, waste in ACTIONS:
            _, created = ActionCatalogItem.objects.update_or_create(
                name=name,
                defaults={
                    'category': category, 'default_points': points, 'co2_impact_kg': co2,
                    'water_saved_liters': water, 'waste_recycled_kg': waste,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
        self.stdout.write(self.style.SUCCESS(
            f'Seeded {created_count} new, updated {updated_count} existing action catalog items '
            f'({len(ACTIONS)} total defined).'
        ))
