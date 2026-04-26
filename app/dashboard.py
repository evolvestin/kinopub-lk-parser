import json

from app.services.stats_calculator import generate_global_stats


def dashboard_callback(context):
    global_stats = generate_global_stats()
    context['global_stats_json'] = json.dumps(global_stats)
    return context
