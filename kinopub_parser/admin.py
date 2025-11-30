from django.contrib import admin
from django.shortcuts import render
from django.urls import path

from app.dashboard import dashboard_callback


class CustomAdminSite(admin.AdminSite):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', self.admin_view(self.custom_index), name='index'),
        ]
        return custom_urls + urls

    def custom_index(self, request, extra_context=None):
        context = self.each_context(request)
        context = dashboard_callback(request, context)
        return render(request, 'admin/index.html', context)


admin_site = CustomAdminSite(name='admin')
