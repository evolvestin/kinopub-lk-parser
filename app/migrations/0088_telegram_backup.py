import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0087_showcrew_canonical_person_index'),
    ]

    operations = [
        migrations.CreateModel(
            name='TelegramBackup',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('source_filename', models.CharField(max_length=255)),
                ('size_bytes', models.PositiveBigIntegerField()),
                ('sha256', models.CharField(max_length=64)),
                ('part_count', models.PositiveIntegerField(default=0)),
                ('manifest_message_id', models.BigIntegerField(blank=True, null=True)),
                ('manifest_file_id', models.CharField(blank=True, max_length=512)),
                ('status', models.CharField(choices=[('uploading', 'Загружается'), ('uploaded', 'Загружен'), ('failed', 'Ошибка')], default='uploading', max_length=16)),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Telegram backup',
                'verbose_name_plural': 'Telegram backups',
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='TelegramBackupPart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('part_number', models.PositiveIntegerField()),
                ('filename', models.CharField(max_length=255)),
                ('size_bytes', models.PositiveBigIntegerField()),
                ('sha256', models.CharField(max_length=64)),
                ('message_id', models.BigIntegerField()),
                ('file_id', models.CharField(max_length=512)),
                ('file_unique_id', models.CharField(blank=True, max_length=255)),
                ('backup', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parts', to='app.telegrambackup')),
            ],
            options={
                'verbose_name': 'Telegram backup part',
                'verbose_name_plural': 'Telegram backup parts',
                'ordering': ('part_number',),
            },
        ),
        migrations.AddConstraint(
            model_name='telegrambackuppart',
            constraint=models.UniqueConstraint(fields=('backup', 'part_number'), name='unique_telegram_backup_part'),
        ),
    ]
