from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('permissions', '0008_remove_parent_role_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='NurseRoomEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('student_name', models.CharField(max_length=100)),
                ('level', models.CharField(choices=[('o_level', 'O LEVEL'), ('a_level', 'A LEVEL')], max_length=20)),
                ('student_class', models.CharField(max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('nurse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='nurse_room_entries', to=settings.AUTH_USER_MODEL)),
                ('shared_list', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='nurse_room_entries', to='permissions.sharedstudentlist')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
