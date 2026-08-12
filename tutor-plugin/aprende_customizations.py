from tutor import hooks

hooks.Filters.ENV_PATCHES.add_item((
    "openedx-lms-common-settings",
    """
OPEN_EDX_FILTERS_CONFIG = {
    "org.openedx.learning.certificate.render.started.v1": {
        "fail_silently": False,
        "pipeline": ["aprende_customizations.filters.AddUserScore"],
    },
}
""",
))
