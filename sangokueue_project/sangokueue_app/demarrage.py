import os

from django.core.management import call_command


def preparer_production():
    """Migre et peuple les billets au démarrage, sans shell Render."""
    if os.environ.get("ENVIRONMENT") != "production":
        return
    call_command("migrate", interactive=False, verbosity=1)
    call_command("peupler_billets")
