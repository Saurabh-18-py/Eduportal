from django.core.cache import cache
from django.db import IntegrityError
from django.db.models import Max
from rest_framework.response import Response
from rest_framework.views import APIView

from notes.models import Chapter, Note, PYQPaper, Subject

from .admin_views import IsSuperuser


def _bust(subject_id):
    cache.delete(f'chapters:subject:{subject_id}')


def _drop_file(field_file):
    """Remove the stored PDF too, but never fail the request because of it."""
    try:
        if field_file:
            field_file.delete(save=False)
    except Exception:
        pass


class SubjectCreateView(APIView):
    """POST /api/admin/subjects/ {"name": "...", "class_level": 9}"""
    permission_classes = [IsSuperuser]

    def post(self, request):
        name = str(request.data.get('name', '')).strip()[:100]
        try:
            class_level = int(request.data.get('class_level'))
        except (TypeError, ValueError):
            class_level = 0
        if not name or class_level not in (9, 10, 11, 12):
            return Response({'error': 'Enter a subject name and choose class 9-12.'}, status=400)
        if Subject.objects.filter(name__iexact=name, class_level=class_level).exists():
            return Response({'error': 'That subject already exists for this class.'}, status=400)
        s = Subject.objects.create(name=name, class_level=class_level)
        return Response({'id': s.id, 'name': s.name, 'class_level': s.class_level}, status=201)


class SubjectDetailView(APIView):
    """PATCH /api/admin/subjects/<id>/ {"name": "..."}"""
    permission_classes = [IsSuperuser]

    def patch(self, request, subject_id):
        s = Subject.objects.filter(id=subject_id).first()
        if not s:
            return Response({'error': 'Subject not found.'}, status=404)
        name = str(request.data.get('name', '')).strip()[:100]
        if not name:
            return Response({'error': 'Enter a name.'}, status=400)
        if Subject.objects.filter(name__iexact=name, class_level=s.class_level).exclude(id=s.id).exists():
            return Response({'error': 'Another subject already uses that name.'}, status=400)
        s.name = name
        try:
            s.save(update_fields=['name'])
        except IntegrityError:
            return Response({'error': 'Another subject already uses that name.'}, status=400)
        return Response({'id': s.id, 'name': s.name, 'class_level': s.class_level})


class ChapterCreateView(APIView):
    """POST /api/admin/chapters/ {"subject": 5, "title": "..."}"""
    permission_classes = [IsSuperuser]

    def post(self, request):
        subject = Subject.objects.filter(id=request.data.get('subject') or 0).first()
        title = str(request.data.get('title', '')).strip()[:200]
        if not subject:
            return Response({'error': 'Choose a subject.'}, status=400)
        if not title:
            return Response({'error': 'Enter the chapter name.'}, status=400)
        if Chapter.objects.filter(subject=subject, title__iexact=title).exists():
            return Response({'error': 'This chapter already exists in the subject.'}, status=400)
        last = Chapter.objects.filter(subject=subject).aggregate(m=Max('order'))['m'] or 0
        c = Chapter.objects.create(subject=subject, title=title, order=last + 1)
        _bust(subject.id)
        return Response({'id': c.id, 'title': c.title, 'order': c.order}, status=201)


class ChapterDetailView(APIView):
    """PATCH /api/admin/chapters/<id>/ {"title": "...", "order": 3}   DELETE removes it and its PDFs"""
    permission_classes = [IsSuperuser]

    def patch(self, request, chapter_id):
        c = Chapter.objects.filter(id=chapter_id).first()
        if not c:
            return Response({'error': 'Chapter not found.'}, status=404)
        if 'title' in request.data:
            title = str(request.data['title']).strip()[:200]
            if not title:
                return Response({'error': 'Enter the chapter name.'}, status=400)
            if Chapter.objects.filter(subject=c.subject, title__iexact=title).exclude(id=c.id).exists():
                return Response({'error': 'Another chapter already has that name.'}, status=400)
            c.title = title
        if 'order' in request.data:
            try:
                order = int(request.data['order'])
                if not 0 <= order <= 999:
                    raise ValueError
            except (TypeError, ValueError):
                return Response({'error': 'Order must be a number.'}, status=400)
            c.order = order
        c.save()
        _bust(c.subject_id)
        return Response({'id': c.id, 'title': c.title, 'order': c.order})

    def delete(self, request, chapter_id):
        c = Chapter.objects.filter(id=chapter_id).first()
        if not c:
            return Response({'error': 'Chapter not found.'}, status=404)
        notes = list(Note.objects.filter(chapter=c))
        for n in notes:
            _drop_file(n.pdf_file)
        subject_id = c.subject_id
        c.delete()
        _bust(subject_id)
        return Response({'deleted': True, 'files_removed': len(notes)})


class NoteDetailView(APIView):
    """PATCH /api/admin/notes/<id>/ {"title": "..."}   DELETE"""
    permission_classes = [IsSuperuser]

    def patch(self, request, note_id):
        n = Note.objects.filter(id=note_id).first()
        if not n:
            return Response({'error': 'File not found.'}, status=404)
        title = str(request.data.get('title', '')).strip()[:200]
        if not title:
            return Response({'error': 'Enter a title.'}, status=400)
        n.title = title
        n.save(update_fields=['title'])
        return Response({'id': n.id, 'title': n.title})

    def delete(self, request, note_id):
        n = Note.objects.select_related('chapter').filter(id=note_id).first()
        if not n:
            return Response({'error': 'File not found.'}, status=404)
        subject_id = n.chapter.subject_id
        _drop_file(n.pdf_file)
        n.delete()
        _bust(subject_id)
        return Response({'deleted': True})


class PYQDetailView(APIView):
    """DELETE /api/admin/pyq/<id>/"""
    permission_classes = [IsSuperuser]

    def delete(self, request, pyq_id):
        p = PYQPaper.objects.filter(id=pyq_id).first()
        if not p:
            return Response({'error': 'Paper not found.'}, status=404)
        _drop_file(p.pdf_file)
        p.delete()
        return Response({'deleted': True})
