# ChessTalentsFactory – Reels orgánicos automáticos

Publica sola **2 reels al día** en Instagram + Story, **Facebook Reels**, YouTube Shorts y TikTok, pensados para
padres estadounidenses, con un único objetivo: que vean la VSL, reserven llamada y lleguen convencidos.
Tu tiempo continuo: cero. Cada lunes recibes un informe por email.

## Qué se publica (calendario automático, hora de Nueva York)

| Día | 12:00 – reel de conversión (motion graphics) | 21:00 – reto (insight + puzzle) |
|---|---|---|
| Lunes | Dolor → solución | Test para tu hijo |
| Martes | Error que frena el rating (insight + puzzle) | Test para tu hijo |
| Miércoles | Pregunta de padres (FAQ) | Envíaselo a otro padre |
| Jueves | Método / hoja de ruta | Test para tu hijo |
| Viernes | Dolor → solución | Test para tu hijo |
| Sábado | Prueba (solo con datos aprobados; si no, método) | Test para tu hijo |
| Domingo | Pregunta de padres (FAQ) | Test para tu hijo |

**Motion graphics** (`make_explainer.py`): mismo estilo que el vídeo "Stuck in chess?". Gemini solo escribe el
guion y elige entre 13 bloques de escena ya diseñados (niña frustrada, rating que baja, "lo que no funciona",
coach, roadmap, pasos del método, insignias, pregunta/respuesta, progreso, trofeo…). El diseño nunca depende de
que una IA dibuje bien.

**Insight + puzzle** (`make_story.py`): ilustraciones de Gemini + puzzle de Lichess para el hijo.

## Conversión
- **CTA** que el piloto automático prueba y optimiza: comentar la palabra clave (por defecto `PLAN`), ver la VSL,
  reservar llamada o comentar+seguir.
- **Palabra clave + DM**: quien comenta `PLAN` recibe por DM el enlace a la VSL (con UTM). Solo a quien lo pide,
  máximo 1 DM por persona y semana.
- **Piloto automático**: cada reel es un experimento (gancho, tema, nivel, CTA). La recompensa pesa mucho las
  visitas al perfil y los follows. Los lunes un estratega IA reescribe `playbook.md`.

## Calidad sin revisión humana
- Cifras de resultados **solo** si están aprobadas en `claims.json` / `cases.json`. Cualquier otra cifra en el
  guion hace que se descarte y se reescriba.
- Revisor IA en guion, imágenes y vídeo final; controles duros de duración y audio; jugadas verificadas.
- **Freno automático**: si fallan 2 ejecuciones seguidas o las views de los últimos 6 reels caen por debajo del
  40 % de la mediana de 14 días, se pausa la publicación (`paused.json`) y GitHub te avisa por email.
  Para reanudar: borra `paused.json` en el repo, o ejecuta *Daily reels* con `force`.
- Si un reel premium falla, sale otro formato de respaldo: nunca queda un hueco.

## Puesta en marcha (una sola vez, ~30 min)
1. Crea un repo **privado** en GitHub (p. ej. `ctf-auto-reels`) y sube todo este contenido.
2. **Secrets** (Settings → Secrets and variables → Actions → Secrets):
   - `IG_TOKEN`: token de **página** de Facebook vinculada al Instagram de la Academia. Permisos:
     instagram_basic, instagram_content_publish, instagram_manage_insights, instagram_manage_comments,
     **instagram_manage_messages** (DMs de palabra clave), pages_show_list, pages_read_engagement,
     **pages_manage_posts** (Facebook Reels).
   - `GEMINI_API_KEY` (pon un aviso de presupuesto en Google Cloud; coste estimado 10-20 $/mes).
   - `ZERNIO_API_KEY` (opcional, YouTube/TikTok; necesitas un perfil distinto al de StreakChess).
   - `AC_API_KEY` (opcional, para contar leads orgánicos de ActiveCampaign en el informe).
3. **Datos aprobados**: en `claims.json` pon `"approved": true` SOLO en las cifras reales y medidas
   (Elo medio ganado, títulos FIDE, plazas limitadas). En `cases.json`, casos con permiso de la familia.
4. **Prueba**: Actions → *Daily reels* → Run workflow → elige `pillar` (pain, faq, method…) con `dry_run`
   marcado. El vídeo queda en *Artifacts*.
5. Listo. Los horarios corren solos.

## Variables opcionales (Settings → Variables)
| Variable | Por defecto | Para qué |
|---|---|---|
| `CTA_MODE` | `auto` | Fija `keyword`, `vsl`, `call` o `comment` en lugar de dejar que el piloto pruebe. |
| `DM_KEYWORD` | `PLAN` | Palabra clave de los comentarios. |
| `KEYWORD_DMS` | `true` | `false` desactiva los DMs de palabra clave. |
| `CTA_URL` / `BOOK_URL` | web / admission-process | Enlaces de VSL y de reserva. |
| `FB_REELS` | `on` | `off` desactiva Facebook Reels. |
| `GEMINI_VOICE` | `Charon` | Voz (escucha opciones con *Voice samples*). |
| `NARRATOR` | `academy` | `coach` = primera persona como entrenador principal. |
| `LEAD_WEIGHT` | `1.0` | Peso de visitas al perfil/follows en la recompensa. |
| `AC_API_URL` | — | URL de tu cuenta de ActiveCampaign (para el informe). |

## Personajes y logo
`assets/kit/` contiene los personajes recortados de tu vídeo y `assets/logo_h.png` tu logo, de forma
**provisional**. Cuando el diseñador te pase los archivos fuente, exporta cada pose como PNG transparente con el
mismo nombre (`girl_sad.png`, `girl_thinking.png`, `girl_standing.png`, `girl_trophy.png`, `coach_standing.png`,
`pair_hands.png`) y súbelos: todos los reels mejoran sin tocar código. Se pueden añadir poses nuevas.

## Workflows
- *Daily reels*: 2 al día (13:00 y 22:00 hora de Paraguay).
- *Comment bot*: cada hora, respuestas públicas + DM de palabra clave.
- *Weekly report*: lunes 10:00 Paraguay, llega como Issue a tu email.
- *Story reel test* y *Voice samples*: pruebas sin publicar.

Pausar todo: Actions → *Daily reels* → "…" → *Disable workflow*.
