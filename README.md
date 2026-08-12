# aprende-openedx-customizations

Personalizaciones de Open edX para `cursos.aprende.gob.mx`, empaquetadas como
Django app plugin.

Sustituye a las 49 líneas de Python que hasta agosto de 2026 vivían en un fork
completo de `edx-platform` (≈1,4 M de líneas) alojado en una cuenta personal.

**Estado: borrador. No instalar todavía en ningún ambiente.** Ver "Trabajo
pendiente".

---

## Qué reemplaza

| Origen en el fork | Líneas | Mecanismo aquí |
|---|---:|---|
| `courseware/courses.py` — orden del catálogo | 7 | `patches.py` — sustitución de función |
| `courseware/utils.py` — `is_empty_html` | 10 | `patches.py` — sustitución de función |
| `certificates/views/webview.py` — calificación | ~20 | `filters.py` — hook `CertificateRenderStarted` |
| `certificates/views/webview.py` — `fullTheme` | ~4 | `filters.py` — **conservado**, ver abajo |
| `certificates/views/webview.py` — `linked_in_url` | 1 | `patches.py` — sustitución de función |
| `certificates/views/webview.py` — descripción de la organización | ~2 | **descartado** — sin consumidor |

---

## Decisiones y su razón

### El certificado usa el hook oficial, no un parche

El fork inyectaba una llamada a `_update_context_with_user_score` en medio de
`render_html_view`. Reproducir eso con monkeypatch obligaría a copiar las ~200
líneas de `render_html_view` al plugin, que es exactamente el problema de
mantenimiento que esta fase busca eliminar.

Open edX expone `org.openedx.learning.certificate.render.started.v1`, que corre
en la línea 597 de `webview.py` (release/ulmo.3) — **después** de
`context.update(course.cert_html_view_overrides)`, que era la única restricción
de orden de la versión original. El hook sirve exactamente para esto.

Es el mismo salto que el commit `fa9af19` de `tutor-indigo`: usar el mecanismo
previsto en vez de forzar el código.

### El orden del catálogo es un setting, no una constante

El fork cambiaba dos `reverse=False` por `reverse=True`. Aquí el sentido se lee
de `APRENDE_CATALOG_NEWEST_FIRST`, lo que permite revertirlo sin reconstruir la
imagen y deja el código en forma de propuesta para upstream (Fase 3 del plan).

### `fullTheme` se conserva — corrección de la auditoría

La auditoría lo listó como código muerto, y una primera versión de este paquete lo
descartó. **Era un error.**

La clave llega desde `cert_html_view_overrides` en las Advanced Settings del curso.
Ejemplo real de producción:

```json
{
    "customOrganizacionText": "impartido por la Secretaría Anticorrupción y Buen Gobierno...",
    "displayScore": true,
    "fullTheme": true,
    "organizationLogoExtra": "https://mexicox.gob.mx/media/organization_logos/fucion_publica.jpg"
}
```

La inversión (`context['fullTheme'] = not context.get('fullTheme', False)`) selecciona qué
rama de `certificates/_accomplishment-rendering.html` se renderiza:

| En `cert_html_view_overrides` | Tras la inversión | Rama | Logo |
|---|---|---|---|
| `"fullTheme": true` | `False` | `% if not fullTheme:` | local `ENDOSO_5.png` |
| clave ausente | `True` | `% else:` | remoto `aprende.gob.mx` |

Es un interruptor de juego de logos por curso. Descartarlo cambiaría el logo de todos los
certificados que declaran `"fullTheme": true`.

La doble negación es confusa y convendría invertir el nombre de la clave o la condición de la
plantilla, pero eso cambiaría el significado de la clave en los cursos que ya la declaran.
El paquete conserva el comportamiento exacto; simplificarlo es trabajo aparte.

### `LinkedInAddToProfileConfiguration` vive en `student.models`

No en `lms.djangoapps.certificates.models`, que es donde parecería por el contexto. La ruta
correcta —la que usa `webview.py:26`— es:

```python
from common.djangoapps.student.models import LinkedInAddToProfileConfiguration
```

Detectado al probar en `cursos-dev`: el import equivocado estaba **dentro** de
`_update_social_context`, así que no fallaba al aplicar el parche sino **al renderizar un
certificado**. Un despliegue con ese error habría tumbado todos los certificados.

Es el argumento a favor de probar el renderizado real y no solo que los parches se apliquen.

### Se descartan dos variables sin consumidor

`score_available` y `accomplishment_copy_course_org_2` no aparecen en ninguna
plantilla del tema Indigo ni de upstream. Se calculaban y nadie las leía.

### Defectos de la auditoría

1. **`except Exception as e` sin registro** — corregido: `log.exception`, y el filtro
   se configura con `fail_silently: False`.
2. **`user` sombreado en el bucle de `CourseGradeFactory`** — corregido: se usa `read()`
   en lugar de `iter()`, que no necesita bucle para un solo usuario.
3. **`fullTheme` como código muerto** — **el diagnóstico era incorrecto.** Es un
   interruptor funcional. Ver arriba.

---

## Instalación

```yaml
# config.yml de Tutor
OPENEDX_EXTRA_PIP_REQUIREMENTS:
- git+https://github.com/aprendemx/aprende-openedx-customizations.git@<sha>
```

Y un plugin de Tutor para registrar el filtro:

```python
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
```

`fail_silently: False` es deliberado: si el filtro falla, que falle de forma
visible en lugar de emitir certificados incompletos en silencio.

**Precaución:** si otro plugin ya define `OPEN_EDX_FILTERS_CONFIG`, esta
asignación lo sobrescribe. Verificar antes:

```bash
grep -rn "OPEN_EDX_FILTERS_CONFIG" /opt/tutor/env/apps/openedx/settings/
```

---

## Verificado contra release/ulmo.3 — 12 de agosto de 2026

| Comprobación | Resultado |
|---|---|
| Los cuatro módulos a parchear se importan sin `AppRegistryNotReady` | OK |
| `CourseGradeFactory.read(self, user, course=None, …, course_key=None, create_if_needed=True)` | OK |
| `context['course_id']` existe (webview.py:170) | OK |
| `context['user']` **no existe** | se usa `context['accomplishment_user_id']` (webview.py:320) |
| Cuerpo de `_update_social_context` copiado de ulmo.3 | OK |

### Nota de seguridad: de dónde sale el usuario

El contexto del certificado no incluye el objeto `user`. `filters.py` lo
reconstruye desde `accomplishment_user_id`, que puebla
`_update_context_with_user_info` y corresponde al **titular** del certificado.

**No se usa `request.user`.** La URL de un certificado es pública: si el
certificado de una persona lo abre otra, `request.user` sería quien mira y se
imprimiría su calificación en el documento de otro.

## Trabajo pendiente

1. **Verificar si LinkedIn está habilitado.** El botón "Add to LinkedIn" no aparece
   en ningún certificado de `cursos-dev` ni de producción:

   ```python
   from common.djangoapps.student.models import LinkedInAddToProfileConfiguration
   print(LinkedInAddToProfileConfiguration.current().is_enabled())
   ```

   Si devuelve `False`, la corrección de `linked_in_url` afecta a una rama que nunca
   se ejecuta — lo que explica que el defecto pasara desapercibido. El parche es
   inocuo y se conserva, pero conviene saberlo antes de proponer el PR upstream
   (Fase 3).

2. **Probar el renderizado real de un certificado** tras cada cambio en
   `patches.py` o `filters.py`. Que los parches se apliquen al arrancar no prueba
   que el certificado renderice: los import locales solo se evalúan al ejecutarse
   la función. Así se detectó el error de ruta de
   `LinkedInAddToProfileConfiguration`.

3. **Verificar que ningún otro plugin define `OPEN_EDX_FILTERS_CONFIG`**, que
   esta configuración sobrescribiría.

4. **Pruebas funcionales completas.** Orden del catálogo, `is_empty_html` con
   descripción que solo tenga un iframe, certificado con y sin `displayScore`, y
   certificado con y sin `fullTheme` — comprobando que el logo cambia.

## Fuera del alcance del paquete

**Recursos externos en el certificado.** El certificado carga imágenes desde
`aprende.gob.mx` y `mexicox.gob.mx` (esta última vía `organizationLogoExtra`).
En `cursos-dev` algunas aparecen rotas. Un certificado se abre meses después de
emitirse; si esos recursos se mueven, el documento sale incompleto.

Además, `/static/images/Logo_OCEI.png` se sirve **sin hash de manifiesto**, a
diferencia del resto de estáticos del tema — probablemente no pasó por
`collectstatic` correctamente.

Es contenido e infraestructura de assets, no arquitectura de este paquete, pero
conviene revisarlo.

---

## Mantenimiento

`patches.py` sustituye funciones en varios módulos porque los llamadores usan
`from ... import nombre`, lo que copia la referencia en tiempo de import.

**La lista de módulos debe revisarse en cada actualización de Open edX.** Si una
versión nueva añade un llamador, el parche deja de cubrirlo sin dar ningún
error. `_patch_in_modules` registra un aviso cuando un módulo esperado no expone
el atributo, pero no puede detectar llamadores nuevos.

```bash
# sobre un clon de edx-platform en la versión de destino
grep -rn "sort_by_announcement\|sort_by_start_date" --include="*.py" | grep -v "def sort_by"
grep -rn "is_empty_html" --include="*.py" | grep -v "def is_empty_html"
```

Lista verificada contra `release/ulmo.3` el 12 de agosto de 2026.
