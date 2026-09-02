from django import forms
from django.core.exceptions import ValidationError
from .models import PYQPaper, CLASS_CHOICES


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """A FileField that accepts multiple files and returns a list of them."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'multiple': True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


class BulkNoteUploadForm(forms.Form):
    """
    Just pick Class + Subject, then drop in PDFs - works the same way for
    every class (9-12). No need to pre-create Chapters: each PDF becomes
    its own Chapter (named after the cleaned filename) under the chosen
    Subject, with one Note inside it. If a Chapter with that exact name
    already exists for the subject, the new PDF is added as another Note
    under it instead of duplicating the chapter.
    """
    class_level = forms.ChoiceField(choices=CLASS_CHOICES)
    subject = forms.ModelChoiceField(queryset=None)
    pdf_files = MultipleFileField(
        help_text="Select multiple PDF files. Each file becomes its own chapter + note (named from the filename)."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Subject
        self.fields['subject'].queryset = Subject.objects.all()

    def clean(self):
        cleaned_data = super().clean()
        class_level = cleaned_data.get('class_level')
        subject = cleaned_data.get('subject')
        if class_level and subject and str(subject.class_level) != str(class_level):
            raise ValidationError(
                f'"{subject.name}" is a Class {subject.class_level} subject, not Class {class_level}. '
                f'Pick a subject that matches the selected class.'
            )
        return cleaned_data

    def clean_pdf_files(self):
        files = self.cleaned_data.get('pdf_files') or []
        if not files:
            raise ValidationError("Please select at least one PDF file.")
        for f in files:
            if not f.name.lower().endswith('.pdf'):
                raise ValidationError(f'"{f.name}" is not a PDF file.')
        return files


class BulkPYQUploadForm(forms.Form):
    class_level = forms.ChoiceField(choices=CLASS_CHOICES)
    subject = forms.ModelChoiceField(queryset=None)
    year = forms.IntegerField(min_value=2000, max_value=2100)
    set_label = forms.CharField(
        max_length=50, required=False,
        help_text='Optional, e.g. "Set 1" — leave blank if only one set.'
    )
    pdf_files = MultipleFileField(
        help_text="Select multiple PDF files. Each file becomes one PYQ Paper (same year/subject/class)."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Subject
        self.fields['subject'].queryset = Subject.objects.all()

    def clean_pdf_files(self):
        files = self.cleaned_data.get('pdf_files') or []
        if not files:
            raise ValidationError("Please select at least one PDF file.")
        for f in files:
            if not f.name.lower().endswith('.pdf'):
                raise ValidationError(f'"{f.name}" is not a PDF file.')
        return files
