from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError

from notes.decorators import UPLOADER_GROUP_NAME
from notes.models import Note, PYQPaper


class Command(BaseCommand):
    help = (
        "Create (or update) a non-staff 'Uploader' account that can only access "
        "the /notes/upload/ page to add Notes and PYQ Papers - no access to /admin/."
    )

    def add_arguments(self, parser):
        parser.add_argument('username', type=str)
        parser.add_argument('password', type=str)

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']

        group, created = Group.objects.get_or_create(name=UPLOADER_GROUP_NAME)
        if created:
            note_ct = ContentType.objects.get_for_model(Note)
            pyq_ct = ContentType.objects.get_for_model(PYQPaper)
            perms = Permission.objects.filter(
                content_type__in=[note_ct, pyq_ct],
                codename__in=['add_note', 'change_note', 'add_pyqpaper', 'change_pyqpaper'],
            )
            group.permissions.set(perms)
            self.stdout.write(self.style.SUCCESS(f"Created group '{UPLOADER_GROUP_NAME}' with upload permissions."))

        user, user_created = User.objects.get_or_create(username=username)
        user.set_password(password)
        user.is_staff = False
        user.is_superuser = False
        user.save()
        user.groups.add(group)

        action = "Created" if user_created else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"{action} uploader account '{username}'. They can log in at /accounts/login/ "
            f"and use /notes/upload/ only - no admin access."
        ))
