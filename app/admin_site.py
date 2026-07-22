import json
import shlex
import subprocess
import sys
from argparse import _StoreFalseAction, _StoreTrueAction

from django.conf import settings
from django.contrib import admin, messages
from django.core.management import get_commands, load_command_class
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse

from app.dashboard import dashboard_callback
from app.models import TaskRun
from app.tasks import run_admin_command
from app.utils import get_scheduled_tasks_info
from kinopub_parser import celery_app
from shared.constants import DATETIME_FORMAT, SHOW_TYPE_DISPLAY_RU, SHOW_TYPE_MAPPING


class CustomAdminSite(admin.AdminSite):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', self.admin_view(self.custom_index), name='index'),
            path('tasks/', self.admin_view(self.task_control_view), name='task_control'),
        ]
        return custom_urls + urls

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request)

        model_map = {}
        for app in app_list:
            for model in app['models']:
                model_map[model['object_name']] = model

        # Определение категорий
        categories = [
            {
                'name': '⚙️ Система и Задачи',
                'app_label': 'system',
                'models': [
                    {
                        'name': 'Контроль задач',
                        'object_name': 'task_control',
                        'admin_url': reverse('admin:task_control'),
                        'view_only': True,
                    },
                    'TaskRun',
                    'SiteMetric',
                    'SharedStat',
                ],
            },
            {
                'name': '🎬 Каталог контента',
                'app_label': 'catalog',
                'models': [
                    'Show',
                    'ExternalRating',
                    'Person',
                    'RejectedPersonPhoto',
                    'ShowCrew',
                    'ShowDuration',
                    'Country',
                    'Genre',
                ],
            },
            {
                'name': '👥 Пользователи и Активность',
                'app_label': 'activity',
                'models': [
                    'ViewUser',
                    'ViewUserGroup',
                    'ViewHistory',
                    'UserRating',
                    'CasinoSpin',
                    'MutedShowNotification',
                ],
            },
            {
                'name': '🔖 Избранное (Wishlists)',
                'app_label': 'wishlists',
                'models': ['WishlistFolder', 'WishlistItem'],
            },
            {
                'name': '🛡 Доступ и Логи',
                'app_label': 'logs',
                'models': ['User', 'Group', 'Code', 'LogEntry', 'TelegramLog'],
            },
        ]

        new_app_list = []
        for cat in categories:
            category_models = []
            for m_ref in cat['models']:
                if isinstance(m_ref, dict):
                    category_models.append(m_ref)
                elif m_ref in model_map:
                    category_models.append(model_map[m_ref])

            if category_models:
                new_app_list.append(
                    {
                        'name': cat['name'],
                        'app_label': cat['app_label'],
                        'app_url': '',
                        'has_module_perms': True,
                        'models': category_models,
                    }
                )

        if app_label:
            return [app for app in new_app_list if app['app_label'] == app_label]

        return new_app_list

    def custom_index(self, request, extra_context=None):
        app_list = self.get_app_list(request)

        context = {
            **self.each_context(request),
            'title': self.index_title,
            'app_list': app_list,
            **(extra_context or {}),
        }
        context = dashboard_callback(context)
        return render(request, 'admin/index.html', context)

    def _get_app_commands_details(self):
        commands_dict = {}
        sys_commands = get_commands()

        ignored_args = {
            '-v',
            '--verbosity',
            '--settings',
            '--pythonpath',
            '--traceback',
            '--no-color',
            '--force-color',
            '--skip-checks',
            '--version',
            '-h',
            '--help',
        }

        hidden_commands = [
            'healthcheck',
            'runemaillistener',
            'runparserlocal',
            'createsuperuserifneeded',
            'restorebackup',
            'runhealthdaemon',
        ]

        target_commands = [
            name
            for name, app in sys_commands.items()
            if app == 'app' and name not in hidden_commands
        ]

        for name in target_commands:
            try:
                cmd_class = load_command_class('app', name)
                parser = cmd_class.create_parser('manage.py', name)

                args_details = []
                for action in parser._actions:
                    is_ignored = any(opt in ignored_args for opt in action.option_strings)
                    if is_ignored:
                        continue

                    arg_info = {
                        'dest': action.dest,
                        'help': action.help,
                        'required': action.required,
                        'default': action.default if action.default is not None else '',
                        'type': 'text',
                    }

                    if not action.option_strings:
                        arg_info['is_positional'] = True
                        arg_info['name'] = action.dest
                    else:
                        arg_info['is_positional'] = False
                        long_opt = next(
                            (o for o in action.option_strings if o.startswith('--')),
                            action.option_strings[0],
                        )
                        arg_info['name'] = long_opt

                        if isinstance(action, (_StoreTrueAction, _StoreFalseAction)):
                            arg_info['type'] = 'checkbox'
                        elif action.type is int:
                            arg_info['type'] = 'number'

                        if action.dest == 'type':
                            arg_info['type'] = 'select'
                            unique_types = sorted(list(set(SHOW_TYPE_MAPPING.values())))
                            arg_info['choices'] = [
                                {'value': t, 'label': SHOW_TYPE_DISPLAY_RU.get(t, t)}
                                for t in unique_types
                            ]

                    args_details.append(arg_info)

                commands_dict[name] = {
                    'help': cmd_class.help or 'Описание отсутствует',
                    'args': args_details,
                }
            except Exception:
                continue

        return commands_dict

    def task_control_view(self, request):
        commands_info = self._get_app_commands_details()

        if (
            request.method == 'POST'
            and not request.headers.get('x-requested-with') == 'XMLHttpRequest'
        ):
            if 'stop_task_id' in request.POST:
                try:
                    task_to_stop = TaskRun.objects.get(
                        id=request.POST.get('stop_task_id'), status='RUNNING'
                    )
                    task_to_stop.status = 'STOPPED'
                    task_to_stop.save()

                    messages.warning(
                        request, f'Сигнал остановки отправлен задаче {task_to_stop.command}.'
                    )

                except TaskRun.DoesNotExist:
                    messages.error(request, 'Задача не найдена или уже завершена.')
                return redirect('admin:task_control')

            command_name = request.POST.get('command')

            if command_name and command_name in commands_info:
                running_tasks = TaskRun.objects.filter(command=command_name, status='RUNNING')
                for old_task in running_tasks:
                    if old_task.celery_task_id:
                        celery_app.control.revoke(
                            old_task.celery_task_id, terminate=True, signal='SIGINT'
                        )
                    old_task.status = 'STOPPED'
                    old_task.save()

                if running_tasks.exists():
                    messages.warning(
                        request,
                        f"Предыдущие активные задачи '{command_name}'"
                        f' были принудительно остановлены.',
                    )

                cmd_config = commands_info[command_name]
                args_list = []

                for arg in cmd_config['args']:
                    form_key = f'arg_{arg["dest"]}'
                    value = request.POST.get(form_key)

                    if arg['is_positional']:
                        if value:
                            args_list.append(json.dumps(value))
                    else:
                        if arg['type'] == 'checkbox':
                            if value == 'on':
                                args_list.append(arg['name'])
                        elif value:
                            args_list.append(f'{arg["name"]} {json.dumps(value)}')

                arguments_str = ' '.join(args_list)

                if command_name == 'resetlocks':
                    task_run = TaskRun.objects.create(
                        command=command_name, arguments=arguments_str, status='RUNNING'
                    )

                    cmd = [sys.executable, 'manage.py', command_name]
                    if arguments_str:
                        cmd.extend(shlex.split(arguments_str))

                    try:
                        result = subprocess.run(
                            cmd, capture_output=True, text=True, cwd=settings.BASE_DIR, timeout=60
                        )
                        task_run.output = (result.stdout + '\n' + result.stderr).strip()
                        if result.returncode == 0:
                            task_run.status = 'SUCCESS'
                        else:
                            task_run.status = 'FAILURE'
                            task_run.error_message = f'Exit code: {result.returncode}'
                    except Exception as e:
                        task_run.status = 'FAILURE'
                        task_run.error_message = str(e)

                    task_run.save()
                    messages.success(
                        request,
                        f'Команда {command_name} выполнена принудительно (в обход очереди).',
                    )
                    return redirect('admin:task_control')

                TaskRun.objects.create(command=command_name, arguments=arguments_str)
                last_run = TaskRun.objects.order_by('-id').first()
                if last_run:
                    run_admin_command.delay(last_run.id)

                messages.success(request, f'Команда {command_name} поставлена в очередь.')
                return redirect('admin:task_control')

        # Используем общую функцию для получения расписания
        scheduled_tasks = get_scheduled_tasks_info()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            recent_tasks = TaskRun.objects.all()[:10]

            return JsonResponse(
                {
                    'schedule': [
                        {
                            'name': t['name'],
                            'next_run_display': t['next_run_display'],
                            'seconds_left': t['seconds_left'],
                        }
                        for t in scheduled_tasks
                    ],
                    'history': [
                        {
                            'id': t.id,
                            'created_at': t.created_at.strftime(DATETIME_FORMAT),
                            'command': t.command,
                            'arguments': t.arguments or '-',
                            'status': t.status,
                            'status_display': t.get_status_display(),
                        }
                        for t in recent_tasks
                    ],
                }
            )

        recent_tasks = TaskRun.objects.all()[:10]

        context = self.each_context(request)
        context.update(
            {
                'commands_json': json.dumps(commands_info),
                'available_commands_list': commands_info.keys(),
                'recent_tasks': recent_tasks,
                'scheduled_tasks': scheduled_tasks,
                'title': 'Управление задачами',
                'websocket_url': settings.WEBSOCKET_URL,
                'websocket_port': settings.WEBSOCKET_PORT,
            }
        )
        return render(request, 'admin/task_control.html', context)


admin_site = CustomAdminSite(name='admin')
