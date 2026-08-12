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
| `certificates/views/webview.py` — `linked_in_url` | 1 | `patches.py` — sustitución de función |
| `certificates/views/webview.py` — `fullTheme` | ~4 | **descartado** — ver abajo |
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

### `fullTheme` queda fuera, y es un hallazgo aparte

En el fork, `_update_context_with_user_score` invertía `fullTheme` partiendo de
`context.get('fullTheme', False)`. Como la clave nunca existe en el contexto, el
valor era siempre `True` y la rama `% if not fullTheme:` de
`certificates/_accomplishment-rendering.html` **no se renderizaba nunca**.

Consecuencia: todos los certificados sirven el logo desde una URL externa

```
https://aprende.gob.mx/images/Logo_Educ_RG.png
```

en lugar del estático local `${static.url("images/ENDOSO_5.png")}`. Un
certificado es un documento que se abre meses después de emitirse; si ese
recurso se mueve o el sitio no responde, el logo sale roto.

**Decidir cuál es el logo correcto** y, si es el local, corregir la condición de
la plantilla. Es contenido, no arquitectura: se resuelve fuera de este paquete.

### Se descartan dos variables sin consumidor

`score_available` y `accomplishment_copy_course_org_2` no aparecen en ninguna
plantilla del tema Indigo ni de upstream. Se calculaban y nadie las leía.

### Los tres defectos de la auditoría, corregidos

1. **`except Exception as e` sin registro** — ahora `log.exception`, y el filtro
   se configura con `fail_silently: False`.
2. **`user` sombreado en el bucle de `CourseGradeFactory`** — se usa `read()` en
   lugar de `iter()`, que no necesita bucle para un solo usuario.
3. **`fullTheme` como código muerto** — ver arriba.

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

1. **Verificar el orden de llamada.** `filters.py` asume que
   `_update_context_with_user_info` corre antes de `run_filter` (línea 597).
   Confirmar que `accomplishment_user_id` ya está en el contexto en ese punto:

   ```bash
   docker exec $LMS grep -n "_update_context_with_user_info\|run_filter" \
     /openedx/edx-platform/lms/djangoapps/certificates/views/webview.py
   ```

2. **Probar el import desde `AppConfig.ready()`, no solo desde el shell.** El
   shell corre con las apps ya cargadas; `ready()` corre durante el arranque.
   El resultado OK del shell es necesario pero no suficiente. Si falla, mover
   los parches a una señal posterior.

3. **Verificar que ningún otro plugin define `OPEN_EDX_FILTERS_CONFIG`**, que
   esta configuración sobrescribiría.

4. **Pruebas funcionales.** Al menos: orden del catálogo, `is_empty_html` con
   descripción que solo tenga un iframe, renderizado de un certificado con y sin
   `displayScore`, y el botón de LinkedIn en un certificado.

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

---

## Plugin de Tutor

`tutor-plugin/aprende_customizations.py` registra el filtro del certificado en
`OPEN_EDX_FILTERS_CONFIG`. **No se instala con pip**: hay que copiarlo a la raíz de plugins de
Tutor del servidor.

```bash
sudo cp tutor-plugin/aprende_customizations.py /opt/tutor/plugins/
tutor plugins enable aprende_customizations
tutor config save
```

Se versiona aquí, junto al código que configura, para que no se separen. Sin este plugin el
paquete se instala pero el filtro del certificado nunca se registra — y no da ningún error.

Antes de habilitarlo, verificar que ningún otro plugin defina la misma variable:

```bash
grep -rn "OPEN_EDX_FILTERS_CONFIG" /opt/tutor/env/apps/openedx/settings/
```
