from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0110_person_photo_member_page_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserStatsAggregate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope', models.CharField(choices=[('personal', 'Personal'), ('group', 'Group')], max_length=12)),
                ('year', models.IntegerField(blank=True, null=True)),
                ('aggregates', models.JSONField(default=dict)),
                ('details', models.JSONField(default=dict)),
                ('generated_at', models.DateTimeField(auto_now=True)),
                ('ready', models.BooleanField(default=False)),
                ('dirty', models.BooleanField(default=False)),
                ('dirty_version', models.PositiveBigIntegerField(default=0)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stats_aggregates', to='app.viewuser')),
            ],
        ),
        migrations.AddConstraint(
            model_name='userstatsaggregate',
            constraint=models.UniqueConstraint(fields=('user', 'scope', 'year'), name='uniq_user_stats_aggregate_period', nulls_distinct=False),
        ),
    ]
