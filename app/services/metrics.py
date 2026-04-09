from datetime import timedelta
from django.utils import timezone
from django.db.models import Count
from app.models import Show, SiteMetric

def calculate_missing_kp_metric():
    qs = Show.objects.filter(
        kinopoisk_url__isnull=False,
        ext_rating__isnull=True
    ).exclude(kinopoisk_url='')

    stats = qs.values('type').annotate(
        total_missing=Count('id')
    ).order_by('-total_missing')

    data = [
        {'name': item['type'] or 'Unknown', 'value': item['total_missing']} 
        for item in stats
    ]
    return data

def get_or_update_metric(key: str, calc_func) -> dict:
    now = timezone.now()
    
    latest = SiteMetric.objects.filter(key=key).order_by('-created_at').first()
    
    if not latest or (now - latest.created_at).total_seconds() > 300:
        new_data = calc_func()
        latest = SiteMetric.objects.create(key=key, data=new_data)

    yesterday_cutoff = now - timedelta(days=1)
    yesterday = SiteMetric.objects.filter(
        key=key, 
        created_at__lte=yesterday_cutoff
    ).order_by('-created_at').first()

    week_cutoff = now - timedelta(days=7)
    week_ago = SiteMetric.objects.filter(
        key=key, 
        created_at__lte=week_cutoff
    ).order_by('-created_at').first()

    return {
        'now': latest.data if latest else [],
        'yesterday': yesterday.data if yesterday else [],
        'week_ago': week_ago.data if week_ago else [],
    }