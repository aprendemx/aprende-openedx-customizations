"""
Filtro de renderizado del certificado.

Reemplaza `_update_context_with_user_score`, la función que el fork inyectaba
en medio de `render_html_view`. Aquí se usa el hook oficial
`org.openedx.learning.certificate.render.started.v1`, que corre después de
`context.update(course.cert_html_view_overrides)` — o sea, con `displayScore`
ya disponible en el contexto, que es la única restricción de orden que tenía
la versión original.

Diferencias deliberadas respecto al código del fork:

1. **No se toca `fullTheme`.** En el fork esa bandera se invertía en cada
   llamada partiendo de un valor que nunca existe en el contexto, así que
   siempre acababa en True y la rama `% if not fullTheme:` de
   `_accomplishment-rendering.html` no se renderizaba nunca. Es una decisión
   de contenido —qué logo debe llevar el certificado— y no de arquitectura;
   se resuelve aparte. Ver README.

2. **No se calcula `score_available` ni
   `accomplishment_copy_course_org_2`.** Ninguna plantilla del tema ni de
   upstream las consume.

3. **Las excepciones se registran.** El fork usaba `except Exception as e` sin
   hacer nada con `e`; un fallo de CourseGradeFactory dejaba el certificado
   con "N/A" sin rastro en los logs.

4. **No se sombrea `user`.** El fork reasignaba el parámetro dentro del bucle
   de `CourseGradeFactory().iter()`.
"""

import logging

from openedx_filters import PipelineStep

log = logging.getLogger(__name__)


class AddUserScore(PipelineStep):
    """
    Añade `course_grade` al contexto del certificado cuando el curso tiene
    `displayScore` activo en sus Advanced Settings.

    La plantilla `certificates/_accomplishment-rendering.html` del tema Indigo
    lo consume así:

        % if course_grade:
            <p class="...">Calificación: ${course_grade}%</p>
        % endif
    """

    def run_filter(self, context, custom_template):  # pylint: disable=arguments-differ
        if not context.get("displayScore", False):
            return {"context": context, "custom_template": custom_template}

        # El contexto NO trae el objeto `user`. Se reconstruye desde
        # `accomplishment_user_id`, que puebla `_update_context_with_user_info`
        # y es el id del TITULAR del certificado.
        #
        # Deliberadamente NO se usa `request.user`: un certificado es una URL
        # pública y puede abrirlo cualquiera. Con `request.user` se imprimiría
        # la calificación de quien mira, no la de quien lo obtuvo.
        user_id = context.get("accomplishment_user_id")
        course_id = context.get("course_id")

        if user_id is None or course_id is None:
            log.warning(
                "aprende_customizations: displayScore activo pero falta %s "
                "en el contexto del certificado; no se calcula la calificación.",
                "accomplishment_user_id" if user_id is None else "course_id",
            )
            context["course_grade"] = None
            return {"context": context, "custom_template": custom_template}

        context["course_grade"] = self._get_grade(user_id, course_id)
        return {"context": context, "custom_template": custom_template}

    @staticmethod
    def _get_grade(user_id, course_id):
        """
        Devuelve la calificación como porcentaje entero en texto, o None.

        None hace que la plantilla omita la línea entera, que es preferible a
        imprimir "Calificación: N/A" en un documento oficial.
        """
        from django.contrib.auth import get_user_model  # pylint: disable=import-outside-toplevel
        from lms.djangoapps.grades.api import CourseGradeFactory  # pylint: disable=import-outside-toplevel

        try:
            user = get_user_model().objects.get(id=user_id)
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "aprende_customizations: no existe el usuario id=%s "
                "referido por el certificado de course_id=%s.",
                user_id, course_id,
            )
            return None

        try:
            # create_if_needed=False: renderizar un certificado no debe provocar
            # el cálculo y persistencia de una calificación. Si no existe, se
            # omite la línea. Upstream tiene el parámetro en True por defecto.
            course_grade = CourseGradeFactory().read(
                user, course_key=course_id, create_if_needed=False
            )
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "aprende_customizations: no se pudo obtener la calificación de "
                "user_id=%s en course_id=%s para el certificado.",
                user_id, course_id,
            )
            return None

        if course_grade is None or course_grade.percent is None:
            log.warning(
                "aprende_customizations: sin calificación para user_id=%s en "
                "course_id=%s; el certificado se emite sin la línea.",
                user_id, course_id,
            )
            return None

        return "{:.0f}".format(course_grade.percent * 100)
