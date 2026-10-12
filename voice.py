"""Narration voice for all reels.

Engine order (automatic, never blocks a reel):
  1. Gemini TTS (very natural, takes acting directions) when GEMINI_API_KEY is set.
     Story narration is recorded in ONE take so the intonation flows like a real narrator,
     then split into scenes at the natural pauses.
  2. Chatterbox (open source) if VOICE_ENGINE=chatterbox and its venv exists.
  3. Kokoro (local) as last resort.
"""
import base64, json, os, re, subprocess, tempfile, time
import numpy as np
import requests
import soundfile as sf
import make_reel as R

SR = 24000
HERE = os.path.dirname(os.path.abspath(__file__))
KOKORO_VOICE = os.environ.get("HYPE_VOICE", "am_fenrir")
CB_PY = os.environ.get("CHATTERBOX_PY", os.path.join(HERE, ".venv-cb", "bin", "python"))
REF_LINE = ("Most kids don't lose games because of openings. They lose because they move too fast. "
            "So take a breath, and look at the whole board.")

GEMINI_VOICE = os.environ.get("GEMINI_VOICE", "Fenrir")
API = "https://generativelanguage.googleapis.com/v1beta"
TTS_PREFERRED = ["gemini-3.8-flash-tts", "gemini-3.8-flash-tts-preview", "gemini-3.1-flash-tts-preview",
                 "gemini-3.1-flash-tts", "gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"]
import brand
NARRATOR = brand.VOICE_STYLE
ENGINE_USED = None
LOCK = None          # engine chosen for the current reel: every line of one reel uses the same voice


class VoiceError(RuntimeError):
    """The engine locked for this reel failed; the caller must redo the whole reel with another engine."""


def reset(force=None):
    """Call at the start of every reel. force: None (best available), 'local' (no Gemini) or 'kokoro'."""
    global LOCK
    LOCK = force


# ------------------------------------------------------------------ speech recognition (captions + checks)
_asr_model, _asr_cache = None, {}


import threading
_asr_lock = threading.Lock()


def _asr(a):
    with _asr_lock:
        return _asr_inner(a)


def _asr_inner(a):
    """[(word, start_s, end_s)] heard in a 24 kHz clip, or None if speech recognition is unavailable."""
    global _asr_model
    k = (len(a), round(float(np.sum(np.abs(a[::97]))), 3))
    if k in _asr_cache:
        return _asr_cache[k]
    if _asr_model is False:
        return None
    try:
        if _asr_model is None:
            from faster_whisper import WhisperModel
            _asr_model = WhisperModel(os.environ.get("ASR_MODEL", "base.en"), device="cpu", compute_type="int8")
        a16 = np.interp(np.linspace(0, len(a) - 1, int(len(a) * 16000 / SR)), np.arange(len(a)), a).astype(np.float32)
        segs, _ = _asr_model.transcribe(a16, language="en", beam_size=1, word_timestamps=True, vad_filter=False)
        out = [(w.word.strip(), float(w.start), float(w.end)) for sg in segs for w in (sg.words or []) if w.word.strip()]
    except Exception as e:
        print("voice: speech recognition unavailable:", str(e)[:150], flush=True)
        _asr_model = False
        return None
    _asr_cache[k] = out
    return out


def _norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen " \
        "seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _num_words(n):
    if n < 20: return _ONES[n]
    if n < 100: return _TENS[n // 10] + ("" if n % 10 == 0 else _ONES[n % 10])
    if n < 1000: return _ONES[n // 100] + "hundred" + ("" if n % 100 == 0 else _num_words(n % 100))
    if n < 10000: return _ONES[n // 1000] + "thousand" + ("" if n % 1000 == 0 else _num_words(n % 1000))
    return str(n)


def _spoken(text):
    """Letters-only spoken form, so 'H6' == 'H six', '300' == 'three hundred', 'Rook takes h6' == 'Rook takes H six'."""
    t = text.lower().replace("%", " percent").replace("&", " and ")
    t = re.sub(r"\d+", lambda m: " " + _num_words(int(m.group())) + " ", t)
    return re.sub(r"[^a-z]", "", t)


def _similarity(a, text):
    """0..1 how well the audio says the text (None when we cannot check). Compared letter by letter on the
    spoken form, so notation, numbers and punctuation written differently by the recogniser do not count."""
    heard = _asr(a)
    if heard is None:
        return None
    import difflib
    x, y = _spoken(text), _spoken(" ".join(w for w, _, _ in heard))
    if not x or not y:
        return 0.0
    return difflib.SequenceMatcher(None, x, y, autojunk=False).ratio()


def align(a, text):
    """Word timings for captions: [(t_seconds, word)] matching what is actually heard in the clip."""
    ws = text.split()
    heard = _asr(a)
    if heard:
        import difflib
        sm = difflib.SequenceMatcher(None, [_norm(w) for w in ws], [_norm(w) for w, _, _ in heard])
        if _similarity(a, text) < 0.6:                         # voice said something else: show what it said
            return [(st, w) for w, st, _ in heard]
        t = [None] * len(ws)
        for i, j, n in sm.get_matching_blocks():
            for d in range(n):
                t[i + d] = heard[j + d][1]
        dur = len(a) / SR
        known = [(i, v) for i, v in enumerate(t) if v is not None]
        xs = [-1] + [i for i, _ in known] + [len(ws)]
        ys = [0.0] + [v for _, v in known] + [dur * 0.95]
        t = list(np.interp(range(len(ws)), xs, ys))
        for i in range(1, len(t)):                             # keep order
            t[i] = max(t[i], t[i - 1] + 0.05)
        return list(zip(t, ws))
    L = sum(len(w) + 1 for w in ws); acc = 0; out = []        # fallback: proportional to characters
    for w in ws:
        out.append(((len(a) / SR) * acc / L * 0.95, w)); acc += len(w) + 1
    return out



# ------------------------------------------------------------------ take verification (no stray words, ever)
# Words that only appear when the model reads our prompt aloud ("Read aloud in a calm voice, only the words after the
# colon...", "Paragraph 2: warm"). If any of them is heard and is not in the script, the take is thrown away.
LEAK_STRONG = {"aloud", "transcript", "colon", "paragraph", "paragraphs", "director", "directors", "delivery",
               "instructions", "instruction", "narrator", "prompt"}
LEAK_SOFT = {"read", "reads", "voice", "perform", "pace", "brisk", "tone", "words", "quote", "unquote"}


def _num_tokens(n):
    if n < 20: return [_ONES[n]]
    if n < 100: return [_TENS[n // 10]] + ([] if n % 10 == 0 else [_ONES[n % 10]])
    if n < 1000: return [_ONES[n // 100], "hundred"] + ([] if n % 100 == 0 else _num_tokens(n % 100))
    if n < 10000: return [_ONES[n // 1000], "thousand"] + ([] if n % 1000 == 0 else _num_tokens(n % 1000))
    return [str(n)]


def _tokens(word):
    """Spoken tokens of one written word: '300' -> three hundred, '90-minute' -> ninety minute, 'T-T-P' -> t t p."""
    w = word.lower().replace("%", " percent").replace("&", " and ")
    out = []
    for part in re.split(r"[^a-z0-9']+", w):
        part = part.strip("'")
        if not part:
            continue
        for chunk in re.findall(r"\d+|[a-z']+", part):
            out += _num_tokens(int(chunk)) if chunk.isdigit() else [chunk.replace("'", "")]
    return [t for t in out if t]


def verify_take(a, text):
    """Checks a recorded take against its script with speech recognition.
    Returns (clean_audio, ok, reason). clean_audio is cropped to exactly the script's words (anything the model said
    before or after - an instruction, a breath of static, a garbled tail - is cut), with gentle fades.
    When speech recognition is unavailable returns (a, None, 'unverified')."""
    heard = _asr(a)
    if heard is None:
        return a, None, "unverified"
    if not heard:
        return a, False, "no speech heard"
    st = [t for w in text.split() for t in _tokens(w)]
    ht, hidx = [], []
    for k, (w, _, _) in enumerate(heard):
        for t in _tokens(w):
            ht.append(t); hidx.append(k)
    if not st or not ht:
        return a, False, "empty"
    import difflib
    sm = difflib.SequenceMatcher(None, st, ht, autojunk=False)
    matched = set()
    for i, j, n in sm.get_matching_blocks():
        matched.update(range(j, j + n))
    if not matched:
        return a, False, "nothing matches the script"
    coverage = sum(n for _, _, n in sm.get_matching_blocks()) / len(st)
    j0, j1 = min(matched), max(matched)
    inside_extra = [ht[j] for j in range(j0, j1 + 1) if j not in matched]
    script_set = set(st)
    leaked = [t for t in ht if t not in script_set and t in LEAK_STRONG]
    soft = [t for t in ht if t not in script_set and t in LEAK_SOFT]
    reason = f"coverage {coverage:.2f}, {len(inside_extra)} extra word(s) inside"
    if leaked or len(soft) >= 3:
        return a, False, f"read instructions aloud ({' '.join((leaked + soft)[:6])})"
    if coverage < 0.8:
        return a, False, reason
    if len(inside_extra) > max(2, int(0.12 * len(st))):
        return a, False, reason + f": {' '.join(inside_extra[:6])}"
    w0, w1 = hidx[j0], hidx[j1]
    a0 = int(max(0.0, heard[w0][1] - 0.10) * SR)
    a1 = int(min(len(a) / SR, heard[w1][2] + 0.24) * SR)
    out = a[a0:a1].copy()
    if a0 or a1 < len(a):
        dropped = [w for k, (w, _, _) in enumerate(heard) if k < w0 or k > w1]
        if dropped:
            print(f"voice: cut words outside the script {dropped[:8]} from {text[:40]!r}", flush=True)
        _asr_cache.clear()
    # silence the gaps between words (removes hiss, clicks and breaths in long pauses; words untouched)
    words = [(s - a0 / SR, e - a0 / SR) for k, (_, s, e) in enumerate(heard) if w0 <= k <= w1]
    out = _gate_gaps(out, words)
    return fade(out), True, reason


def _gate_gaps(a, words, min_gap=0.34, pre=0.07, post=0.16, ramp=0.025):
    """Fade to digital silence inside pauses longer than min_gap (between recognised words)."""
    if len(words) < 2:
        return a
    g = np.ones(len(a), np.float32)
    r = max(1, int(ramp * SR))
    for (_, e), (s, _) in zip(words[:-1], words[1:]):
        if s - e < min_gap:
            continue
        x0, x1 = int((e + post) * SR), int((s - pre) * SR)
        if x1 - x0 < 2 * r:
            continue
        g[x0:x0 + r] = np.minimum(g[x0:x0 + r], np.linspace(1, 0, r))
        g[x0 + r:x1 - r] = 0
        g[x1 - r:x1] = np.minimum(g[x1 - r:x1], np.linspace(0, 1, r))
    return (a * g).astype(np.float32)


def energy_gate(a, floor_db=-42.0):
    """Without speech recognition: smooth downward gate for anything far below the speech level."""
    if len(a) < SR // 10:
        return a
    hop = int(SR * 0.01)
    env = np.sqrt(np.convolve(a.astype(np.float64) ** 2, np.ones(hop * 2) / (hop * 2), "same"))
    ref = np.percentile(env, 95) + 1e-9
    db = 20 * np.log10(env / ref + 1e-9)
    g = np.clip((db - floor_db) / 8.0, 0, 1)
    k = int(0.03 * SR)
    g = np.convolve(g, np.ones(k) / k, "same")
    return (a * g).astype(np.float32)


def fade(a, fin=0.012, fout=0.045):
    """Short fades at both ends: a clip that starts or stops abruptly sounds like a click / burst of noise."""
    a = a.astype(np.float32).copy()
    n_in, n_out = min(len(a) // 4, int(fin * SR)), min(len(a) // 4, int(fout * SR))
    if n_in > 1:
        a[:n_in] *= np.linspace(0, 1, n_in) ** 2
    if n_out > 1:
        a[-n_out:] *= np.linspace(1, 0, n_out) ** 2
    return a


# ------------------------------------------------------------------ helpers
def _trim(a):
    if len(a) == 0:
        return a
    thr = max(0.01, 0.04 * float(np.max(np.abs(a))))
    nz = np.nonzero(np.abs(a) > thr)[0]
    return a[max(0, nz[0] - 240): nz[-1] + 1600] if len(nz) else a


def _tighten(a, max_gap=0.32):
    """Shorten long internal silences (dramatic pauses, breaths) so short lines stay short."""
    hop = int(SR * 0.01)
    if len(a) < hop * 10:
        return a
    env = np.sqrt(np.convolve(a ** 2, np.ones(hop * 3) / (hop * 3), "same"))[::hop]
    quiet = env < max(0.01, 0.05 * np.percentile(env, 95))
    keep = np.ones(len(a), bool); i = 0; mg = int(max_gap * 100)
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]: j += 1
            if j - i > mg:
                keep[(i + mg // 2) * hop:(j - mg // 2) * hop] = False
            i = j
        else:
            i += 1
    return a[keep]


def polish(a, light=False):
    """Gentle cleanup: high-pass ~80 Hz, short fades, level. No exciter or saturation (they made hiss audible)."""
    a = a.astype(np.float32)
    if len(a) < 10:
        return a
    k = int(SR / 80)
    a = a - np.convolve(a, np.ones(k) / k, "same")                                    # high-pass ~80 Hz
    if not light:                                                                     # local engines: gate the room
        a = energy_gate(a)
    a = fade(a)
    tail = np.zeros(int(SR * 0.1), np.float32)
    out = np.concatenate([a, tail])
    return (out / (np.max(np.abs(out)) + 1e-6) * 0.9).astype(np.float32)


def _resample(a, sr):
    if sr == SR:
        return a.astype(np.float32)
    n = int(len(a) * SR / sr)
    return np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)


def _words(t):
    return max(1, len(re.findall(r"[A-Za-z0-9']+", t)))


# ------------------------------------------------------------------ Gemini TTS
_models = None


def _tts_models(key):
    global _models
    if _models is not None:
        return _models
    found = []
    try:
        r = requests.get(f"{API}/models", params={"key": key, "pageSize": 200}, timeout=30)
        for m in r.json().get("models", []):
            n = m["name"].split("/")[-1]
            if "tts" in n and "generateContent" in m.get("supportedGenerationMethods", []):
                found.append(n)
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Gemini unreachable: {e}")
    except Exception as e:
        print("voice: could not list models:", e, flush=True)
    env = os.environ.get("GEMINI_TTS_MODEL")
    order = ([env] if env else []) + [m for m in TTS_PREFERRED if not found or m in found]

    def rank(n):  # newest flash (not lite) first
        v = re.findall(r"(\d+(?:\.\d+)?)", n)
        return (-float(v[0]) if v else 0, "lite" in n, "pro" in n, "preview" in n)
    order += sorted([m for m in found if m not in order], key=rank)
    _models = list(dict.fromkeys(order))
    return _models


_TTS_DEAD = set()


def _gemini_call(prompt, key):
    """Gemini TTS. Daily quota / retired model -> skip that model for the rest of the run (fast fallback to the
    next model or to the free local voice instead of waiting minutes)."""
    from make_story import _retry_delay
    last = None
    for model in [m for m in _tts_models(key) if m not in _TTS_DEAD][:3]:
        for attempt in range(3):
            try:
                r = requests.post(f"{API}/models/{model}:generateContent", headers={"x-goog-api-key": key},
                                  timeout=150, json={
                                      "contents": [{"parts": [{"text": prompt}]}],
                                      "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                                          "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": GEMINI_VOICE}}}}})
                if r.status_code == 429:
                    delay, daily = _retry_delay(r)
                    last = RuntimeError(f"{model} 429{' daily quota' if daily else ''}")
                    if daily or (delay and delay > 70):
                        _TTS_DEAD.add(model); break
                    time.sleep(min(delay or 15, 45) + 1); continue
                if r.status_code in (500, 502, 503, 504):
                    last = RuntimeError(f"{model} {r.status_code}"); time.sleep(6 * (attempt + 1)); continue
                if r.status_code != 200:
                    last = RuntimeError(f"{model} {r.status_code}: {r.text[:200]}")
                    if r.status_code in (400, 403, 404):
                        _TTS_DEAD.add(model)
                    break
                for p in r.json()["candidates"][0]["content"]["parts"]:
                    d = p.get("inlineData") or p.get("inline_data")
                    if d:
                        mime = d.get("mimeType") or d.get("mime_type") or ""
                        rate = int((re.findall(r"rate=(\d+)", mime) or [24000])[0])
                        pcm = np.frombuffer(base64.b64decode(d["data"]), dtype="<i2").astype(np.float32) / 32768
                        return _resample(pcm, rate)
                last = RuntimeError(f"{model}: no audio in response"); break
            except requests.exceptions.ConnectionError as e:
                raise RuntimeError(f"Gemini unreachable: {e}")
            except Exception as e:
                last = e; time.sleep(4)
    if not [m for m in _tts_models(key) if m not in _TTS_DEAD]:
        raise RuntimeError("no Gemini TTS model available (daily quota exhausted)")
    raise last or RuntimeError("no Gemini TTS model available")


def _ratio(audio, text):
    return (len(audio) / SR) / (_words(text) / 2.7 + 0.6)


def _sane(audio, text, factor=2.6):
    """Reject takes where the model read the stage directions aloud or cut the line."""
    r = _ratio(audio, text)
    return 0.3 < r < factor


def _strip_extras(a, text):
    """Cut words the model added before/after the script (e.g. it read 'Say' or a stage direction aloud).
    Uses the recogniser's word timings; returns the audio unchanged when it cannot check."""
    heard = _asr(a)
    if not heard:
        return a
    ws = [_norm(w) for w in text.split() if _norm(w)]
    hw = [_norm(w) for w, _, _ in heard]
    if not ws:
        return a
    def match(x, y):
        return x == y or (len(x) > 3 and len(y) > 3 and (x.startswith(y[:4]) or y.startswith(x[:4])))
    start = next((j for j in range(min(4, len(hw))) if match(hw[j], ws[0]) or
                  (len(ws) > 1 and j + 1 < len(hw) and match(hw[j + 1], ws[1]) and j > 0 and hw[j] in ("say", "says", "said"))), 0)
    if start and hw[start] in ("say", "says", "said") and not match(hw[start], ws[0]):
        start += 1
    end = len(hw) - 1
    for j in range(len(hw) - 1, max(-1, len(hw) - 5), -1):
        if match(hw[j], ws[-1]):
            end = j; break
    a0 = int(max(0, heard[start][1] - 0.06) * SR) if start > 0 else 0
    a1 = int(min(len(a) / SR, heard[end][2] + 0.18) * SR) if end < len(hw) - 1 else len(a)
    if a0 or a1 < len(a):
        print(f"voice: trimmed extra words {hw[:start]} {hw[end + 1:]} from {text[:40]!r}", flush=True)
        _asr_cache.clear()
        return a[a0:a1]
    return a


def _gemini_line(text, style, key, pace):
    """Records one line. Every take is checked word by word with speech recognition and cropped to exactly the
    script; a take where the model says anything else (e.g. reads our directions aloud) is thrown away.
    Never publishes an unverified take with instructions in the prompt: without speech recognition only the bare
    script is sent to the model, so there is nothing it could read aloud."""
    verifiable = _asr(np.zeros(SR // 2, np.float32)) is not None
    styled = (f"{NARRATOR} Style: {style or 'natural and engaging'}, {pace}.\n"
              f"Say only the text between the quotation marks, word for word, and nothing else:\n\"{text}\"")
    prompts = [styled, text, text] if verifiable else [text, text]
    last = "no take"
    for pr in prompts:
        try:
            raw = _trim(_gemini_call(pr, key))
        except Exception as e:
            if "unreachable" in str(e) or "no Gemini TTS" in str(e):
                raise
            print("voice: take error:", str(e)[:150], flush=True); continue
        a, ok, why = verify_take(raw, text)
        if ok is None:                               # cannot verify: bare script only, length sanity check
            if pr == text and _sane(a, text):
                return _tighten(fade(a))
            last = "unverified take"; continue
        if ok and _sane(a, text, 3.0):
            return _tighten(a)
        last = why
        print(f"voice: retake {text[:50]!r}: {why}", flush=True)
    raise RuntimeError(f"bad take for {text[:60]!r}: {last}")


def _split_takes(a, texts):
    """Split one continuous take into len(texts) pieces at the longest natural pauses, then verify each piece."""
    n = len(texts)
    if n == 1:
        p, ok, why = verify_take(a, texts[0])
        if not ok:
            raise RuntimeError(why)
        return [p]
    hop = int(SR * 0.01)
    env = np.sqrt(np.convolve(a ** 2, np.ones(hop * 3) / (hop * 3), "same"))[::hop]
    thr = max(0.012, 0.06 * np.percentile(env, 95))
    silent = env < thr
    runs, i = [], 0
    while i < len(silent):
        if silent[i]:
            j = i
            while j < len(silent) and silent[j]: j += 1
            if j - i >= 12 and i > 20 and j < len(silent) - 20:     # >=120 ms, not at the edges
                runs.append((j - i, (i + j) // 2))
            i = j
        else:
            i += 1
    w = np.array([_words(t) for t in texts], float)
    exp_cuts = np.cumsum(w)[:-1] / w.sum() * len(env)
    cuts, used = [], set()
    for ec in exp_cuts:
        cands = [(ln, c) for ln, c in runs if c not in used and abs(c - ec) < 0.22 * len(env)]
        if not cands:
            raise RuntimeError("no pause found to split the take")
        ln, c = max(cands, key=lambda x: x[0] - 0.02 * abs(x[1] - ec))
        cuts.append(c); used.add(c)
    if cuts != sorted(cuts):
        raise RuntimeError("pauses out of order")
    edges = [0] + [c * hop for c in cuts] + [len(a)]
    parts = []
    for k in range(n):
        p, ok, why = verify_take(_trim(a[edges[k]:edges[k + 1]]), texts[k])
        if not ok or not _sane(p, texts[k], 3.2):
            raise RuntimeError(f"piece {k + 1} does not match its text ({why})")
        parts.append(_tighten(p))
    return parts


def _gemini_many(texts, styles, key, one_take, pace):
    verifiable = _asr(np.zeros(SR // 2, np.float32)) is not None
    if one_take and len(texts) > 1 and verifiable:       # a single take is only used when we can check every word
        try:
            script = "\n\n".join(texts)
            mood = ", ".join(dict.fromkeys(s for s in styles if s)) or "warm and natural"
            prompt = (f"{NARRATOR} Style: {mood}, {pace}, a clear breath pause between paragraphs.\n"
                      f"Say only the text between the quotation marks, word for word, and nothing else:\n\"{script}\"")
            take = _trim(_gemini_call(prompt, key))
            print(f"voice: one take {len(take) / SR:.1f}s for {sum(_words(t) for t in texts)} words", flush=True)
            full, ok, why = verify_take(take, " ".join(texts))         # crop anything said before/after the script
            if not ok:
                raise RuntimeError(f"one take rejected: {why}")
            return _split_takes(full, texts)
        except Exception as e:
            if "unreachable" in str(e) or "no Gemini TTS" in str(e):
                raise
            print("voice: one-take narration failed, recording line by line:", str(e)[:200], flush=True)
    from concurrent.futures import ThreadPoolExecutor        # 3 lines recorded at the same time
    with ThreadPoolExecutor(3) as ex:
        return list(ex.map(lambda ts: _gemini_line(ts[0], ts[1], key, pace), zip(texts, styles)))


# ------------------------------------------------------------------ local engines
def _kokoro(text, speed=1.08):
    return _trim(R.tts(text, voice=KOKORO_VOICE, speed=speed))


CB_SCRIPT = r'''
import json, sys, torch, torchaudio
from chatterbox.tts import ChatterboxTTS
job = json.load(open(sys.argv[1]))
m = ChatterboxTTS.from_pretrained(device="cpu")
for i, t in enumerate(job["texts"]):
    w = m.generate(t, audio_prompt_path=job["ref"], exaggeration=job["exag"], cfg_weight=job["cfg"])
    torchaudio.save(f"{job['dir']}/{i}.wav", w, m.sr)
print("ok")
'''


def _chatterbox_batch(texts):
    d = tempfile.mkdtemp()
    ref = os.path.join(d, "ref.wav")
    sf.write(ref, _kokoro(REF_LINE, 1.0), SR)
    job = os.path.join(d, "job.json"); scr = os.path.join(d, "cb.py")
    json.dump({"texts": texts, "ref": ref, "dir": d, "exag": float(os.environ.get("VOICE_EXAG", "0.65")),
               "cfg": float(os.environ.get("VOICE_CFG", "0.45"))}, open(job, "w"))
    open(scr, "w").write(CB_SCRIPT)
    r = subprocess.run([CB_PY, scr, job], capture_output=True, text=True, timeout=1500)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-800:])
    outs = []
    for i in range(len(texts)):
        a, sr = sf.read(os.path.join(d, f"{i}.wav"), dtype="float32")
        if a.ndim > 1: a = a.mean(1)
        outs.append(_trim(_resample(a, sr)))
    return outs


# ------------------------------------------------------------------ public
def say_many(texts, speed=1.08, styles=None, one_take=False):
    """Returns a list of float32 arrays at 24 kHz, one per text.
    styles: optional acting direction per line ("hushed, suspenseful"...).
    one_take: record all lines as one continuous performance (used for the story narration).
    All calls inside one reel use the same engine (see reset/LOCK); if that engine fails later in the
    reel, VoiceError is raised so the caller can redo the reel with a single consistent voice."""
    global ENGINE_USED, LOCK
    texts = [t.replace("3%", "three percent") for t in texts]
    styles = list(styles or [None] * len(texts))
    pace = "a lively, brisk pace" if speed >= 1.1 else "a relaxed but energetic pace"
    key = os.environ.get("GEMINI_API_KEY")
    engine = os.environ.get("VOICE_ENGINE", "gemini").lower()
    allow_gemini = (key and engine in ("gemini", "auto", "chatterbox") and os.environ.get("VOICE_NO_GEMINI") != "1"
                    and LOCK in (None, "gemini"))
    allow_cb = os.path.exists(CB_PY) and engine != "kokoro" and LOCK in (None, "local", "chatterbox")
    if allow_gemini:
        try:
            clips = _gemini_many(texts, styles, key, one_take, pace)
            ENGINE_USED = LOCK = "gemini"
            print(f"voice: gemini {GEMINI_VOICE} ({len(texts)} lines, one_take={one_take})", flush=True)
            return [polish(c, light=True) for c in clips]
        except Exception as e:
            if LOCK == "gemini":
                raise VoiceError(f"gemini failed mid-reel: {str(e)[-200:]}")
            print("voice: gemini failed, trying local voices:", str(e)[-300:], flush=True)
    if allow_cb:
        try:
            clips = _chatterbox_batch(texts); ENGINE_USED = LOCK = "chatterbox"
            print(f"voice: chatterbox ({len(texts)} lines)", flush=True)
            return [polish(c) for c in clips]
        except Exception as e:
            if LOCK == "chatterbox":
                raise VoiceError(f"chatterbox failed mid-reel: {str(e)[-200:]}")
            print("voice: chatterbox failed, using kokoro:", str(e)[-300:], flush=True)
    if LOCK not in (None, "local", "kokoro"):
        raise VoiceError(f"{LOCK} not available")
    clips = [_kokoro(t, speed) for t in texts]; ENGINE_USED = LOCK = "kokoro"
    print(f"voice: kokoro ({len(texts)} lines)", flush=True)
    return [polish(c) for c in clips]


def next_engine():
    """Engine to force after a VoiceError."""
    return {"gemini": "local", "chatterbox": "kokoro"}.get(LOCK, "kokoro")
