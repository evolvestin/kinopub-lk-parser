from django.contrib.postgres.fields import ArrayField
from django.db import migrations, models


CREATE_DIRTY_TRIGGERS = """
CREATE OR REPLACE FUNCTION app_mark_show_metric_summary_dirty()
RETURNS trigger AS $$
BEGIN
    IF OLD.type IS DISTINCT FROM NEW.type
       OR OLD.kinopoisk_url IS DISTINCT FROM NEW.kinopoisk_url THEN
        INSERT INTO app_personmetricsummarydirty (canonical_person_id)
        SELECT DISTINCT COALESCE(sc.canonical_person_id, p.master_person_id, p.id)
        FROM app_showcrew AS sc
        JOIN app_person AS p ON p.id = sc.person_id
        WHERE sc.show_id = NEW.id
        ON CONFLICT DO NOTHING;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS app_show_metric_summary_dirty ON app_show;
CREATE TRIGGER app_show_metric_summary_dirty
AFTER UPDATE OF type, kinopoisk_url ON app_show
FOR EACH ROW EXECUTE FUNCTION app_mark_show_metric_summary_dirty();

CREATE OR REPLACE FUNCTION app_mark_external_rating_summary_dirty()
RETURNS trigger AS $$
DECLARE
    old_show_id bigint;
    new_show_id bigint;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        old_show_id := OLD.show_id;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        new_show_id := NEW.show_id;
    END IF;

    INSERT INTO app_personmetricsummarydirty (canonical_person_id)
    SELECT DISTINCT COALESCE(sc.canonical_person_id, p.master_person_id, p.id)
    FROM app_showcrew AS sc
    JOIN app_person AS p ON p.id = sc.person_id
    WHERE sc.show_id = old_show_id OR sc.show_id = new_show_id
    ON CONFLICT DO NOTHING;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER app_externalrating_metric_summary_dirty
AFTER INSERT OR DELETE OR UPDATE OF show_id ON app_externalrating
FOR EACH ROW EXECUTE FUNCTION app_mark_external_rating_summary_dirty();
"""


DROP_DIRTY_TRIGGERS = """
DROP TRIGGER IF EXISTS app_externalrating_metric_summary_dirty ON app_externalrating;
DROP FUNCTION IF EXISTS app_mark_external_rating_summary_dirty();

CREATE OR REPLACE FUNCTION app_mark_show_metric_summary_dirty()
RETURNS trigger AS $$
BEGIN
    IF OLD.type IS DISTINCT FROM NEW.type THEN
        INSERT INTO app_personmetricsummarydirty (canonical_person_id)
        SELECT DISTINCT COALESCE(sc.canonical_person_id, p.master_person_id, p.id)
        FROM app_showcrew AS sc
        JOIN app_person AS p ON p.id = sc.person_id
        WHERE sc.show_id = NEW.id
        ON CONFLICT DO NOTHING;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS app_show_metric_summary_dirty ON app_show;
CREATE TRIGGER app_show_metric_summary_dirty
AFTER UPDATE OF type ON app_show
FOR EACH ROW EXECUTE FUNCTION app_mark_show_metric_summary_dirty();
"""


def mark_summary_not_ready(apps, schema_editor):
    state_model = apps.get_model('app', 'PersonMetricSummaryState')
    state_model.objects.filter(id=1).update(ready=False, rebuilt_at=None)


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0103_person_metrics_summary'),
    ]

    operations = [
        migrations.AddField(
            model_name='personmetricsummary',
            name='kp_waiting_person_ids',
            field=ArrayField(base_field=models.BigIntegerField(), blank=True, default=list, size=None),
        ),
        migrations.RunPython(mark_summary_not_ready, migrations.RunPython.noop),
        migrations.RunSQL(CREATE_DIRTY_TRIGGERS, DROP_DIRTY_TRIGGERS),
    ]
