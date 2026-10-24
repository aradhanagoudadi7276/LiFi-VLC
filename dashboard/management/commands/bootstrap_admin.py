import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the starter admin account when it does not already exist."

    def handle(self, *args, **options):
        user_model = get_user_model()
        username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "admin")
        password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "admin@123")

        if user_model.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User "{username}" already exists; no changes made.')
            )
            return

        user_model.objects.create_superuser(
            username=username,
            email="",
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f'Created admin user "{username}".'))
