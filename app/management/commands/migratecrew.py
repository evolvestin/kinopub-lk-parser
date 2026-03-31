from app.management.base import LoggableBaseCommand
from app.models import Show, ShowCrew


class Command(LoggableBaseCommand):
    help = 'Migrates actors and directors from legacy M2M fields to ShowCrew table.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting crew migration...'))

        actor_relations = Show.actors.through.objects.all().iterator(chunk_size=5000)
        actor_crew = (
            ShowCrew(
                show_id=rel.show_id,
                person_id=rel.person_id,
                profession='Актер',
                en_profession='Actor',
            )
            for rel in actor_relations
        )

        ShowCrew.objects.bulk_create(
            actor_crew, ignore_conflicts=True, batch_size=2000
        )
        self.stdout.write(self.style.SUCCESS('Processed actors batch. Inserted/Ignored records.'))

        director_relations = Show.directors.through.objects.all().iterator(chunk_size=5000)
        director_crew = (
            ShowCrew(
                show_id=rel.show_id,
                person_id=rel.person_id,
                profession='Режиссер',
                en_profession='Director',
            )
            for rel in director_relations
        )

        ShowCrew.objects.bulk_create(
            director_crew, ignore_conflicts=True, batch_size=2000
        )
        self.stdout.write(
            self.style.SUCCESS('Processed directors batch. Inserted/Ignored records.')
        )

        self.stdout.write(self.style.SUCCESS('Crew migration completed successfully.'))
