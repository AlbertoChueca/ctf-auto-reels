"""ChessTalentsFactory brand + every business decision of the reels tool, in ONE place.

Everything can be changed without touching code through GitHub repository *Variables*
(Settings -> Secrets and variables -> Actions -> Variables):

  REEL_FORMAT   coach (default) | mascot      coach = illustrated scenes, no character; mascot = needs assets/mascot/
  NARRATOR      academy (default) | coach      academy = "we at ChessTalentsFactory"; coach = first person as the head coach
  CTA_MODE      auto (default) | vsl | call | comment      auto = the autopilot tests the three and keeps the winner
  CTA_URL       URL of the VSL (default chesstalentsfactory.com, the page with the free video)
  BOOK_URL      URL to book the call (default chesstalentsfactory.com/admission-process)
  IG_HANDLE     Instagram handle without @ (only used in texts)
  COACH_NAME    default "IM Alberto Chueca"
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))


def _env(k, default):
    v = (os.environ.get(k) or "").strip()
    return v or default


NAME = "ChessTalentsFactory"
SHORT = "CTF"
COACH = _env("COACH_NAME", "IM Alberto Chueca")
COACH_SHORT = "Coach " + COACH.split()[-2] if len(COACH.split()) >= 2 else COACH
IG_HANDLE = _env("IG_HANDLE", "chesstalentsfactory")
CTA_URL = _env("CTA_URL", "chesstalentsfactory.com")
BOOK_URL = _env("BOOK_URL", "chesstalentsfactory.com/admission-process")
FORMAT = _env("REEL_FORMAT", "coach").lower()
NARRATOR = _env("NARRATOR", "academy").lower()
CTA_MODE = _env("CTA_MODE", "auto").lower()
KEYWORD = _env("DM_KEYWORD", "PLAN").upper()        # comment keyword that triggers the DM with the free video


def url_display(u):
    return re.sub(r"^https?://(www\.)?", "", u).rstrip("/")


def url_full(u, medium="reel"):
    u = u if u.startswith("http") else "https://" + u
    sep = "&" if "?" in u else "?"
    return f"{u}{sep}utm_source=instagram&utm_medium={medium}&utm_campaign=auto_reels"


# Colours: the academy uses black + orange.
ORANGE = (245, 128, 32)
ORANGE_DARK = (196, 86, 14)
GOLD = (255, 200, 70)
INK = (14, 12, 16)
WHITE = (255, 255, 255)

# ---------------------------------------------------------------- audience (what every AI agent is told)
AUDIENCE = (
    "AUDIENCE: ambitious US parents (often tech professionals, many of Indian origin, Bay Area / NJ / Texas, high "
    "income, busy, travel a lot) whose child (7-16) already plays chess and maybe tournaments. They want their child to "
    "progress fast and stand out, they value expertise, method and measurable results (rating), and they are tired of "
    "slow, improvised lessons. They watch on Instagram/Facebook, often with their child next to them.")

ACADEMY = (
    f"{NAME} is a premium online chess academy for kids with a team of International Masters and 15 years of "
    "coaching experience. Small groups (2-6 kids of similar age and level) or private lessons with International Masters, a "
    "tested methodology and level-based roadmap, weekly assignments, masterclasses, recorded lessons and progress "
    "reports. Its free video explains how a child can gain 300 rating points in 3 months with the right training.")

HONESTY = (
    "HONESTY RULES (non-negotiable): never invent students, testimonials, names, ages, ratings or results; never "
    "promise or guarantee a specific result to the viewer. Talk about patterns coaches see, typical mistakes and how "
    "training works. Only mention a concrete student result if it is listed under REAL CASES below, exactly as written. "
    "Never show or describe real, identifiable children. No brands other than ChessTalentsFactory. Never name any "
    "coach or person and never mention or quote any book: the academy and its method are the protagonists. Never call "
    "the academy 'high-performance' or 'high performance training': it is simply ChessTalentsFactory.")


def bible():
    """The brand bible (brand_bible.md), read fresh every run so edits apply to the next reel."""
    try:
        txt = open(os.path.join(HERE, "brand_bible.md")).read()
        return re.sub(r"<!--.*?-->", "", txt, flags=re.S).strip()
    except Exception:
        return ""


# Words that prove a reel is OURS (the competitor test). At least one must appear in every script.
ANCHOR_TERMS = ["our method", "our coaches", "at chesstalentsfactory", "6 levels", "six levels", "meta-chess", "t-t-p", "tripartite", "tactics, theory", "learning path",
                "the basics", "the strategist", "the competitor", "the expert", "candidate master", "master & beyond",
                "study thesis", "technical diagnosis", "deliberate practice", "macrocycle", "microcycle",
                "ninety-minute", "90-minute", "international master", "fide trainer",
                "our students", "one of our students", "world champion", "pan-american", "national master",
                "progress report", "chesstalentsfactory"]


def cases_text():
    """Real, permission-approved cases written by the owner in cases.json (empty by default)."""
    try:
        cases = [c for c in json.load(open(os.path.join(HERE, "cases.json"))) if c.get("approved")]
    except Exception:
        cases = []
    if not cases:
        return "REAL CASES: none available -> do not mention any specific student result."
    return "REAL CASES (approved by the families, anonymous, use at most one, exactly as written):\n" + "\n".join(
        f"- {c['text']}" for c in cases)


def narrator_text():
    if False and NARRATOR == "coach":
        return (f"NARRATOR: {COACH} himself, first person ('I', 'my students'), calm, confident, warm, direct, like a top "
                "coach giving a parent a straight answer in a hallway at a tournament.")
    return (f"NARRATOR: the voice of {NAME} ('we', 'our coaches', 'our students'), calm, confident, warm and direct, like "
            "a top coach giving a parent a straight answer. Never mention any coach by name and never cite a book.")


# Voice actor direction (Gemini TTS)
VOICE_STYLE = ("You are the narrator of short videos for a premium chess academy, talking to parents. Sound like a real, "
               "trusted expert talking to one parent: warm, calm confidence, natural pace and pitch, slight smile, relaxed "
               "breathing. Never robotic, never a hype announcer, never salesy.")

# ---------------------------------------------------------------- call to action (spoken + on screen + caption)
CTA = {
    "vsl": dict(
        say="Parents, want to see how your child could gain three hundred rating points in three months? "
            "Watch our free video. The link is in our bio.",
        pills=["FREE VIDEO FOR PARENTS", "+300 RATING IN 3 MONTHS"],
        url=lambda: url_display(CTA_URL),
        caption="Parents: watch our free video on how your child can gain 300 rating points in 3 months. Link in bio."),
    "call": dict(
        say="Parents, want a clear training plan for your child? Book a call with our coaches. The link is in our bio.",
        pills=["BOOK A CALL WITH OUR COACHES", "SMALL GROUPS - INTERNATIONAL MASTERS"],
        url=lambda: url_display(BOOK_URL),
        caption="Parents: book a call with our coaches and get a clear training plan for your child. Link in bio."),
    "keyword": dict(
        say=f"Parents, comment the word {KEYWORD.lower()}, and we'll send you our free training video.",
        pills=[f'COMMENT "{KEYWORD}"', "FREE TRAINING VIDEO FOR PARENTS"],
        url=lambda: f'Comment "{KEYWORD}"',
        caption=f'Parents: comment "{KEYWORD}" and we\'ll send you our free training video by DM.'),
    "comment": dict(
        say="Does this sound like your child? Tell us in the comments, and follow us for new tips for chess parents.",
        pills=["TELL US IN THE COMMENTS", "FOLLOW FOR TIPS FOR CHESS PARENTS"],
        url=lambda: "@" + IG_HANDLE,
        caption=f"Does this sound like your child? Tell us in the comments. Follow @{IG_HANDLE} for new tips for chess "
                "parents. Free training video for parents in bio."),
}


def cta(kind):
    return CTA.get(kind) or CTA["vsl"]


# Facts the AI may use freely (true by definition of the offer). Anything else about results needs claims.json.
FACTS = ["International Masters", "FIDE Trainer", "T-T-P training system", "90-minute classes",
         "6-level Learning Path", "Quarterly progress reports", "Technical diagnosis first",
         "Small groups of 2-6", "Private 1-on-1 lessons", "Level-based roadmap",
         "Weekly assignments", "Recorded lessons", "Masterclasses", "Progress reports", "Kids of the same level",
         "15 years of coaching"]

PARENT_LINE = (f"{NAME}: online chess academy for kids. Small groups and private lessons with International "
               "Masters.")

TAGS = ["chess", "chessparenting", "chesstraining", "chesscoach", "chesslessons", "chesskids", "kidschess",
        "scholasticchess", "chessparents", "chessforkids", "chesstactics", "chessacademy", "uschess", "learnchess",
        "chesstournament", "chessimprovement"]


def hashtags(rng):
    return ["#" + t for t in rng.sample(TAGS, rng.randint(3, 5))]


YT_TAGS = ["chess", "chess coaching", "chess lessons for kids", "chess coach", "chesstalentsfactory"]


# ---------------------------------------------------------------- logo
def logo_card(width=620, pad=36):
    """Logo on a white rounded card: readable on dark, orange or busy backgrounds."""
    from PIL import Image, ImageDraw, ImageFilter
    lg = logo(width - 2 * pad)
    w, h = lg.width + 2 * pad, lg.height + 2 * pad
    out = Image.new("RGBA", (w + 40, h + 50), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([20, 30, 20 + w, 30 + h], radius=h // 3, fill=(0, 0, 0, 90))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
    ImageDraw.Draw(out).rounded_rectangle([20, 20, 20 + w, 20 + h], radius=h // 3, fill=(255, 255, 255, 255))
    out.alpha_composite(lg, (20 + pad, 20 + pad))
    return out


def logo(width=620):
    """assets/logo_h.png if present (put the real logo there), otherwise a clean wordmark."""
    from PIL import Image, ImageDraw, ImageFont
    p = os.path.join(HERE, "assets", "logo_h.png")
    if os.path.exists(p):
        lg = Image.open(p).convert("RGBA"); lg = lg.crop(lg.getbbox() or (0, 0, lg.width, lg.height))
        return lg.resize((width, int(lg.height * width / lg.width)), Image.LANCZOS)
    f = os.path.join(HERE, "fonts", "Nunito-900.ttf")
    a, b = "ChessTalents", "Factory"
    size = 120
    fo = ImageFont.truetype(f, size)
    wa, wb = fo.getlength(a), fo.getlength(b)
    im = Image.new("RGBA", (int(wa + wb) + 20, int(size * 1.35)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((0, 0), a, font=fo, fill=INK); d.text((wa + 8, 0), b, font=fo, fill=ORANGE)
    im = im.crop(im.getbbox())
    return im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)
