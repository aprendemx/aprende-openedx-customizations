"""
Sustitución de funciones de edx-platform.

Reemplaza las 17 líneas de `courseware/courses.py` y `courseware/utils.py` más
la corrección de `linked_in_url` en `certificates/views/webview.py`.

--------------------------------------------------------------------------
POR QUÉ HAY QUE PARCHEAR VARIOS MÓDULOS
--------------------------------------------------------------------------
Los llamadores usan `from ... import nombre`, lo que copia la referencia a la
función al namespace del llamador en tiempo de import. Reemplazar el atributo
solo en el módulo de origen NO afecta a quien ya tiene su propia referencia.

Por eso cada parche declara la lista completa de módulos donde la función
aparece como atributo.

**Esta lista debe revisarse en cada actualización de Open edX.** Si una
versión nueva añade un llamador, el parche deja de cubrirlo en silencio.
Comando para regenerarla, sobre un clon de edx-platform:

    grep -rn "sort_by_announcement\|sort_by_start_date" --include="*.py" \
      | grep -v "def sort_by"
    grep -rn "is_empty_html" --include="*.py" | grep -v "def is_empty_html"

Verificado contra release/ulmo.3 el 12 de agosto de 2026.
"""

import logging
from importlib import import_module

from django.conf import settings

log = logging.getLogger(__name__)


def _patch_in_modules(module_paths, attr_name, new_func):
    """
    Sustituye `attr_name` por `new_func` en cada módulo de `module_paths`.

    Registra en el log cada sustitución y avisa si un módulo no expone el
    atributo esperado: eso significa que upstream cambió y el parche podría
    haber dejado de aplicarse donde hacía falta.
    """
    applied = []
    for path in module_paths:
        try:
            module = import_module(path)
        except ImportError:
            log.warning(
                "aprende_customizations: no se pudo importar %s para parchear %s",
                path, attr_name,
            )
            continue

        if not hasattr(module, attr_name):
            log.warning(
                "aprende_customizations: %s no expone %s. "
                "¿Cambió upstream? El parche NO se aplicó ahí.",
                path, attr_name,
            )
            continue

        setattr(module, attr_name, new_func)
        applied.append(path)

    log.info(
        "aprende_customizations: %s parcheado en %d módulo(s): %s",
        attr_name, len(applied), ", ".join(applied) or "ninguno",
    )
    return applied


# ---------------------------------------------------------------------------
# Orden del catálogo
# ---------------------------------------------------------------------------
# Upstream ordena de más viejo a más nuevo. @prende.mx quiere lo contrario.
# Antes: dos `reverse=False` -> `reverse=True` dentro del fork.
# Ahora: mismas funciones, con el sentido leído de un setting.

_CATALOG_SORT_MODULES = (
    "lms.djangoapps.courseware.courses",              # origen
    "lms.djangoapps.courseware.views.views",          # from ... import
    "common.djangoapps.student.views.management",     # from ... import
)


def sort_by_announcement(courses):
    """
    Igual que upstream, con el sentido del orden configurable.
    """
    reverse = getattr(settings, "APRENDE_CATALOG_NEWEST_FIRST", True)
    return sorted(courses, key=lambda course: course.sorting_score, reverse=reverse)


def sort_by_start_date(courses):
    """
    Igual que upstream, con el sentido del orden configurable.
    """
    reverse = getattr(settings, "APRENDE_CATALOG_NEWEST_FIRST", True)
    return sorted(
        courses,
        key=lambda course: (course.has_ended(), course.start is None, course.start),
        reverse=reverse,
    )


# ---------------------------------------------------------------------------
# is_empty_html — corrección de un defecto de upstream
# ---------------------------------------------------------------------------
# Upstream considera vacía cualquier descripción sin texto visible, incluidas
# las que solo contienen el iframe del video de introducción del curso.
#
# Candidata a PR upstream (Fase 3). Si se acepta, este parche se retira.

_EMPTY_HTML_MODULES = (
    "lms.djangoapps.courseware.utils",                # origen
    "lms.djangoapps.courseware.courses",              # from ... import
)

_MEDIA_TAGS = ("iframe", "video", "audio", "img", "embed", "object", "source")


def is_empty_html(html_content):
    """
    Una descripción es no vacía si tiene texto visible O algún elemento
    multimedia embebido.
    """
    from bs4 import BeautifulSoup  # pylint: disable=import-outside-toplevel

    if not html_content:
        return True

    soup = BeautifulSoup(html_content, "html.parser")
    if soup.get_text(strip=True):
        return False

    return soup.find(_MEDIA_TAGS) is None


# ---------------------------------------------------------------------------
# linked_in_url — corrección de una línea
# ---------------------------------------------------------------------------
# Upstream pasa el objeto `course` donde add_to_profile_url espera el nombre.
# Se parchea la función privada completa porque la corrección está en medio
# de ella y el módulo la resuelve por globals() en tiempo de llamada.
#
# Candidata a PR upstream (Fase 3).

_SOCIAL_CONTEXT_MODULES = ("lms.djangoapps.certificates.views.webview",)


def _update_social_context(request, context, course, user_certificate, platform_name):
    """
    Copia literal de `_update_social_context` de release/ulmo.3, con una sola
    diferencia: `add_to_profile_url` recibe `course.display_name` en lugar del
    objeto `course`.

    Se copia el cuerpo entero porque la corrección está en la última línea de
    la función y no hay hook que permita interceptar solo eso.

    Verificado contra release/ulmo.3 el 12 de agosto de 2026. **Revisar en cada
    actualización de Open edX**: si upstream cambia esta función, esta copia se
    queda atrás en silencio.
    """
    # Imports locales: replican los del módulo de upstream.
    import urllib.parse  # pylint: disable=import-outside-toplevel

    from django.utils.encoding import smart_str  # pylint: disable=import-outside-toplevel
    from django.utils.translation import gettext as _  # pylint: disable=import-outside-toplevel
    from lms.djangoapps.certificates.api import get_certificate_url  # pylint: disable=import-outside-toplevel
    from openedx.core.djangoapps.site_configuration import (  # pylint: disable=import-outside-toplevel
        helpers as configuration_helpers,
    )
    from openedx.core.djangoapps.user_api.models import (  # noqa pylint: disable=import-outside-toplevel,unused-import
        UserPreference,
    )
    from lms.djangoapps.certificates.models import (  # pylint: disable=import-outside-toplevel
        LinkedInAddToProfileConfiguration,
    )

    share_settings = configuration_helpers.get_value(
        "SOCIAL_SHARING_SETTINGS", settings.SOCIAL_SHARING_SETTINGS
    )
    context["facebook_share_enabled"] = share_settings.get("CERTIFICATE_FACEBOOK", False)
    context["facebook_app_id"] = configuration_helpers.get_value(
        "FACEBOOK_APP_ID", settings.FACEBOOK_APP_ID
    )
    context["facebook_share_text"] = share_settings.get(
        "CERTIFICATE_FACEBOOK_TEXT",
        _("I completed the {course_title} course on {platform_name}.").format(
            course_title=context["accomplishment_copy_course_name"],
            platform_name=platform_name,
        ),
    )
    context["twitter_share_enabled"] = share_settings.get("CERTIFICATE_TWITTER", False)
    context["twitter_share_text"] = share_settings.get(
        "CERTIFICATE_TWITTER_TEXT",
        _("I completed a course at {platform_name}. Take a look at my certificate.").format(
            platform_name=platform_name
        ),
    )

    share_url = request.build_absolute_uri(
        get_certificate_url(course_id=course.id, uuid=user_certificate.verify_uuid)
    )
    context["share_url"] = share_url
    twitter_url = ""
    if context.get("twitter_share_enabled", False):
        twitter_url = "https://twitter.com/intent/tweet?text={twitter_share_text}&url={share_url}".format(
            twitter_share_text=smart_str(context["twitter_share_text"]),
            share_url=urllib.parse.quote_plus(smart_str(share_url)),
        )
    context["twitter_url"] = twitter_url
    context["linked_in_url"] = None

    linkedin_config = LinkedInAddToProfileConfiguration.current()
    if linkedin_config.is_enabled():
        context["linked_in_url"] = linkedin_config.add_to_profile_url(
            # ÚNICA diferencia con upstream: display_name en lugar del objeto.
            course.display_name,
            user_certificate.mode,
            smart_str(share_url),
            certificate=user_certificate,
        )


# ---------------------------------------------------------------------------
# Aplicación
# ---------------------------------------------------------------------------

def apply_all():
    """
    Aplica todos los parches habilitados. Llamado desde AppConfig.ready().
    """
    if getattr(settings, "APRENDE_CATALOG_NEWEST_FIRST", True):
        _patch_in_modules(_CATALOG_SORT_MODULES, "sort_by_announcement", sort_by_announcement)
        _patch_in_modules(_CATALOG_SORT_MODULES, "sort_by_start_date", sort_by_start_date)

    if getattr(settings, "APRENDE_FIX_EMPTY_HTML_MEDIA", True):
        _patch_in_modules(_EMPTY_HTML_MODULES, "is_empty_html", is_empty_html)

    if getattr(settings, "APRENDE_FIX_LINKEDIN_URL", True):
        _patch_in_modules(
            _SOCIAL_CONTEXT_MODULES, "_update_social_context", _update_social_context
        )
