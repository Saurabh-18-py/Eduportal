from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import StudentProfile, Avatar, Message
from notes.models import Subject, Chapter, Note, PYQPaper
from mocktest.models import Test, Question, Choice, TestAttempt
from doubtsolver.models import DoubtMessage


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
        from django.contrib.auth.models import User as UserModel
        from accounts.models import Message

        class_level = validated_data.pop('class_level')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )
        default_avatar = Avatar.objects.filter(is_active=True).order_by('order', 'id').first()
        StudentProfile.objects.create(user=user, class_level=class_level, avatar=default_avatar)

        admin_user = UserModel.objects.filter(is_superuser=True).order_by('id').first()
        if admin_user and admin_user != user:
            Message.objects.create(
                sender=admin_user,
                recipient=user,
                text=(
                    f"Welcome, {user.username} 🎉 You're in the right spot — "
                    f"studying's about to hit different. I'm Saurabh. "
                    f"Hit me up anytime 💯"
                ),
            )
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


class TestAttemptSerializer(serializers.ModelSerializer):
    test_title = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source='test.subject.name', read_only=True)

    class Meta:
        model = TestAttempt
        fields = ['id', 'test_title', 'subject_name', 'score', 'total', 'started_at', 'submitted_at']

    def get_test_title(self, obj):
        return obj.test.title.replace(' - Practice Test', '')


# ------------------------------------------------------------ doubt solver

class DoubtMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoubtMessage
        fields = ['id', 'role', 'content', 'created_at']


class AskDoubtSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000)


# ---------------------------------------------------------------- messages

class MessageSerializer(serializers.ModelSerializer):
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'text', 'created_at', 'is_read', 'is_mine']

    def get_is_mine(self, obj):
        request = self.context.get('request')
        return bool(request and obj.sender_id == request.user.id)


class SendMessageSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=4000)


# ---------------------------------------------------------------- profile

class UpdateProfileSerializer(serializers.ModelSerializer):
    avatar_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = StudentProfile
        fields = ['phone', 'avatar_id']

    def update(self, instance, validated_data):
        avatar_id = validated_data.pop('avatar_id', 'unset')
        if avatar_id != 'unset':
            if avatar_id is None:
                instance.avatar = None
            else:
                instance.avatar = Avatar.objects.filter(id=avatar_id, is_active=True).first()
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])


# MATH_CLEAN_HOOK: LaTeX jaisa math app ke liye saaf karo
from .mathclean import clean_math as _clean_math


def _hook_clean(cls, field_names):
    orig = cls.to_representation

    def to_representation(self, instance):
        data = orig(self, instance)
        for f in field_names:
            if f in data:
                data[f] = _clean_math(data[f])
        return data

    cls.to_representation = to_representation


_hook_clean(ChoiceSerializer, ['text'])
_hook_clean(QuestionSerializer, ['text', 'explanation'])
