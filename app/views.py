from django.shortcuts import render

from app.dashboard import dashboard_callback


def index(request):
    context = dashboard_callback(request, {})
    return render(request, 'index.html', context)