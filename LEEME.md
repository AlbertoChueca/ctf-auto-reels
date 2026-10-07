# ChessTalentsFactory – Reels orgánicos automáticos

Publica sola **2 reels al día** en Instagram + Story, **Facebook Reels**, YouTube Shorts y TikTok, pensados para
padres estadounidenses, con un único objetivo: que vean la VSL, reserven llamada y lleguen convencidos.
Tu tiempo continuo: cero. Cada lunes recibes un informe por email.

## Qué se publica (calendario automático, hora de Nueva York)

Sin puzzles: todo son reels de motion graphics para padres.

| Día | 12:00 | 21:00 |
|---|---|---|
| Lunes | Dolor → solución | Pregunta de padres (FAQ) |
| Martes | **Éxito de alumno** | **Remix** de un reel anterior |
| Miércoles | Pregunta de padres (FAQ) | Dolor → solución |
| Jueves | **Remix** de un reel anterior | **Éxito de alumno** |
| Viernes | Método / hoja de ruta | **Remix** de un reel anterior |
| Sábado | **Éxito de alumno** | Pregunta de padres (FAQ) |
| Domingo | **Remix** de un reel anterior | Método / hoja de ruta |

- **Éxito de alumno**: historias reales sacadas SOLO de lo que la Academia ya publica: las páginas de alumnos de la
  web (`success_sync.py`, cada domingo) y los casos que aparecen en tus propios reels (`content_bank.py`). Rota los
  casos para no repetir. Por defecto no dice nombres ("one of our students"); con la variable
  `STUDENT_NAMES=first` usa el nombre de pila que ya aparece en tu web.
- **Remix**: cada domingo el sistema analiza con Gemini tus reels publicados (los del editor y los automáticos):
  tema, gancho, puntos clave, por qué funcionó. Los mejores se reexplican de otra forma (otro gancho, otro ángulo)
  sin repetir la misma idea en 45 días. Todo queda en `content_bank.json`.
- **Motion graphics** (`make_explainer.py` + `design.py`): 15 bloques de escena con diseño premium
  (titulares Montserrat Black con marca naranja, tarjetas tipo papel, fondos de estudio, subtítulos con la palabra
  activa en naranja, barra de progreso, fundidos suaves y sonido tonal). Gemini solo escribe y elige bloques.
- **Director creativo** (`director.py`, segundo agente): antes de grabar la voz escribe 5 ganchos alternativos, los
  puntúa y se queda con el mejor, y pule todo el guion para que convierta. Después revisa un storyboard con un
  fotograma de cada escena (legibilidad, solapes, jerarquía, coherencia con la voz) y aplica correcciones hasta
  llegar a 8/10 (máx. 2 rondas). Al final un tercer control ve el vídeo terminado. Todo queda en el resumen de
  cada ejecución y en `review_log.jsonl`.
- **Respaldo**: si el guion de IA falla dos veces, se usa un guion de reserva ya escrito (`evergreen.json`, solo
  hechos reales de tu web). Siempre sale un reel de la Academia.

## 100 % gratis
- No se usa generación de imágenes con IA: todo el diseño está hecho en código.
- Gemini se usa en su capa gratuita (guiones, voz y análisis de vídeos). Si la voz de Gemini supera el límite
  gratuito, el sistema cambia solo a una voz local gratuita (Kokoro) para que el reel salga igualmente.
- Instagram, Facebook Reels y el bot usan la API gratuita de Meta.
- GitHub Actions: un repo privado tiene 2.000 minutos gratis al mes. Con 2 reels/día, el bot cada 2 horas y
  los trabajos semanales se queda por debajo. Si algún mes se acercara al límite, GitHub avisa por email.
- YouTube/TikTok vía Zernio es opcional; sin `ZERNIO_API_KEY` simplemente no se publica ahí.

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
3. **Datos aprobados**: `claims.json` ya trae aprobadas las cifras de tu web (250+ alumnos, 30+ campeones
   nacionales, 15+ países, títulos). `cases.json` trae los casos de Pranav y Vyom de tu web y se amplía solo cada
   domingo. Pon `"approved": false` en cualquiera que no quieras usar.
4. **Prueba**: Actions → *Daily reels* → Run workflow → elige `pillar` (success, remix, faq…) con `dry_run`
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
| `STUDENT_NAMES` | `none` | `first` = usar el nombre de pila de los alumnos que ya aparecen en tu web. |
| `BANK_MAX_NEW` | `8` | Vídeos nuevos analizados por semana. |

## Personajes y logo
`assets/kit/` contiene los personajes recortados de tu vídeo y `assets/logo_h.png` tu logo, de forma
**provisional**. Cuando el diseñador te pase los archivos fuente, exporta cada pose como PNG transparente con el
mismo nombre (`girl_sad.png`, `girl_thinking.png`, `girl_standing.png`, `girl_trophy.png`, `coach_standing.png`,
`pair_hands.png`) y súbelos: todos los reels mejoran sin tocar código. Se pueden añadir poses nuevas.

## Workflows
- *Daily reels*: 2 al día (13:00 y 22:00 hora de Paraguay).
- *Comment bot*: cada 2 horas, respuestas públicas + DM de palabra clave.
- *Content bank*: domingos, lee los éxitos de tu web y analiza tus reels publicados.
- *Weekly report*: lunes 10:00 Paraguay, llega como Issue a tu email.
- *Voice samples*: escucha voces sin publicar nada.

Pausar todo: Actions → *Daily reels* → "…" → *Disable workflow*.
