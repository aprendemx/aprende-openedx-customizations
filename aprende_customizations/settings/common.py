"""
Valores por defecto. Se pueden sobrescribir desde un plugin de Tutor sin
reconstruir la imagen.
"""


def plugin_settings(settings):
    """
    Open edX llama a esta función al cargar los settings del LMS.
    """
    # Orden del catálogo: True = del más nuevo al más viejo.
    # Upstream ordena al revés; esto es la personalización de @prende.mx.
    # Configurable para poder revertirlo sin reconstruir la imagen.
    settings.APRENDE_CATALOG_NEWEST_FIRST = True

    # Trata como no vacía una descripción de curso que solo contiene un
    # elemento multimedia (típicamente el iframe del video de introducción).
    # Es una corrección de un defecto de upstream; se retirará si se acepta
    # el PR correspondiente.
    settings.APRENDE_FIX_EMPTY_HTML_MEDIA = True

    # Corrige la llamada a LinkedInAddToProfileConfiguration.add_to_profile_url,
    # que upstream invoca con el objeto `course` en lugar de su display_name.
    settings.APRENDE_FIX_LINKEDIN_URL = True
