"""Parent + child challenge reels: "Can your child find the winning move?"

A real puzzle (Lichess puzzle database, CC0, at a level young players can solve; or a built-in verified set),
a calm countdown so the parent can pause and hand the phone to their child, then the answer animated on the board.
No narrator. Comments are the goal: families answer under the reel.

python make_challenge.py  -> out/test_challenge.mp4 (built-in puzzle, no download)
"""
import json, os, random, sys
import numpy as np
from PIL import Image

import brand
import formats as F

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SR = F.W, F.H, F.FPS, F.SR
FALLBACK = os.path.join(HERE, "puzzles_fallback.json")
BOARD = 880
COUNT = 8.0

HOOKS = ["Can your child find the winning move?", "Show this to your child. Can they find it?",
         "Only one move wins here. Can your child see it?", "Quick test for your chess kid. One move wins."]
AFTER = [("Found it? That's how strong players see the board.", ["strong"]),
         ("Missed it? Patterns like this are trained, not born.", ["trained"]),
         ("Kids who solve a few of these daily start seeing them in games.", ["daily"])]
CAP_HOOKS = ["Can your child find the winning move? Answer in the comments 👇",
             "Show this to your child. Did they find it? 👇",
             "One move wins. Can your child spot it? ♟️"]


def get_puzzle(seed):
    """Lichess puzzle (basic/intermediate) when the database is available, else the verified built-in set."""
    if os.environ.get("CHALLENGE_SOURCE", "lichess") == "lichess":
        try:
            import pick_puzzles
            level = random.Random(seed).choice(["basic", "basic", "intermediate"])
            p = pick_puzzles.pick(level, seed=seed)
            moves = p["moves"].split()
            pick_puzzles.mark_used(p["id"])
            return {"id": p["id"], "fen": p["fen"], "setup": moves[0], "solution": moves[1:], "rating": p["rating"],
                    "themes": p["themes"], "source": "lichess"}
        except BaseException as e:                          # pick() may SystemExit when nothing is left
            print("challenge: puzzle database unavailable, using built-in set:", str(e)[:150], flush=True)
    lib = json.load(open(FALLBACK))
    used = {r.get("puzzle"): i for i, r in enumerate(F.recent(400)) if r.get("puzzle")}
    p = min(lib, key=lambda x: (used.get(x["id"], -1), random.Random(seed).random()))
    return dict(p, source="built-in")


def goal_text(p, board):
    th = p.get("themes", "").split()
    side = "White" if board.turn else "Black"
    for n in (1, 2, 3, 4):
        if f"mateIn{n}" in th:
            return f"{side} to move · Checkmate in {n}"
    return f"{side} to move · Find the winning move"


def build(seed, out, mock=False):
    import chess
    rng = random.Random(seed)
    p = get_puzzle(seed)
    b0 = chess.Board(p["fen"])
    setup = chess.Move.from_uci(p["setup"]) if p.get("setup") else None
    b1 = b0.copy()
    if setup:
        b1.push(setup)
    sol = [chess.Move.from_uci(m) for m in p["solution"]]
    flip = not b1.turn                                # show the board from the solver's side
    goal = goal_text(p, b1)
    hook = rng.choice(HOOKS)
    after, after_hl = rng.choice(AFTER)
    # timeline
    T_HOOK, T_SETUP = 0.0, 1.1
    T_COUNT = 3.0
    T_ANS = T_COUNT + COUNT + 0.3
    PLY = 1.15
    T_DONE = T_ANS + 0.6 + PLY * len(sol)
    T_AFTER = T_DONE + 1.4
    T_CTA = T_AFTER + 2.9
    total = T_CTA + 4.8
    sq = BOARD // 8
    states = [b1.copy()]
    for m in sol:
        nb = states[-1].copy(); nb.push(m); states.append(nb)
    final_mate = states[-1].is_checkmate()
    goal_im = F.cached(("goal", goal), lambda: _chip(goal))
    hook_cy = 470

    def board_at(t):
        """(board image, centre y offset) at time t."""
        if t < T_SETUP or not setup:
            st, mv, k = (b0 if setup else b1), None, 0
            hl = ()
        elif t < T_SETUP + 0.6:
            st, mv, k = b0, setup, F.ease_in_out((t - T_SETUP) / 0.45)
            hl = (setup.from_square, setup.to_square)
        else:
            st, mv, k = b1, None, 0
            hl = (setup.from_square, setup.to_square)
        arrows = ()
        if t >= T_ANS + 0.6:
            j = min(len(sol) - 1, int((t - T_ANS - 0.6) / PLY))
            lt = t - T_ANS - 0.6 - j * PLY
            st, mv, k = states[j], sol[j], F.ease_in_out(lt / 0.5)
            hl = (sol[j].from_square, sol[j].to_square)
            arrows = ((sol[j].from_square, sol[j].to_square),) if j % 2 == 0 and lt < 0.9 else ()
            if lt >= 0.5:
                st, mv = states[j + 1], None
        if mv is None:
            return F.board_img(st, BOARD, flip, highlight=hl, arrows=arrows)
        im = F.board_img(st, BOARD, flip, highlight=hl, arrows=arrows, hide=(mv.from_square, mv.to_square))
        x0, y0 = F.square_xy(mv.from_square, sq, flip); x1, y1 = F.square_xy(mv.to_square, sq, flip)
        cap = st.piece_at(mv.to_square)
        if cap and k < 0.85:
            im.alpha_composite(F.alpha(F.piece_img(cap.symbol(), sq), 1 - k), (x1, y1))
        pc = st.piece_at(mv.from_square)
        im.alpha_composite(F.piece_img(pc.symbol(), sq), (int(x0 + (x1 - x0) * k), int(y0 + (y1 - y0) * k)))
        return im

    def frames():
        for fi in range(int(total * FPS)):
            t = fi / FPS
            fr = Image.new("RGBA", (W, H))
            if t >= T_CTA:
                F.cta_card(fr, t - T_CTA, seed, total, line="Want puzzles like this at your child's level?")
                yield fr; continue
            F.draw_bg(fr, seed, t, total)
            fr.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 90)))
            # top text area
            if t < T_COUNT:
                lab = F.cached("chl", lambda: F.label("Challenge for chess kids", 32))
                F.paste(fr, lab, W / 2, 300, 1, F.clamp(t / 0.3))
                F.kinetic(fr, hook, ["child", "your"], t, hook_cy, size=80, align="center", out_t=T_COUNT - 0.3, per_word=0.06)
            elif t < T_ANS:
                lt = t - T_COUNT
                F.kinetic(fr, "Pause the video. Let your child try.", ["try"], lt, 360, size=58, align="center",
                          out_t=COUNT + 0.05, per_word=0.04)
                left = max(0.0, COUNT - lt)
                F.paste(fr, _ring(left / COUNT, int(np.ceil(left)) if left > 0 else 0), W / 2, 545, 1,
                        F.clamp(lt / 0.3) * F.clamp((COUNT + 0.3 - lt) / 0.3))
            elif t < T_AFTER:
                lt = t - T_ANS
                lab = F.cached("ans", lambda: F.label("The answer", 40))
                F.paste(fr, lab, W / 2, 380, 1, F.clamp(lt / 0.3))
                if t >= T_DONE:
                    msg = "Checkmate!" if final_mate else "Winning!"
                    im = F.cached(("done", msg), lambda: F.button(msg, 64))
                    F.paste(fr, im, W / 2, 545, 0.85 + 0.15 * F.back((t - T_DONE) / 0.4), F.clamp((t - T_DONE) / 0.2))
            else:
                lt = t - T_AFTER
                F.kinetic(fr, after, after_hl, lt, 480, size=64, align="center", out_t=T_CTA - T_AFTER - 0.25, per_word=0.05)
            # board
            ba = F.clamp((t - 0.5) / 0.5)
            if ba > 0:
                bim = F.framed_board(board_at(t))
                F.paste(fr, bim, W / 2, 1190 + (1 - F.ease_out((t - 0.5) / 0.6)) * 60, 1.0, ba)
                F.paste(fr, goal_im, W / 2, 1190 - BOARD / 2 - 70, 1, ba)
            F.brand_mark(fr, 0.95, y=150)
            F.progress(fr, t, total)
            yield fr

    # sound: music, a gentle tick each second of the countdown, a whoosh-free tonal swell into the answer, a bell
    n = int(total * SR)
    bed, track = F.music(total, seed, energy=0.4)
    mix = bed[:n] * 0.9
    def put(x, at, g=1.0):
        a = int(at * SR); bnd = min(n, a + len(x))
        if 0 <= a < n: mix[a:bnd] += g * x[:bnd - a]
    for k in range(int(COUNT)):
        put(F.soft_tick(1650 if k >= COUNT - 3 else 1350, 0.08), T_COUNT + k)
    put(F.swell(0.7, 0.05), T_ANS - 0.6)
    for j in range(len(sol)):
        put(F.soft_tick(900, 0.07), T_ANS + 0.6 + j * PLY + 0.45)
    put(F.bell(880, 0.12), T_DONE)
    put(F.bell(784, 0.08), T_CTA + 1.0)
    wav = F.write_wav(F.master(mix, target_db=-15.0), out.replace(".mp4", "_a.wav"))
    F.encode(frames(), wav, out)
    os.remove(wav)
    cap_hook = rng.choice(CAP_HOOKS)
    body = "Pause the video, let your child try, then check the answer at the end. Write their move in the comments."
    open(out.replace(".mp4", ".txt"), "w").write(F.caption(cap_hook, body, seed=seed))
    F.remember({"format": "challenge", "puzzle": p["id"], "title": hook, "music": track})
    return {"format": "challenge", "engine": p["source"], "puzzle": p["id"], "rating": p.get("rating"),
            "story": hook, "hook": cap_hook, "headline": hook, "duration": round(total, 1), "music": track,
            "cta": "keyword", "solution": [m.uci() for m in sol]}


def _chip(text):
    from PIL import ImageDraw
    f = F.font(F.F_UI, 40)
    w, h = int(f.getlength(text)) + 64, 76
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w, h], radius=h // 2, fill=(22, 21, 25, 235), outline=(245, 128, 32), width=3)
    d.text((w / 2, h / 2 + 1), text, font=f, fill=F.CREAM, anchor="mm")
    return im


def _ring(frac, num):
    from PIL import ImageDraw
    s = 210
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([10, 10, s - 10, s - 10], fill=(18, 17, 20, 220))
    d.arc([14, 14, s - 14, s - 14], 0, 360, fill=(70, 66, 64), width=10)
    if frac > 0:
        d.arc([14, 14, s - 14, s - 14], -90, -90 + 360 * frac, fill=F.ORANGE, width=10)
    d.text((s / 2, s / 2 + 4), str(num), font=F.font(F.F_BLACK, 92), fill=F.CREAM, anchor="mm")
    return im


if __name__ == "__main__":
    os.environ.setdefault("CHALLENGE_SOURCE", "builtin")
    os.makedirs("out", exist_ok=True)
    print(build(int(sys.argv[1]) if len(sys.argv) > 1 else 11, "out/test_challenge.mp4"))
