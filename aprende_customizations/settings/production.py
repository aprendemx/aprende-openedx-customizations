"""
Settings de producción: hereda de common y permite sobrescribir desde
AUTH_TOKENS / ENV_TOKENS si en algún momento hiciera falta.
"""

from aprende_customizations.settings.common import plugin_settings as common_settings


def plugin_settings(settings):
    common_settings(settings)

    for name in (
        "APRENDE_CATALOG_NEWEST_FIRST",
        "APRENDE_FIX_EMPTY_HTML_MEDIA",
        "APRENDE_FIX_LINKEDIN_URL",
    ):
        if hasattr(settings, "ENV_TOKENS") and name in settings.ENV_TOKENS:
            setattr(settings, name, settings.ENV_TOKENS[name])
