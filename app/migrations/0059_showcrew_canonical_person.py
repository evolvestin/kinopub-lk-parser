import django.db.models.deletion
from django.db import migrations, models

CREATE_TRIGGERS = """
CREATE OR REPLACE FUNCTION app_set_showcrew_canonical_person()
RETURNS trigger AS $$
BEGIN
    SELECT COALESCE(master_person_id, id)
      INTO NEW.canonical_person_id
      FROM app_person
     WHERE id = NEW.person_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER app_showcrew_canonical_person_trigger
BEFORE INSERT OR UPDATE OF person_id ON app_showcrew
FOR EACH ROW EXECUTE FUNCTION app_set_showcrew_canonical_person();

CREATE OR REPLACE FUNCTION app_sync_showcrew_canonical_person()
RETURNS trigger AS $$
BEGIN
    IF OLD.master_person_id IS DISTINCT FROM NEW.master_person_id THEN
        UPDATE app_showcrew
           SET canonical_person_id = COALESCE(NEW.master_person_id, NEW.id)
         WHERE person_id = NEW.id OR canonical_person_id = OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER app_person_canonical_person_trigger
AFTER UPDATE OF master_person_id ON app_person
FOR EACH ROW EXECUTE FUNCTION app_sync_showcrew_canonical_person();
"""

DROP_TRIGGERS = """
DROP TRIGGER IF EXISTS app_showcrew_canonical_person_trigger ON app_showcrew;
DROP TRIGGER IF EXISTS app_person_canonical_person_trigger ON app_person;
DROP FUNCTION IF EXISTS app_set_showcrew_canonical_person();
DROP FUNCTION IF EXISTS app_sync_showcrew_canonical_person();
"""


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('app', '0058_showcrew_profession_person_indexes'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    'ALTER TABLE app_showcrew ADD COLUMN '
                    'IF NOT EXISTS canonical_person_id bigint NULL',
                    migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='showcrew',
                    name='canonical_person',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='canonical_crew_rows',
                        to='app.person',
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name='show',
            name='crew',
            field=models.ManyToManyField(
                blank=True,
                related_name='shows_as_crew',
                through='app.ShowCrew',
                through_fields=('show', 'person'),
                to='app.person',
            ),
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name='showcrew',
                    index=models.Index(
                        fields=['profession', 'canonical_person'], name='idx_crew_prof_canonical'
                    ),
                ),
                migrations.AddIndex(
                    model_name='showcrew',
                    index=models.Index(
                        fields=['en_profession', 'canonical_person'],
                        name='idx_crew_enprof_canonical',
                    ),
                ),
                migrations.AddIndex(
                    model_name='showcrew',
                    index=models.Index(
                        fields=['show', 'canonical_person'], name='idx_crew_show_canonical'
                    ),
                ),
            ],
        ),
        migrations.RunSQL(CREATE_TRIGGERS, DROP_TRIGGERS),
    ]
