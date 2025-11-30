import json
from django.contrib import admin
from django.conf import settings
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.core.management import get_commands, load_command_class
from django.http import JsonResponse
from argparse import _StoreTrueAction, _StoreFalseAction

from app.dashboard import dashboard_callback
from app.models import TaskRun, LogEntry
from app.tasks import run_admin_command
from app.constants import SHOW_TYPE_MAPPING

class CustomAdminSite(admin.AdminSite):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', self.admin_view(self.custom_index), name='index'),
            path('tasks/', self.admin_view(self.task_control_view), name='task_control'),
        ]
        return custom_urls + urls

    def custom_index(self, request, extra_context=None):
        app_list = self.get_app_list(request)

        app_list.insert(0, {
            'name': 'System',
            'app_label': 'system',
            'models': [{
                'name': 'Task Control',
                'object_name': 'task_control',
                'admin_url': reverse('admin:task_control'),
                'add_url': None,
                'view_only': True,
            }],
        })

        context = {
            **self.each_context(request),
            'title': self.index_title,
            'app_list': app_list,
            **(extra_context or {}),
        }
        context = dashboard_callback(request, context)
        return render(request, 'admin/index.html', context)

    def _get_app_commands_details(self):
        """Инспектирует команды приложения app и возвращает их структуру аргументов."""       
        commands_dict = {}
        sys_commands = get_commands()
        
        # Стандартные аргументы Django, которые мы хотим скрыть из UI
        ignored_args = {
            '-v', '--verbosity', '--settings', '--pythonpath', '--traceback', 
            '--no-color', '--force-color', '--skip-checks', '--version', '-h', '--help'
        }

        # Команды, которые нужно исключить из списка
        hidden_commands = [
            'healthcheck',
            'runemail_listener',
            'runparserlocal',
        ]

        target_commands = [
            name for name, app in sys_commands.items() 
            if app == 'app' and name not in hidden_commands
        ]

        for name in target_commands:
            try:
                cmd_class = load_command_class('app', name)
                # Создаем парсер, чтобы извлечь аргументы
                parser = cmd_class.create_parser('manage.py', name)
                
                args_details = []
                for action in parser._actions:
                    # Пропускаем стандартные аргументы
                    is_ignored = any(opt in ignored_args for opt in action.option_strings)
                    if is_ignored:
                        continue
                        
                    arg_info = {
                        'dest': action.dest,
                        'help': action.help,
                        'required': action.required,
                        'default': action.default if action.default is not None else '',
                        'type': 'text' # default
                    }

                    # Определяем позиционный это аргумент или опциональный (флаг)
                    if not action.option_strings:
                        arg_info['is_positional'] = True
                        arg_info['name'] = action.dest
                    else:
                        arg_info['is_positional'] = False
                        long_opt = next((o for o in action.option_strings if o.startswith('--')), action.option_strings[0])
                        arg_info['name'] = long_opt
                        
                        if isinstance(action, (_StoreTrueAction, _StoreFalseAction)):
                            arg_info['type'] = 'checkbox'
                        elif action.type == int:
                            arg_info['type'] = 'number'

                        if name == 'updatedetails' and action.dest == 'type':
                            arg_info['type'] = 'select'
                            unique_types = sorted(list(set(SHOW_TYPE_MAPPING.values())))
                            arg_info['choices'] = [{'value': t, 'label': t} for t in unique_types]

                    args_details.append(arg_info)

                commands_dict[name] = {
                    'help': cmd_class.help or "Описание отсутствует",
                    'args': args_details
                }
            except Exception:
                continue
                
        return commands_dict

    def task_control_view(self, request):
        commands_info = self._get_app_commands_details()
        
        if request.method == 'POST' and not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            command_name = request.POST.get('command')
            
            if command_name and command_name in commands_info:
                # Собираем строку аргументов из POST данных
                cmd_config = commands_info[command_name]
                args_list = []

                for arg in cmd_config['args']:
                    form_key = f"arg_{arg['dest']}"
                    value = request.POST.get(form_key)

                    if arg['is_positional']:
                        if value:
                            args_list.append(str(value))
                    else:
                        # Опциональные аргументы (флаги)
                        if arg['type'] == 'checkbox':
                            # Если чекбокс отмечен, добавляем флаг
                            if value == 'on':
                                args_list.append(arg['name'])
                        elif value:
                             # --account main
                            args_list.append(f"{arg['name']} {value}")

                arguments_str = " ".join(args_list)

                TaskRun.objects.create(
                    command=command_name,
                    arguments=arguments_str
                )
                last_run = TaskRun.objects.order_by('-id').first()
                if last_run:
                    run_admin_command.delay(last_run.id)

                messages.success(request, f'Команда {command_name} поставлена в очередь.')
                return redirect('admin:task_control')

        # Обработка расписания (для отображения таблицы Cron)
        scheduled_tasks = []
        now = timezone.now()
        if hasattr(settings, 'CELERY_BEAT_SCHEDULE'):
            for name, config in settings.CELERY_BEAT_SCHEDULE.items():
                schedule_obj = config.get('schedule')
                next_run_dt = now 
                try:
                    if isinstance(schedule_obj, (int, float)):
                        interval = float(schedule_obj)
                        next_run_dt = now + timedelta(seconds=interval - (now.timestamp() % interval))
                    elif isinstance(schedule_obj, timedelta):
                        interval = schedule_obj.total_seconds()
                        next_run_dt = now + timedelta(seconds=interval - (now.timestamp() % interval))
                    elif hasattr(schedule_obj, 'is_due'):
                        is_due, next_seconds = schedule_obj.is_due(now)
                        next_run_dt = now + timedelta(seconds=next_seconds)
                except Exception:
                    pass
                
                seconds_left = (next_run_dt - now).total_seconds()
                scheduled_tasks.append({
                    'name': name,
                    'next_run_dt': next_run_dt,
                    'seconds_left': seconds_left,
                    'next_run_display': next_run_dt.strftime('%Y-%m-%d %H:%M:%S')
                })

        scheduled_tasks.sort(key=lambda x: x['seconds_left'])

        # AJAX запрос для обновления таблиц
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            recent_tasks = TaskRun.objects.all()[:10]
            logs_qs = LogEntry.objects.all()[:30]
            logs_data = [{
                'created_at': l.created_at.strftime('%H:%M:%S'),
                'level': l.level,
                'module': l.module,
                'message': l.message
            } for l in logs_qs]
            logs_data.reverse()

            return JsonResponse({
                'schedule': [
                    {'name': t['name'], 'next_run_display': t['next_run_display'], 'seconds_left': t['seconds_left']} 
                    for t in scheduled_tasks
                ],
                'history': [
                    {
                        'created_at': t.created_at.strftime('%d.%m.%Y %H:%M:%S'),
                        'command': t.command,
                        'arguments': t.arguments or "-",
                        'status': t.status,
                        'status_display': t.get_status_display()
                    } for t in recent_tasks
                ],
                'logs': logs_data
            })

        recent_tasks = TaskRun.objects.all()[:10]
        
        context = self.each_context(request)
        context.update({
            'commands_json': json.dumps(commands_info), # Передаем структуру команд в JS
            'available_commands_list': commands_info.keys(),
            'recent_tasks': recent_tasks,
            'scheduled_tasks': scheduled_tasks,
            'title': 'Управление задачами'
        })
        return render(request, 'admin/task_control.html', context)

admin_site = CustomAdminSite(name='admin')