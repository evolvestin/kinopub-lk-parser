from django.test import TestCase

from app.models import Show, ShowPoster
from app.services.show_identity import record_kinopub_source


class KinopubSourcePosterTests(TestCase):
    def test_repeated_variant_updates_existing_slot_instead_of_violating_constraint(self):
        show = Show.objects.create(
            title='3D copy',
            original_title='3D copy',
            type='Movie',
            is_3d=True,
        )
        existing = ShowPoster.objects.create(
            show=show,
            source=ShowPoster.SOURCE_KINOPUB,
            external_id=100,
            variant='3d',
            url='https://example.test/100.jpg',
        )

        result = record_kinopub_source(show, 200, is_3d=True)

        existing.refresh_from_db()
        self.assertEqual(result.pk, existing.pk)
        self.assertEqual(existing.external_id, 200)
        self.assertEqual(
            ShowPoster.objects.filter(
                show=show,
                source=ShowPoster.SOURCE_KINOPUB,
                variant='3d',
            ).count(),
            1,
        )

    def test_source_id_owned_by_another_show_is_not_reassigned(self):
        owner_show = Show.objects.create(
            title='Owner', original_title='Owner', type='Movie'
        )
        incoming_show = Show.objects.create(
            title='Incoming', original_title='Incoming', type='Movie'
        )
        owner = ShowPoster.objects.create(
            show=owner_show,
            source=ShowPoster.SOURCE_KINOPUB,
            external_id=300,
            variant='main',
            url='https://example.test/300.jpg',
        )

        result = record_kinopub_source(incoming_show, 300)

        self.assertEqual(result.pk, owner.pk)
        self.assertFalse(ShowPoster.objects.filter(show=incoming_show).exists())
