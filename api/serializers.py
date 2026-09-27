from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import StudentProfile, Avatar
from notes.models import Subject, Chapter, Note, PYQPaper
from mocktest.models import Test, Question, Choice


# ---------------------------------------------------------------- accounts

class AvatarSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Avatar
        fields = ['id', 'image_url', 'emoji']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image:
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None


class StudentProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    avatar = AvatarSerializer(read_only=True)

    class Meta:
        model = StudentProfile
        fields = ['username', 'email', 'class_level', 'phone', 'avatar']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    class_level = serializers.ChoiceField(choices=[9, 10, 11, 12], write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'class_level']

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is already taken.")
        return value

    def create(self, validated_data):
        class_level = validated_data.pop('class_level')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )
        default_avatar = Avatar.objects.filter(is_active=True).order_by('order', 'id').first()
        StudentProfile.objects.create(user=user, class_level=class_level, avatar=default_avatar)
        return user


# ------------------------------------------------------------------- notes

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'class_level', 'board']


class ChapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chapter
        fields = ['id', 'title', 'order']


class NoteSerializer(serializers.ModelSerializer):
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = ['id', 'title', 'resource_type', 'pdf_url', 'uploaded_at']

    def get_pdf_url(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.pdf_file.url) if request else obj.pdf_file.url


class PYQPaperSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = PYQPaper
        fields = ['id', 'subject_name', 'class_level', 'year', 'set_label', 'pdf_url']

    def get_pdf_url(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.pdf_file.url) if request else obj.pdf_file.url


# ---------------------------------------------------------------- mocktest

class TestListSerializer(serializers.ModelSerializer):
    """One row per chapter's overall question bank (before slicing into Test 1, 2, 3...)."""
    total_questions = serializers.ReadOnlyField()
    num_slices = serializers.ReadOnlyField()

    class Meta:
        model = Test
        fields = ['id', 'title', 'duration_minutes', 'total_questions', 'num_slices']


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'text']  # is_correct deliberately left out - never reveal answers up front


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'choices']  # no explanation here either - only after submit


class SubmitAnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    choice_id = serializers.IntegerField(allow_null=True)
