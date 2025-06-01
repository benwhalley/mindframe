# checks.py
from django.apps import apps
from django.core.checks import Warning, register

from llmtools.models import LLM, LLMCredentials
from mindframe.settings import RESERVED_USERNAMES


@register()
def check_required_defaults(app_configs, **kwargs):
    CustomUser = apps.get_model("mindframe", "CustomUser")
    for i in RESERVED_USERNAMES:
        if not CustomUser.objects.filter(username="system").exists():
            return [
                Warning(
                    f'Default user "{i}" missing.',
                    hint="Run `manage.py ensure_defaults` to restore it.",
                    id="mindframe.W001",
                )
            ]
    return []


@register()
def check_default_intervention(app_configs, **kwargs):
    BotInterface = apps.get_model("mindframe", "BotInterface")
    N = BotInterface.objects.all().count()
    if N < 0:
        return [
            Warning(
                f"No BotInterfaces found.",
                hint="Create one to use a bot.",
                id="mindframe.W002",
            )
        ]
    return []


@register()
def check_llm_config(app_configs, **kwargs):
    LLM = apps.get_model("llmtools", "LLM")
    if LLM.objects.filter(pk=1).count() == 0:
        return [
            Warning(
                f"No default LLM found.",
                hint="Use ensure_defaults to create one.",
                id="mindframe.W003",
            )
        ]
    if LLMCredentials.objects.filter(pk=1).count() == 0:
        return [
            Warning(
                f"No default LLMCredentials found.",
                hint="Use ensure_defaults to create one.",
                id="mindframe.W003",
            )
        ]
    return []


@register()
def check_usage_plan_exists(app_configs, **kwargs):
    UsagePlan = apps.get_model("mindframe", "UsagePlan")
    if not UsagePlan.objects.filter(label="Default UsagePlan").exists():
        return [
            Warning(
                "No default UsagePlan found.",
                hint="Run `manage.py ensure_defaults` to create one.",
                id="mindframe.W004",
            )
        ]
    return []
