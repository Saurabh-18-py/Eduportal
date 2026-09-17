from django.core.management.base import BaseCommand, CommandError

from notifications.models import PushSubscription
from notifications.push import send_push_to_subscription


class Command(BaseCommand):
    help = (
        "Send a web push notification.\n"
        "Examples:\n"
        "  python manage.py send_push --title 'New Test!' --body 'Class 10 Maths mock test is live.' --all\n"
        "  python manage.py send_push --title 'Hi' --body 'Just for you' --username saurabh\n"
    )

    def add_arguments(self, parser):
        parser.add_argument('--title', required=True)
        parser.add_argument('--body', required=True)
        parser.add_argument('--url', default='/', help='URL opened when the notification is tapped')
        parser.add_argument('--all', action='store_true', help='Send to every subscribed device')
        parser.add_argument('--username', help='Send only to this user\'s device(s)')

    def handle(self, *args, **options):
        if not options['all'] and not options['username']:
            raise CommandError('Pass --all or --username <name>')

        qs = PushSubscription.objects.all()
        if options['username']:
            qs = qs.filter(user__username=options['username'])

        if not qs.exists():
            self.stdout.write(self.style.WARNING('No matching subscriptions found.'))
            return

        sent, failed = 0, 0
        for sub in qs:
            ok, error = send_push_to_subscription(sub, options['title'], options['body'], options['url'])
            if ok:
                sent += 1
            else:
                failed += 1
                self.stdout.write(self.style.ERROR(f'  Failed for {sub.user.username}: {error}'))

        self.stdout.write(self.style.SUCCESS(f'Done. Sent: {sent}, Failed: {failed}'))
