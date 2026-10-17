import cloudinary_storage.storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_studentprofile_doubt_limit_per_day'),
    ]

    operations = [
        migrations.AddField(
            model_name='adminprofile',
            name='video',
            field=models.FileField(blank=True, help_text='Intro video shown on your profile', max_length=255, null=True, storage=cloudinary_storage.storage.VideoMediaCloudinaryStorage(), upload_to='admin_videos/'),
        ),
        migrations.AddField(
            model_name='adminprofile',
            name='video_link',
            field=models.URLField(blank=True, default='', help_text='Or paste a YouTube / video link', max_length=500),
        ),
    ]
