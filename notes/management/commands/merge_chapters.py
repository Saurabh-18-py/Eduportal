from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from notes.models import Chapter, Note


class Command(BaseCommand):
    help = (
        "Merge one or more duplicate chapters into a chosen 'keep' chapter: "
        "moves every note from the duplicates onto the keep chapter, then "
        "deletes the (now empty) duplicate chapters. Refuses to merge chapters "
        "that belong to different subjects, as a safety check. "
        "Use find_duplicate_chapters first to find the chapter IDs."
    )

    def add_arguments(self, parser):
        parser.add_argument('--keep', type=int, required=True, help='Chapter ID to keep (the canonical one)')
        parser.add_argument(
            '--into', dest='merge_ids', type=int, nargs='+', required=True,
            help='Chapter ID(s) whose notes get moved into --keep, then get deleted'
        )

    def handle(self, *args, **options):
        keep_id = options['keep']
        merge_ids = options['merge_ids']

        if keep_id in merge_ids:
            raise CommandError("--keep chapter cannot also appear in --into.")

        try:
            keep_chapter = Chapter.objects.get(id=keep_id)
        except Chapter.DoesNotExist:
            raise CommandError(f"Chapter id={keep_id} does not exist.")

        merge_chapters = list(Chapter.objects.filter(id__in=merge_ids))
        found_ids = {c.id for c in merge_chapters}
        missing = set(merge_ids) - found_ids
        if missing:
            raise CommandError(f"Chapter id(s) not found: {sorted(missing)}")

        for ch in merge_chapters:
            if ch.subject_id != keep_chapter.subject_id:
                raise CommandError(
                    f"Chapter id={ch.id} ('{ch.title}') belongs to a different subject "
                    f"than the --keep chapter ('{keep_chapter.subject}'). Refusing to merge across subjects."
                )

        self.stdout.write(
            f"Keeping: id={keep_chapter.id} '{keep_chapter.title}' "
            f"({keep_chapter.notes.count()} notes currently)"
        )

        total_moved = 0
        with transaction.atomic():
            for ch in merge_chapters:
                moved = Note.objects.filter(chapter=ch).update(chapter=keep_chapter)
                total_moved += moved
                self.stdout.write(f"  Moved {moved} note(s) from id={ch.id} '{ch.title}', then deleting it.")
                ch.delete()

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Moved {total_moved} note(s) into '{keep_chapter.title}' (id={keep_chapter.id})."
        ))
        cache.delete(f'chapters:subject:{keep_chapter.subject_id}')
