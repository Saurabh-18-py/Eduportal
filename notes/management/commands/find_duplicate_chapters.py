import re
from collections import defaultdict

from django.core.management.base import BaseCommand

from notes.models import Chapter


def normalize_title(title):
    """
    Loosely normalizes a chapter title so near-duplicates group together:
    lowercase, strips a leading "Ch1", "Ch 2:", "Chapter 3 -" style prefix,
    strips punctuation, collapses whitespace, and strips a trailing 's' so
    singular/plural variants match (e.g. "Real Number" vs "Real Numbers").
    """
    t = title.lower().strip()
    t = re.sub(r'^chapter\s*\d+[\s:_.\-]*', '', t)
    t = re.sub(r'^ch\s*\d+[\s:_.\-]*', '', t)
    t = re.sub(r'[^a-z0-9\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if t.endswith('s') and len(t) > 3:
        t = t[:-1]
    return t


class Command(BaseCommand):
    help = (
        "Find chapters under the same subject whose titles look like duplicates "
        "(created from slightly different PDF filenames). Read-only - only prints "
        "groups for you to review, never changes or deletes anything. "
        "Use merge_chapters afterwards to actually clean up a group."
    )

    def add_arguments(self, parser):
        parser.add_argument('--class', dest='class_level', type=int, default=None, help='Limit to one class (default: all)')
        parser.add_argument('--subject', default=None, help='Limit to one subject name (default: all)')

    def handle(self, *args, **options):
        chapters = Chapter.objects.select_related('subject').order_by(
            'subject__class_level', 'subject__name', 'title'
        )
        if options['class_level']:
            chapters = chapters.filter(subject__class_level=options['class_level'])
        if options['subject']:
            chapters = chapters.filter(subject__name__iexact=options['subject'])

        by_subject = defaultdict(list)
        for ch in chapters:
            by_subject[ch.subject].append(ch)

        found_any = False
        for subject, chapter_list in by_subject.items():
            groups = defaultdict(list)
            for ch in chapter_list:
                groups[normalize_title(ch.title)].append(ch)

            duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
            if not duplicate_groups:
                continue

            found_any = True
            self.stdout.write(self.style.WARNING(f"\n=== {subject} ==="))
            for key, group in duplicate_groups.items():
                self.stdout.write(f"  Possible duplicate group ({key!r}):")
                for ch in sorted(group, key=lambda c: -c.notes.count()):
                    self.stdout.write(
                        f"    id={ch.id:<5} order={ch.order:<4} notes={ch.notes.count():<3} title={ch.title!r}"
                    )

        if not found_any:
            self.stdout.write(self.style.SUCCESS("No likely duplicate chapters found."))
        else:
            self.stdout.write(self.style.WARNING(
                "\nReview the groups above. For each group, pick the one to KEEP "
                "(usually the one with the correct/official title) and merge the "
                "rest into it:\n"
                "  python manage.py merge_chapters --keep <id> --into <id> [<id> ...]"
            ))
