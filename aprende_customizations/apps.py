"""
Configuración de la app y punto de entrada de los parches.
"""

import logging

from django.apps import AppConfig

log = logging.getLogger(__name__)


class AprendeCustomizationsConfig(AppConfig):
    """
    Django app plugin de Open edX.

    `plugin_app` es lo que hace que el LMS la reconozca como plugin: sin este
    diccionario, la app se instala pero Open edX no la registra.
    """

    name = "aprende_customizations"
    verbose_name = "Personalizaciones Aprende/@prende.mx"

    plugin_app = {
        "settings_config": {
            "lms.djangoapp": {
                "common": {"relative_path": "settings.common"},
                "production": {"relative_path": "settings.production"},
                "devstack": {"relative_path": "settings.common"},
            },
        },
    }

    def ready(self):
        """
        Aplica los parches al arrancar.

        Los import van DENTRO del método, no arriba del archivo: importar
        módulos de views de edx-platform en tiempo de import del AppConfig
        dispara AppRegistryNotReady, porque esos módulos arrastran modelos.
        """
        from aprende_customizations import patches  # pylint: disable=import-outside-toplevel

        try:
            patches.apply_all()
        except Exception:  # pylint: disable=broad-except
            # Un fallo aquí impediría arrancar el LMS. Se registra y se sigue:
            # es preferible una instancia con el orden de catálogo de upstream
            # que una instancia caída. El log es la señal de alarma.
            log.exception(
                "aprende_customizations: fallo al aplicar los parches. "
                "La instancia arranca con el comportamiento de upstream."
            )
