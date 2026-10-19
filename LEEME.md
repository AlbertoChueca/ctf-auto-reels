# ChessTalentsFactory – Reels orgánicos automáticos

Publica sola **1 publicación al día** (12:00 Nueva York) en Instagram + Story, **Facebook Reels**, YouTube Shorts y
TikTok, pensada para **padres que no juegan al ajedrez**. Objetivo: que se paren, guarden, comenten "PLAN" y entren
en el embudo. Tu tiempo continuo: cero.

## Qué se publica (versión 3, octubre 2026)

Menos cantidad, más calidad y formatos variados. La mayoría **sin narrador**: nada suena a IA.

| Día | Formato | Qué es |
|---|---|---|
| Lunes | **Carrusel** (`make_carousel.py`) | 7 diapositivas de consejo: "5 señales…", "Qué decir cuando…". El formato que más se guarda |
| Martes | **Chat** (`make_textreel.py chat`) | Conversación de mensajes entre un padre y nuestro coach, con "escribiendo…" |
| Miércoles | **Reto** (`make_challenge.py`) | "¿Encuentra tu hijo la jugada?" Puzzle real, cuenta atrás, solución animada |
| Jueves | **Voz** (`make_broll.py`) | El reel narrado, con voz expresiva verificada palabra a palabra |
| Viernes | **Carrusel** | Otro tema del banco de preguntas |
| Sábado | **Texto** (`make_textreel.py kinetic`) | Frases grandes que entran palabra a palabra: POV, mito vs verdad, "nadie te dice…" |
| Domingo | **Reto** | Otro puzzle, a otro nivel |

- **Banco de preguntas de padres** (`parent_topics.json`, 95 temas en lenguaje de padre: el coche después de
  perder, lágrimas, pantallas, colegio, cuánto entrenar…). Cada publicación usa el tema menos usado. Edítalo
  libremente: añade las preguntas que oyes en tus llamadas.
- **Sin jerga**: se rechaza cualquier texto con términos que un padre no entiende (claves, T-T-P, "metodología",
  notación…). Square 65 ya no es titular.
- **Fondo cinematográfico**: un tablero real con posiciones de partidas clásicas, desenfocado, con luz cálida.
  Todo en código, nada de stock aleatorio ni imágenes de IA.
- **Música**: una base cálida tipo lo-fi/piano generada en código y masterizada. **Mejora fácil:** sube 10-20
  pistas sin copyright a `assets/music/` (YouTube Audio Library o Pixabay Music, gratis) y se usarán ellas,
  rotando la menos usada.
- **Retos**: puzzles de la base pública de Lichess (CC0, se descarga y se guarda en caché la primera vez) a nivel
  infantil; si no se puede descargar, usa 20 puzzles propios verificados por ordenador. Nunca repite un puzzle.
- **Reserva siempre lista**: si la IA falla, cada formato tiene contenido ya escrito (`evergreen_faceless.json`,
  8 por formato). Si un carrusel no se puede publicar, se publica el mismo contenido como reel.
- **CTA único** en todo: comentar `PLAN` (el bot responde por DM con el enlace al formulario).
- **Estudio de creadores desactivado** (`STUDIO=off`) hasta que haya datos reales de visualizaciones; con un solo
  estilo coherente se aprende más rápido.

Para probar un formato: *Actions → Daily reels → Run workflow* → `format` + `dry_run`. Las diapositivas y vídeos
quedan en *Artifacts*.

## Formato voz: vídeo real (`make_broll.py`, solo los jueves)

Escenas reales de familias, niños estudiando, coche camino del torneo, manos moviendo piezas, trofeos… sacadas de
**Pixabay** (y Pexels si tienes clave; gratis, licencia comercial, sin atribución). Encima: voz, titulares animados en
6 composiciones distintas (arriba, centro, abajo, pregunta, lista numerada, cita del libro) y tarjetas de cristal con
datos reales:
- **Gráfica de progreso real** del caso del día (p. ej. 1100 → 1800 en 13 meses), dibujándose en pantalla.
- **Escalera de los 6 niveles** del Learning Path (para que el padre entienda dónde está su hijo).
- **Tarjeta de clave de Square 65**, cifra aprobada (250+ alumnos…) o lista de 3 puntos.

**Cada reel es nuevo y distinto del anterior:**
- 7 estructuras (historia, "3 señales…", mito vs. realidad, POV, carta al padre, pregunta-respuesta, antes/después);
  nunca se repite la estructura de los 3 últimos reels.
- Control de novedad: si el gancho o la idea se parecen a cualquiera de los últimos 40 reels, el guion se rechaza y
  se reescribe con otro ángulo.
- Cada creador IA tiene su propio etalonaje (cálido, frío, contrastado, suave); música, movimientos de cámara y
  transiciones cambian en cada reel; un clip no se repite en 60 días (`stock_used.json`).
- **Editor de vídeo IA**: antes de usar un clip, Gemini mira las miniaturas reales de 6 candidatos por escena y
  elige el que encaja con lo que dice la voz (descarta animaciones, 3D, cielos estrellados, bebés, adultos solos…).
  Si ninguno vale, propone otra búsqueda y repite (hasta 3 rondas). El director de arte puede pedir otro clip y
  vuelve a ver el storyboard ya con el clip nuevo.
- En los éxitos de alumnos solo se usan planos **no identificables** (manos, tablero, trofeo, sala de torneo) con la
  etiqueta "Illustrative footage": el vídeo ilustra, nunca se hace pasar por el alumno.

Los antiguos dibujos (la niña, el niño y el entrenador ilustrados) y el formato de motion graphics están retirados.
Si un día Pixabay no responde, el reel sale igual con el mismo diseño sobre un fondo oscuro de marca.

**Prueba del padre** (`guard.jargon` + guardián de marca): si el guion usa jerga que un padre no entiende
("fianchetto", "pawn structure", notación…) se rechaza y se reescribe; términos como "opening" o "endgame" solo se
permiten de forma puntual y explicados con comparaciones del día a día (notas del colegio, deporte, música).

- **Éxito de alumno**: historias reales sacadas SOLO de lo que la Academia ya publica: las páginas de alumnos de la
  web (`success_sync.py`, cada domingo) y los casos que aparecen en tus propios reels (`content_bank.py`). Rota los
  casos para no repetir. Por defecto no dice nombres ("one of our students"); con la variable
  `STUDENT_NAMES=first` usa el nombre de pila que ya aparece en tu web.
- **Remix**: cada domingo el sistema analiza con Gemini tus reels publicados (los del editor y los automáticos):
  tema, gancho, puntos clave, por qué funcionó. Los mejores se reexplican de otra forma (otro gancho, otro ángulo)
  sin repetir la misma idea en 45 días. Todo queda en `content_bank.json`.
- **Director creativo** (`director.py`, segundo agente): antes de grabar la voz escribe 5 ganchos alternativos, los
  puntúa y se queda con el mejor, y pule todo el guion para que convierta. Después revisa un storyboard con un
  fotograma real de cada escena (con el vídeo de fondo) (legibilidad, solapes, jerarquía, coherencia con la voz) y aplica correcciones hasta
  llegar a 8/10 (máx. 2 rondas). Al final un tercer control ve el vídeo terminado. Todo queda en el resumen de
  cada ejecución y en `review_log.jsonl`.
- **Respaldo**: si el guion de IA falla dos veces, se usa un guion de reserva ya escrito (`evergreen_broll.json`, solo
  hechos reales de tu web). Siempre sale un reel de la Academia.

## 100 % gratis
- Vídeo real: Pixabay es gratuito (solo hay que crear una clave, ver abajo).
- No se usa generación de imágenes con IA: todo el diseño está hecho en código.
- Gemini se usa en su capa gratuita (guiones, voz y análisis de vídeos). Si la voz de Gemini supera el límite
  gratuito, el sistema cambia solo a una voz local gratuita (Kokoro) para que el reel salga igualmente.
- Instagram, Facebook Reels y el bot usan la API gratuita de Meta.
- GitHub Actions: un repo privado tiene 2.000 minutos gratis al mes. Con 2 reels/día, el bot cada 2 horas y
  los trabajos semanales se queda por debajo. Si algún mes se acercara al límite, GitHub avisa por email.
- YouTube/TikTok vía Zernio es opcional; sin `ZERNIO_API_KEY` simplemente no se publica ahí.

## Marca propia: nada de contenido genérico
- **`brand_bible.md`** (editable): posicionamiento, tu método con sus nombres propios (Square 65 / Meta-Chess,
  sistema T-T-P, diagnóstico técnico, Study Thesis, los 6 niveles del Learning Path…), tu voz, las palabras que
  usamos y las prohibidas, y la **prueba del competidor**. Todos los agentes la leen antes de escribir.
- **`method_bank.json`**: las 65 claves de *Square 65* extraídas del libro. Pilar nuevo **"key"** (4 reels a la
  semana): cada uno enseña una clave con la tarjeta "SQUARE 65 · KEY n/65". Rotan sin repetirse hasta usar las 65.
  Además, **todos los demás reels** llevan una clave relacionada como ancla del método.
- **Guardián de marca** (en `director.py`): puntúa de 1 a 10 si solo ChessTalentsFactory podría haber hecho el reel
  y si respeta la voz. Por debajo de 8, o sin ninguna ancla propia, lo reescribe con tu método. Lo verás en el
  resumen de cada ejecución.
- Casos del libro añadidos a `cases.json` (Omya, Vishva, Jwalanthi, Imran, Shiv, Alejandra) y credenciales en
  `claims.json` (IM, FIDE Trainer, entrenador oficial de US Chess en Mundiales U8/U10/U12, autor).

## Estudio de 5 creadores IA (`studio.py`)

Cada reel lo diseña uno de 5 creadores con personalidad, especialidad y estilo visual propios:

| Creador | Especialidad | Estilo de gancho | Look |
|---|---|---|---|
| The Analyst | Método, FAQ, prueba | Marcos claros: "Las 3 habilidades entre 1200 y 1500" | Papel editorial, subrayado |
| The Storyteller | Éxitos, remix, dolor | Momentos reales de alumnos | Cálido, marca naranja |
| The Myth Buster | Dolor, método, remix | Rompe una creencia de los padres | Estudio, marca naranja |
| The Parent Whisperer | FAQ, dolor, éxitos | Empatía con el padre, objeciones | Papel, marca naranja |
| The Trend Scout | Remix, dolor, FAQ, método | Formatos que frenan el scroll (POV, "nadie te dice…") | Cálido, subrayado |

- **Compiten**: cada reel se asigna con muestreo de Thompson según resultados reales (visitas al perfil, follows,
  shares, guardados, views). El mejor recibe más reels; un 20 % sigue explorando y nunca repite el creador del
  reel anterior.
- **Aprenden cada día**: cada creador reescribe su cuaderno (`agents/<creador>.md`) con sus mejores y peores reels,
  los comentarios de los padres y lo que el director creativo le corrigió: qué mantener, qué dejar y 3 experimentos
  nuevos.
- **Se enseñan entre ellos**: cada lunes el jefe de estudio extrae las lecciones del líder (`agents/_studio.md`)
  y todos las aplican a su estilo.
- **Control de calidad**: todo pasa por el director creativo (gancho, copy y arte) y la revisión final del vídeo,
  que pulen sin borrar la voz del creador. Las reglas de honestidad no se pueden saltar.
- El ranking sale en el informe de los lunes. Para probar uno en concreto: *Daily reels* → `creator`.

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
   - `GEMINI_API_KEY` (capa gratuita de Google AI Studio).
   - `PIXABAY_API_KEY` (**gratis**, para el vídeo real): crea cuenta en pixabay.com, entra en
     pixabay.com/api/docs y copia la clave que aparece en el apartado "Parameters" (key).
     `PEXELS_API_KEY` es opcional (Pexels tiene pausada la emisión de claves nuevas).
   - Alternativa sin claves: carpeta `stock_library/` con 12+ clips propios o de licencia libre (ver su LEEME).
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

## Logo
`assets/logo_h.png` es tu logo (barra superior y tarjeta final). Sustitúyelo por la versión del diseñador con el
mismo nombre cuando quieras. Ya no se usan personajes ilustrados.

## Workflows
- *Daily reels*: 2 al día (13:00 y 22:00 hora de Paraguay).
- *Comment bot*: cada 2 horas, respuestas públicas + DM de palabra clave.
- *Content bank*: domingos, lee los éxitos de tu web y analiza tus reels publicados.
- *Weekly report*: lunes 10:00 Paraguay, llega como Issue a tu email.
- *Voice samples*: escucha voces sin publicar nada.

Pausar todo: Actions → *Daily reels* → "…" → *Disable workflow*.
