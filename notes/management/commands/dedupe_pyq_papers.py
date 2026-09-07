from collections import defaultdict

from django.core.management.base import BaseCommand

from notes.models import PYQPaper


class Command(BaseCommand):
    help = (
        "Finds PYQ papers that are exact duplicates (same subject, year, and set) - "
        "keeps the oldest one in each group and reports/removes the rest. Useful after "
        "a crash-and-retry during bulk upload creates the same paper more than once."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--auto-delete', action='store_true', default=False,
            help='Delete duplicates automatically. Without this, only reports them.'
        )

    def handle(self, *args, **options):
        auto_delete = options['auto_delete']
        papers = PYQPaper.objects.select_related('subject').order_by('id')

        groups = defaultdict(list)
        for p in papers:
            key = (p.subject_id, p.year, p.set_label)
            groups[key].append(p)

        total_dupes = 0
        for (subject_id, year, set_label), group in groups.items():
            if len(group) <= 1:
                continue

            keep = group[0]
            dupes = group[1:]
            total_dupes += len(dupes)

            action = "Deleting" if auto_delete else "Found"
            self.stdout.write(
                f"{keep.subject} {year} Set {set_label or '(none)'}: "
                f"keeping id={keep.id}, {action.lower()} {len(dupes)} duplicate(s) "
                f"(ids={[d.id for d in dupes]})"
            )
            if auto_delete:
                for d in dupes:
                    d.delete()

        if total_dupes == 0:
            self.stdout.write(self.style.SUCCESS("No duplicate PYQ papers found."))
        elif auto_delete:
            self.stdout.write(self.style.SUCCESS(f"\nDeleted {total_dupes} duplicate paper(s)."))
        else:
            self.stdout.write(self.style.WARNING(
                f"\nFound {total_dupes} duplicate(s). Re-run with --auto-delete to remove them."
            ))
