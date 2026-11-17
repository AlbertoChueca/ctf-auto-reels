"""Scene blocks for the animated explainer reels. Each block draws ONE idea so the picture shows what the voice says.

A block is a function b(k, t, d, p, sd): k = canvas, t = seconds since the scene started, d = scene duration,
p = params written by the script (validated in make_animated.CATALOG), sd = seed (stable variety between reels).
"""
import math, random
from anim_kit import *


def _cam(k, t, d, z0=1.0, z1=1.06, cx=W / 2, cy=1080, dx=0.0, dy=0.0):
    k.push(); k.camera(lerp(z0, z1, ease(t / max(d, 0.1))), cx, cy, dx, dy)


# ======================================================================= figures at the board
def b_hall(k, t, d, p, sd):
    """Tournament game. mode: focus | rush | freeze | lose | win"""
    mode = p.get("mode", "focus")
    paint_bg(k, "hall", sd % 3); particles(k, t, sd, 10, VIOLET)
    _cam(k, t, d, 1.30, 1.38, 540, 1240, 0, 10)
    floor, ty, u = 1570, 1240, 122
    kid = Person("child", ORANGE, u, 1); hip = (250, 1226)
    opp = Person("child", DIM, 112, -1, accent=MUTED); hip2 = (868, 1230)
    lean, tilt, hand, hand2 = 0.16 + 0.012 * math.sin(t * 2.1), 0.2, None, (430, ty - 8)
    fallen, low, running, opp_a = 0.0, 0.0, 0, 0.8
    J0 = kid.pose(hip, True, lean, tilt)
    if mode == "focus":
        hand = add(J0["head"], (0.5 * u, 0.52 * u)); tilt = 0.24
    elif mode == "rush":
        c = t % 1.25
        reach = ease_out(seg(c, 0.12, 0.26)) - ease(seg(c, 0.7, 1.0))
        hand = lerp2((410, ty - 26), (585, ty - 86), reach); lean = 0.2 + 0.12 * reach; tilt = 0.1
    elif mode == "freeze":
        lean, tilt, low = -0.02, 0.12, 0.55 + 0.45 * pulse(t, 2.2)
        hand = (425 + math.sin(t * 31) * 3, ty - 10)
    elif mode == "lose":
        f = ease(seg(t, 0.45, 1.1)); fallen = f; tilt = 0.2 + 0.62 * f; lean = 0.16 + 0.16 * f; running = 1
        hand = lerp2((430, ty - 10), add(hip, (0.5 * u, 0.3 * u)), f); hand2 = None
    elif mode == "win":
        f = back(seg(t, 0.25, 0.75)); lean = 0.16 - 0.26 * clamp(f); tilt = -0.15 * clamp(f); opp_a = 0.5
        hand = lerp2((430, ty - 10), add(J0["sho"], (0.55 * u, -1.25 * u)), clamp(f))
        hand2 = lerp2((430, ty - 8), add(J0["sho"], (-0.2 * u, -1.3 * u)), clamp(f))
    J = kid.pose(hip, True, lean, tilt, hand, hand2)
    chair(k, hip, u, 1); chair(k, hip2, 112, -1)
    opp.draw(k, opp.pose(hip2, True, 0.1, 0.12, (700, ty - 8)), opp_a, 0.25)
    table(k, 395, 745, ty, floor)
    board_side(k, 540, ty, 250, 1.0, fallen, t)
    chess_clock(k, 692, ty - 14, 36, t, running, low)
    kid.draw(k, J)
    if mode == "rush":
        c = t % 1.25
        if 0.1 < c < 0.5:
            speed_lines(k, J["hand"][0], J["hand"][1], c, ORANGE, 5, 110, 1.0, -1)
        sparks(k, 590, ty - 96, seg(c, 0.26, 0.6), PINK, 8, 18, 80)
    elif mode == "freeze":
        k.circle(692, ty - 32, 70 + 16 * pulse(t, 2.2)); k.neon(PINK, 6, 0.75)
        for i in range(3):
            ph = (t * 0.9 + i * 0.33) % 1
            icon(k, "tear", J["head"][0] + 78 + i * 16, J["head"][1] - 30 + ph * 110, 22, VIOLET, (1 - ph) * 0.9)
    elif mode == "lose":
        ph = seg(t, 1.0, 2.2) % 1
        if t > 1.0:
            icon(k, "tear", J["head"][0] + 62, J["head"][1] + 16 + ((t - 1.0) * 0.8 % 1) * 120, 24, VIOLET, 1 - ((t - 1.0) * 0.8 % 1))
        sparks(k, 515, ty - 60, seg(t, 0.5, 0.95), PINK, 8, 16, 90)
    elif mode == "win":
        for i in range(5):
            ph = (t * 0.7 + i * 0.2) % 1
            icon(k, "star", 150 + i * 190, 900 - ph * 180 + (i % 2) * 60, 44, GOLD, (1 - ph) * clamp(t - 0.4))
    k.pop()


def b_coach(k, t, d, p, sd):
    """A coach reviews the child's game and finds the one thing to fix. mode: find | plan"""
    mode = p.get("mode", "find")
    paint_bg(k, "home", sd % 2); particles(k, t, sd, 8, TEAL)
    if mode == "find":
        _cam(k, t, d, 1.20, 1.27, 540, 1240, 0, 10)
    else:
        _cam(k, t, d, 1.0, 1.04, 540, 1240, 0, 215)
    floor, ty, u = 1570, 1240, 118
    kid = Person("child", ORANGE, u, 1); hip = (236, 1226)
    co = Person("adult", TEAL, 126, -1, accent=ORANGE); hipc = (890, 1251)
    chair(k, hip, u, 1)
    table(k, 380, 730, ty, floor)
    board_side(k, 548, ty, 260)
    kid.draw(k, kid.pose(hip, True, 0.2, 0.2, (415, ty - 8), (395, ty - 4)))
    target = (590, ty - 74)
    point = lerp2((760, 1100), add(target, (60, 16)), ease(seg(t, 0.2, 0.8)))
    Jc = co.pose(hipc, False, 0.12, 0.12, point, None, 0, 0.3)
    co.draw(k, Jc, seated=False)
    if mode == "find":
        f = ease(seg(t, 0.25, min(1.3, d * 0.55)))
        mx = lerp(430, target[0], f) + (1 - f) * math.sin(t * 5) * 40; my = target[1] + (1 - f) * math.sin(t * 3.3) * 24
        k.circle(mx, my, 66); k.fill(TEAL, 0.10, keep=True); k.neon(CREAM, 7, 1.0)
        k.line([(mx + 47, my + 47), (mx + 104, my + 104)]); k.neon(CREAM, 11, 1.0)
        if f >= 1:
            g = t - min(1.3, d * 0.55)
            k.circle(target[0], target[1], 30 + 10 * pulse(g, 2)); k.neon(PINK, 6, 1.0)
            tag = str(p.get("tag") or "The habit").upper()
            bubble_text(k, tag, 450, 860, PINK, (target[0] - 450, target[1] - 905), clamp(g / 0.2), 0.8 + 0.2 * back(g / 0.3), 46, 420)
    else:
        steps = [str(x) for x in (p.get("steps") or ["One habit", "Short practice", "Review"])][:3]
        k.pop(); k.push()
        pw, ph_ = 640, 140 + 104 * len(steps)
        x0, y0 = (W - 640) / 2, 610
        a = clamp(t / 0.25)
        panel(k, x0, y0, pw, ph_, TEAL, a)
        k.text("THE PLAN", x0 + 44, y0 + 62, 40, TEAL, F_BLACK, a, 1.0, "l")
        for i, s_ in enumerate(steps):
            ti = 0.5 + i * max(0.45, (d - 1.2) / max(1, len(steps)))
            yy = y0 + 150 + i * 104
            k.rrect(x0 + 40, yy - 28, 56, 56, 14); k.stroke(TEAL if t > ti else DIM, 4, a)
            if t > ti:
                icon(k, "check", x0 + 68, yy, 34 * (0.6 + 0.4 * back((t - ti) / 0.25)), TEAL)
            k.text(s_, x0 + 122, yy, 42, CREAM if t > ti else MUTED, F_UI, a, 1.0, "l")
    k.pop()


def b_home(k, t, d, p, sd):
    """Child at home on a screen. mode: blitz | video | puzzle | lesson"""
    mode = p.get("mode", "blitz")
    paint_bg(k, "home", sd % 2)
    z = lerp(1.26, 1.32, ease(t / max(d, 0.1))); zc, zd = (540, 1245), (-20, -40)
    k.push(); k.camera(z, zc[0], zc[1], zd[0], zd[1])
    zp = lambda q: (zc[0] + zd[0] + (q[0] - zc[0]) * z, zc[1] + zd[1] + (q[1] - zc[1]) * z)
    floor, ty, u = 1570, 1245, 120
    kid = Person("child", ORANGE, u, 1); hip = (250, 1230)
    scol = {"blitz": PINK, "video": VIOLET, "puzzle": TEAL, "lesson": TEAL}[mode]
    chair(k, hip, u, 1)
    table(k, 400, 880, ty, floor)
    k.glow_dot(560, 1120, 330, scol, 0.16 + 0.05 * pulse(t, 3 if mode == "blitz" else 0.6))
    k.line([(560, ty), (760, ty), (800, 1075), (600, 1075)], True); k.shape(scol, 5, 1, 0.5)
    k.line([(540, ty + 2), (800, ty + 2)]); k.neon(scol, 6, 0.9)
    lean = 0.26 if mode in ("blitz", "video") else 0.16
    tap = (math.sin(t * 22) * 6 if mode == "blitz" else 0)
    kid.draw(k, kid.pose(hip, True, lean, 0.3 if mode != "lesson" else 0.15, (600 + tap, ty - 16 - abs(tap)), (560, ty - 8)))
    k.pop(); k.push()
    # zoomed view of the screen (drawn in screen space so its text stays crisp)
    x0, y0, pw, ph_ = 440, 575, 580, 400
    a = clamp(t / 0.2)
    c1, c2 = zp((600, 1075)), zp((800, 1075))
    k.line([c1, (x0 + 30, y0 + ph_)]); k.stroke(scol, 3, 0.4 * a, dash=[10, 12])
    k.line([c2, (x0 + pw - 30, y0 + ph_)]); k.stroke(scol, 3, 0.4 * a, dash=[10, 12])
    panel(k, x0, y0, pw, ph_, scol, a)
    cx = x0 + pw / 2
    if mode == "blitz":
        n = 1 + int(t * 4.2)
        k.text("GAME", x0 + 44, y0 + 70, 40, MUTED, F_BLACK, a, 1, "l")
        k.big(str(n), x0 + pw - 120, y0 + 76, 96, PINK, a, 1 + 0.12 * (1 - (t * 4.2) % 1))
        rng = random.Random(sd)
        for i in range(min(n, 24)):
            col = PINK if rng.random() < 0.55 else TEAL
            xx = x0 + 48 + (i % 8) * 58; yy = y0 + 170 + (i // 8) * 66
            fresh = (i == n - 1)
            k.rrect(xx, yy, 44, 44, 9); k.fill(col, 0.75 if not fresh else 1.0)
        k.text("no review", cx, y0 + ph_ - 40, 34, MUTED, F_UI2, a)
    elif mode == "video":
        k.circle(cx, y0 + 150, 78 + 4 * pulse(t, 0.8)); k.neon(VIOLET, 6, a)
        icon(k, "play", cx + 6, y0 + 150, 76, VIOLET, a)
        bw = pw - 110
        k.rrect(x0 + 55, y0 + 286, bw, 12, 6); k.fill(DIM, a)
        k.rrect(x0 + 55, y0 + 286, bw * clamp(0.25 + t * 0.09), 12, 6); k.fill(VIOLET, a)
        mm = 41 + int(t * 7)
        k.text(f"2:{mm % 60:02d}:{int(t * 53) % 60:02d} watched", cx, y0 + 344, 38, CREAM, F_UI, a)
    elif mode == "puzzle":
        sq = 62; bx, by = cx - 2 * sq, y0 + 60
        for r in range(4):
            for f in range(4):
                k.rrect(bx + f * sq, by + r * sq, sq, sq, 4); k.fill(TEAL if (r + f) % 2 else (40, 44, 70), 0.2 if (r + f) % 2 else 0.9)
        solved = t > d * 0.58
        k.sprite(piece_sprite("N", 74, ORANGE), bx + (2.5 if solved else 0.5) * sq, by + (0.5 if solved else 2.5) * sq)
        k.sprite(piece_sprite("K", 74, VIOLET), bx + 3.5 * sq, by + 2.5 * sq)
        if not solved:
            for i in range(3):
                k.circle(bx + 4 * sq + 60 + i * 34, by + 60, 9); k.fill(CREAM, 0.3 + 0.7 * (int(t * 3) % 3 == i))
        else:
            g = t - d * 0.58
            icon(k, "check", bx + 4 * sq + 90, by + 2 * sq, 80 * (0.6 + 0.4 * back(g / 0.3)), TEAL)
            sparks(k, bx + 2.5 * sq, by + 0.5 * sq, g / 0.5, TEAL, 8, 30, 90)
        k.text("slow, honest solving", cx, y0 + ph_ - 40, 34, MUTED, F_UI2, a)
    else:   # lesson
        k.circle(x0 + 92, y0 + 96, 50); k.shape(TEAL, 5, a, 0.4)
        k.circle(x0 + 92, y0 + 84, 17); k.fill(TEAL, a); k.rrect(x0 + 64, y0 + 106, 56, 30, 14); k.fill(TEAL, a)
        for i in range(5):
            hh = 14 + 34 * abs(math.sin(t * 7 + i * 1.3))
            k.rrect(x0 + 170 + i * 20, y0 + 96 - hh / 2, 10, hh, 5); k.fill(TEAL, a)
        k.circle(x0 + pw - 150, y0 + 60, 9); k.fill(PINK, 0.5 + 0.5 * pulse(t, 1.2)); k.text("LIVE", x0 + pw - 96, y0 + 60, 34, CREAM, F_BLACK, a)
        sq = 46; bx, by = cx - 2 * sq + 90, y0 + 170
        for r in range(4):
            for f in range(4):
                k.rrect(bx + f * sq, by + r * sq, sq, sq, 3); k.fill(TEAL if (r + f) % 2 else (40, 44, 70), 0.2 if (r + f) % 2 else 0.9)
        e = ease(seg(t % 2.2, 0.3, 1.0))
        k.line([(bx + 0.5 * sq, by + 3.5 * sq), lerp2((bx + 0.5 * sq, by + 3.5 * sq), (bx + 2.5 * sq, by + 0.5 * sq), e)]); k.neon(ORANGE, 7)
        k.text("Your coach", x0 + 44, y0 + 190, 36, CREAM, F_UI, a, 1, "l"); k.text("reviews YOUR games", x0 + 44, y0 + 240, 30, MUTED, F_UI2, a, 1, "l")
    k.pop()


def b_car(k, t, d, p, sd):
    """The car ride home after a tournament. mode: silent | question | kind ; say = what the parent says"""
    mode = p.get("mode", "silent")
    paint_bg(k, "road", sd % 3)
    _cam(k, t, d, 1.20, 1.26, 540, 1250, 0, -40)
    for i in range(9):
        x = ((i * 190 - t * 560) % (W + 380)) - 190
        k.rrect(x, 1404, 92, 10, 5); k.fill(CREAM, 0.45)
    bob = math.sin(t * 9) * 3
    c = k.c; c.save(); c.translate(0, bob)
    car = mix(CREAM, VIOLET, 0.45)
    c.new_path(); c.move_to(1000, 1215); c.line_to(1500, 1150); c.line_to(1500, 1330); c.close_path(); k.fill(GOLD, 0.10)
    k.smooth([(138, 1290), (132, 1215), (190, 1168), (330, 1150), (412, 1045), (560, 1022), (706, 1036), (806, 1150), (930, 1176), (962, 1236), (952, 1290)])
    c.close_path(); k.shape(car, 6, 1, 0.3)
    k.line([(432, 1062), (548, 1052), (548, 1152), (372, 1152)], True); k.fill((16, 18, 40), 1, keep=True); k.stroke(car, 4, 0.8)
    k.line([(568, 1052), (692, 1056), (774, 1152), (568, 1152)], True); k.fill((16, 18, 40), 1, keep=True); k.stroke(car, 4, 0.8)
    sink = {"silent": 10, "question": 10 + 14 * ease(seg(t, 0.6, 1.2)), "kind": 10 - 12 * ease(seg(t, 0.8, 1.4))}[mode]
    k.rrect(432, 1140 + sink, 86, 40, 18); k.fill(mix(BG1, ORANGE, 0.3), 1)
    k.circle(476, 1104 + sink, 40); k.shape(ORANGE, 5, 1, 0.25)
    k.c.new_path(); k.c.arc(476, 1104 + sink, 39, TAU * 0.5, TAU); k.c.close_path(); k.fill(ORANGE, 0.34)
    k.rrect(610, 1136, 84, 40, 18); k.fill(mix(BG1, VIOLET, 0.3), 1)
    k.circle(650, 1098, 38); k.shape(VIOLET, 5, 1, 0.25)
    k.circle(962, 1228, 12); k.fill(GOLD, 1); k.glow_dot(962, 1228, 70, GOLD, 0.8)
    k.circle(136, 1232, 9); k.fill(PINK, 1); k.glow_dot(136, 1232, 46, PINK, 0.7)
    for wx in (312, 800):
        k.circle(wx, 1298, 66); k.shape(car, 6, 1, 0.5)
        k.circle(wx, 1298, 26); k.stroke(car, 4, 0.8)
        for i in range(5):
            an = t * 9 + i * TAU / 5
            k.line([(wx + math.cos(an) * 26, 1298 + math.sin(an) * 26), (wx + math.cos(an) * 60, 1298 + math.sin(an) * 60)]); k.stroke(car, 4, 0.6)
    c.restore()
    say = p.get("say")
    if mode == "silent" or not say:
        a = clamp(t / 0.3)
        bubble(k, 470, 925, 190, 96, MUTED, (6, 130 + bob), a * 0.9, 1.0)
        for i in range(3):
            k.circle(430 + i * 40, 925, 11); k.fill(CREAM, (0.25 + 0.75 * (int(t * 2.5) % 3 == i)) * a)
    if say and mode != "silent":
        g = t - 0.35
        if g > 0:
            col = PINK if mode == "question" else TEAL
            bubble_text(k, str(say), 590, 890, col, (60, 160 + bob), clamp(g / 0.15), 0.75 + 0.25 * back(g / 0.3), 44, 520)
    if mode == "question" and t > 1.1:
        ph = ((t - 1.1) * 0.9) % 1
        icon(k, "tear", 420, 1120 + ph * 90, 22, VIOLET, 1 - ph)
    if mode == "kind" and t > 1.0:
        for i in range(3):
            ph = ((t - 1.0) * 0.6 + i * 0.33) % 1
            icon(k, "heart", 430 + i * 36 + math.sin(t * 2 + i) * 14, 1040 - ph * 220, 30 + i * 6, TEAL, (1 - ph))
    k.pop()


def b_talk(k, t, d, p, sd):
    """Parent and child face to face. tone: bad | good ; say = the parent's words"""
    tone = p.get("tone", "bad")
    paint_bg(k, "home", sd % 2); particles(k, t, sd, 8, VIOLET)
    _cam(k, t, d, 1.0, 1.06, 540, 1150)
    floor = 1500
    par = Person("adult", VIOLET, 132, 1, accent=ORANGE); hp = (270, floor - 2.46 * 132 - 14)
    kid = Person("child", ORANGE, 106, -1); hk = (790, floor - 1.72 * 106 - 14)
    f = ease(seg(t, 0.7, 1.4))
    ges = add(hp, (190 + math.sin(t * 4) * 16, -120 + math.cos(t * 4) * 12))
    par.draw(k, par.pose(hp, False, 0.06, 0.1, ges, None, 0, 0.25), seated=False)
    if tone == "bad":
        Jk = kid.pose(hk, False, 0.12 * f, 0.55 * f, None, None, 0, 0.12)
    else:
        up = add(hk, (-60, -330)) if f > 0 else None
        Jk = kid.pose(hk, False, -0.05 * f, -0.12 * f, lerp2(add(hk, (-10, 150)), add(hk, (-70, -310)), f) if f > 0 else None, None, 0, 0.12)
    kid.draw(k, Jk, seated=False)
    k.line([(120, floor + 6), (960, floor + 6)]); k.stroke(VIOLET, 4, 0.3)
    say = p.get("say")
    if say and t > 0.25:
        g = t - 0.25
        col = PINK if tone == "bad" else TEAL
        bubble_text(k, str(say), 600, 700, col, (-250, 130), clamp(g / 0.15), 0.75 + 0.25 * back(g / 0.3), 50, 520)
    if tone == "bad" and t > 1.2:
        ph = ((t - 1.2) * 0.8) % 1
        icon(k, "tear", Jk["head"][0] - 70, Jk["head"][1] + 20 + ph * 110, 24, VIOLET, 1 - ph)
    if tone == "good" and t > 1.0:
        for i in range(4):
            ph = ((t - 1.0) * 0.7 + i * 0.25) % 1
            icon(k, "star", Jk["head"][0] - 120 + i * 80, Jk["head"][1] - 110 - ph * 150, 34, GOLD, 1 - ph)
    k.pop()


def b_ladder(k, t, d, p, sd):
    """Progress as steps. mode: climb | stuck"""
    mode = p.get("mode", "climb")
    paint_bg(k, "stage", sd % 2); particles(k, t, sd, 10, GOLD)
    _cam(k, t, d, 1.0, 1.05, 540, 1150)
    n, sw, shh = 5, 172, 118
    x0, y0 = 110, 1480

    def top(i):
        return (x0 + i * sw + sw / 2, y0 - i * shh)
    reached = (t / max(0.5, d - 0.6)) * (n - 1) if mode == "climb" else 0
    for i in range(n):
        lit = mode == "climb" and i <= reached + 0.05
        col = TEAL if lit else (ORANGE if (mode == "stuck" and i <= 1) else DIM)
        k.rrect(x0 + i * sw, y0 - i * shh, sw - 10, 30, 10); k.shape(col, 5, 1, 0.5, 1.0 if lit else 0.4)
        k.line([(x0 + i * sw + 6, y0 - i * shh + 30), (x0 + i * sw + 6, y0 + 60)]); k.stroke(col, 3, 0.25)
    tx, tyy = top(n - 1)
    icon(k, "trophy", tx, tyy - 250 - 8 * math.sin(t * 2), 120, GOLD, 0.95)
    k.glow_dot(tx, tyy - 250, 150, GOLD, 0.35)
    kid = Person("child", ORANGE, 86, 1)
    if mode == "climb":
        s_ = clamp(reached, 0, n - 1); i = int(min(s_, n - 1.001)); fr = s_ - i
        hop = ease(seg(fr, 0.25, 0.85))
        a_, b_ = top(i), top(min(n - 1, i + 1))
        px = lerp(a_[0], b_[0], hop); py = lerp(a_[1], b_[1], hop) - math.sin(hop * math.pi) * 70
    else:
        c = t % 1.5
        hop = ease_out(seg(c, 0.2, 0.55)) - ease(seg(c, 0.55, 0.9))
        a_, b_ = top(1), top(2)
        px = lerp(a_[0], b_[0] - 80, hop * 0.75); py = a_[1] - math.sin(hop * math.pi * 0.9) * 90
        wx = x0 + 2 * sw - 6
        k.line([(wx, y0 - 2 * shh - 330), (wx, y0 - shh + 20)]); k.neon(PINK, 8, 0.55 + 0.45 * (0.5 < c < 0.75))
        sparks(k, wx, a_[1] - 190, seg(c, 0.5, 0.85), PINK, 8, 14, 80)
    hipy = py - 1.72 * 86 - 12
    kid.draw(k, kid.pose((px, hipy), False, 0.1, 0.0, add((px, hipy), (60, -40 - 30 * math.sin(t * 6))), None, 0, 0.3), seated=False)
    k.pop()


# ======================================================================= the board itself
POS_A = {"g1": "K", "d1": "Q", "f1": "R", "f3": "N", "a2": "P", "b2": "P", "c2": "P", "e4": "P", "f2": "P", "g2": "P", "h2": "P",
         "g8": "k", "f8": "r", "f6": "n", "c6": "n", "a7": "p", "b7": "p", "c7": "p", "d6": "p", "e5": "p", "f7": "p", "g7": "p", "h7": "p"}
POS_B = {"g1": "K", "d1": "R", "f2": "P", "g2": "P", "h2": "P", "b3": "P", "g8": "k", "f7": "p", "g7": "p", "h7": "p", "a3": "r", "b4": "n"}


def b_board(k, t, d, p, sd):
    """The moment on the board. mode: blunder | pause | pattern"""
    mode = p.get("mode", "blunder")
    paint_bg(k, "lab", sd % 2)
    _cam(k, t, d, 1.0, 1.05, 540, 1050)
    sq = 100; x0, y0 = 140, 630

    def xy(s_):
        return (x0 + (ord(s_[0]) - 97) * sq + sq / 2, y0 + (8 - int(s_[1])) * sq + sq / 2)
    k.rrect(x0 - 16, y0 - 16, 8 * sq + 32, 8 * sq + 32, 22); k.fill((14, 13, 28), 0.9, keep=True); k.neon(VIOLET, 5, 0.9)
    for r in range(8):
        for f in range(8):
            if (r + f) % 2:
                k.rrect(x0 + f * sq, y0 + r * sq, sq, sq, 2); k.fill(VIOLET, 0.13)
    pos = dict(POS_B if mode == "pattern" else POS_A)
    moving, ghost, marks = None, None, []
    if mode == "blunder":
        t1, t2 = 0.45, min(1.3, d * 0.5)
        if t >= t1:
            pos.pop("d1"); moving = ("Q", lerp2(xy("d1"), xy("d5"), ease_out(seg(t, t1, t1 + 0.2))))
        if t >= t2:
            pos.pop("f6"); e = ease(seg(t, t2, t2 + 0.28))
            ghost = ("Q", xy("d5"), 1 - e); moving = ("n", lerp2(xy("f6"), xy("d5"), e))
            marks.append(("sq", "d5", PINK))
    elif mode == "pause":
        t1 = min(1.9, d * 0.6)
        lift = 1 + 0.1 * pulse(t, 1.4)
        if t < t1:
            pos.pop("d1"); moving = ("Q", xy("d1"), lift)
            if t > 0.5:
                marks.append(("danger", "d5", PINK)); marks.append(("ray", ("f6", "d5"), PINK))
        else:
            pos.pop("d1"); moving = ("Q", lerp2(xy("d1"), xy("e2"), ease(seg(t, t1, t1 + 0.35))))
            marks.append(("sq", "e2", TEAL)); marks.append(("danger", "d5", PINK))
    else:   # pattern: the back-rank mate a trained child sees at a glance
        t1 = min(1.5, d * 0.5)
        for s_ in ("f7", "g7", "h7", "g8"):
            marks.append(("sq", s_, TEAL if t > 0.4 else VIOLET))
        if t >= t1:
            pos.pop("d1"); e = ease(seg(t, t1, t1 + 0.35)); moving = ("R", lerp2(xy("d1"), xy("d8"), e))
            marks.append(("ray", ("d1", "d8"), ORANGE))
            if e >= 1:
                marks.append(("ray", ("d8", "g8"), ORANGE))
    for kind, sq_, col in marks:
        if kind == "sq":
            x, y = xy(sq_); k.rrect(x - sq / 2 + 4, y - sq / 2 + 4, sq - 8, sq - 8, 10); k.fill(col, 0.22, keep=True); k.neon(col, 4, 0.9)
        elif kind == "danger":
            x, y = xy(sq_); k.rrect(x - sq / 2 + 6, y - sq / 2 + 6, sq - 12, sq - 12, 10); k.stroke(col, 5, 0.6 + 0.4 * pulse(t, 2), dash=[14, 12])
        elif kind == "ray":
            a_, b_ = xy(sq_[0]), xy(sq_[1]); k.line([a_, b_]); k.neon(col, 6, 0.55, 0.8)
    for s_, pc in pos.items():
        x, y = xy(s_); k.sprite(piece_sprite(pc, 104, ORANGE if pc.isupper() else VIOLET), x, y)
    if ghost:
        k.sprite(piece_sprite(ghost[0], 104, ORANGE), ghost[1][0], ghost[1][1], 1.0, ghost[2])
    if moving:
        pc, (x, y) = moving[0], moving[1]
        sc = moving[2] if len(moving) > 2 else 1.0
        if mode == "pause" and len(moving) > 2:
            k.circle(x, y, 62 + 8 * pulse(t, 1.4)); k.neon(TEAL, 5, 0.8)
        k.sprite(piece_sprite(pc, 104, ORANGE if pc.isupper() else VIOLET), x, y, sc)
    if mode == "blunder":
        t2 = min(1.3, d * 0.5)
        sparks(k, *xy("d5"), seg(t, t2 + 0.2, t2 + 0.7), PINK, 10, 40, 150)
        if 0.6 < t < t2:
            k.big("!", xy("d5")[0] + 70, xy("d5")[1] - 60, 120, PINK, 1, 0.8 + 0.2 * back((t - 0.6) / 0.2))
    if mode == "pause" and 0.5 < t < min(1.9, d * 0.6):
        g = t - 0.5
        bubble_text(k, str(p.get("ask") or "What does my opponent want?"), 590, 780, TEAL, (-120, 560), clamp(g / 0.15),
                    0.8 + 0.2 * back(g / 0.3), 48, 520, "thought")
    if mode == "pause" and t >= min(1.9, d * 0.6) + 0.35:
        g = t - min(1.9, d * 0.6) - 0.35
        icon(k, "check", xy("e2")[0] + 76, xy("e2")[1] - 66, 76 * (0.6 + 0.4 * back(g / 0.25)), TEAL)
    if mode == "pattern" and t >= min(1.5, d * 0.5) + 0.35:
        g = t - min(1.5, d * 0.5) - 0.35
        for i in range(3):
            ph = (g * 0.8 + i * 0.33) % 1
            k.circle(*xy("d8"), 40 + ph * 130); k.neon(ORANGE, 5, (1 - ph) * 0.8)
    k.pop()


# ======================================================================= data: counts, lines, bars, weeks
def _tile_icon(k, kind, x, y, s, col, a, i):
    if kind == "game":
        q = s * 0.2
        for r in range(3):
            for f in range(3):
                if (r + f) % 2 == 0:
                    k.rrect(x - 1.5 * q + f * q, y - 1.5 * q + r * q, q, q, 2); k.fill(col, 0.75 * a)
        k.rrect(x - 1.5 * q, y - 1.5 * q, 3 * q, 3 * q, 3); k.stroke(col, 2.5, a)
    elif kind == "kid":
        k.circle(x, y - s * 0.14, s * 0.17); k.fill(col, 0.85 * a)
        k.c.new_path(); k.c.arc(x, y + s * 0.34, s * 0.3, TAU / 2, TAU); k.c.close_path(); k.fill(col, 0.85 * a)
    elif kind == "hour":
        icon(k, "clock", x, y, s * 0.62, col, a)
    else:   # day
        k.text(str(i + 1), x, y, s * 0.4, col, F_BLACK, a)


def b_tiles(k, t, d, p, sd):
    """n things, k of them marked. icon: game | kid | day | hour ; tone: bad | good"""
    n = int(clamp(p.get("n", 20), 4, 30)); kk = int(clamp(p.get("k", n), 0, n))
    kind, tone = p.get("icon", "game"), p.get("tone", "bad")
    col = PINK if tone == "bad" else TEAL
    paint_bg(k, "lab", sd % 2)
    _cam(k, t, d, 1.0, 1.04, 540, 1050)
    cols = n if n <= 4 else 4 if n <= 12 else 5 if n <= 25 else 6
    rows = math.ceil(n / cols)
    cell = min(190, (W - 240) / cols, 800 / rows)
    gw, gh = cols * cell, rows * cell
    x0, y0 = W / 2 - gw / 2, 1040 - gh / 2
    panel(k, x0 - 40, y0 - 40, gw + 80, gh + 80, VIOLET, clamp(t / 0.2))
    rng = random.Random(sd + n)
    order = list(range(n)); rng.shuffle(order)
    marked = order[:kk] if kk < n else list(range(n))
    span = max(0.4, min(d - 1.1, 0.14 * kk + 0.3))
    for i in range(n):
        r, f = divmod(i, cols)
        cx, cy = x0 + f * cell + cell / 2, y0 + r * cell + cell / 2
        a = clamp((t - i * 0.5 / n) / 0.12)
        if a <= 0:
            continue
        tm = None
        if i in marked:
            tm = 0.55 + marked.index(i) / max(1, len(marked)) * span
        on = tm is not None and t >= tm
        pop = 1 + (0.25 * (1 - clamp((t - tm) / 0.2)) if on else 0)
        s = cell * 0.86 * pop
        k.rrect(cx - s / 2, cy - s / 2, s, s, cell * 0.16)
        if on:
            k.fill(mix(BG1, col, 0.3), 0.95, keep=True); k.neon(col, 4.5, a)
        else:
            k.fill((30, 28, 50), 0.9 * a, keep=True); k.stroke(DIM, 3, a)
        _tile_icon(k, kind, cx, cy, s, col if on else MUTED, a, i)
        if on:
            icon(k, "cross" if tone == "bad" else "check", cx + s * 0.28, cy - s * 0.28, s * 0.3, col, a)
    source_line(k, p.get("source_text"), t)
    k.pop()


def _series(mode, n=26, seed=0):
    rng = random.Random(seed)
    ys = []
    for i in range(n):
        x = i / (n - 1)
        base = {"flat": 0.42, "drop": 0.68 - 0.42 * x ** 1.4, "rise": 0.22 + 0.6 * x ** 1.2,
                "flat_then_rise": 0.3 + (0.0 if x < 0.5 else 0.56 * ((x - 0.5) / 0.5) ** 1.1),
                "up_down": 0.3 + 0.38 * math.sin(x * math.pi)}[mode]
        ys.append(clamp(base + rng.uniform(-0.035, 0.035), 0.05, 0.95))
    return ys


def b_line(k, t, d, p, sd):
    """A rating line over the months. mode: flat | drop | rise | flat_then_rise | up_down"""
    mode = p.get("mode", "flat")
    paint_bg(k, "lab", sd % 2)
    _cam(k, t, d, 1.0, 1.04, 540, 1050)
    x0, y0, pw, ph_ = 100, 640, 880, 760
    a = clamp(t / 0.2)
    panel(k, x0, y0, pw, ph_, VIOLET, a)
    gx0, gy0, gw, gh = x0 + 90, y0 + 70, pw - 150, ph_ - 190
    for i in range(5):
        yy = gy0 + gh * i / 4
        k.line([(gx0, yy), (gx0 + gw, yy)]); k.stroke(DIM, 2, 0.35 * a, dash=[6, 12])
    k.line([(gx0, gy0), (gx0, gy0 + gh), (gx0 + gw, gy0 + gh)]); k.stroke(MUTED, 4, a)
    k.text(str(p.get("y_label") or "Rating").upper(), gx0 + 8, gy0 - 28, 30, MUTED, F_BLACK, a, 1, "l")
    for i in range(6):
        k.text(f"M{i * 2 + 1}", gx0 + gw * (i + 0.5) / 6, gy0 + gh + 44, 30, MUTED, F_UI2, a)
    ys = _series(mode, 26, sd)
    e = ease(seg(t, 0.3, max(0.9, d * 0.72))) * (len(ys) - 1)
    pts = []
    for i, v in enumerate(ys):
        if i > e + 1:
            break
        fr = clamp(e - (i - 1))
        px = gx0 + gw * (i / (len(ys) - 1)); py = gy0 + gh * (1 - v)
        if i > 0 and fr < 1:
            q = (gx0 + gw * ((i - 1) / (len(ys) - 1)), gy0 + gh * (1 - ys[i - 1]))
            px, py = lerp2(q, (px, py), fr)
        pts.append((px, py))
    good = mode in ("rise", "flat_then_rise")
    col = TEAL if good else PINK if mode in ("flat", "drop", "up_down") else ORANGE
    if mode == "flat_then_rise" and len(pts) > 1:
        half = [q for q in pts if q[0] <= gx0 + gw * 0.5 + 1]
        if len(half) > 1:
            k.line(half); k.neon(PINK, 8, a)
        rest = [q for q in pts if q[0] >= gx0 + gw * 0.5 - gw / 25]
        if len(rest) > 1:
            k.line(rest); k.neon(TEAL, 8, a)
        if rest:
            mx = gx0 + gw * 0.5
            k.line([(mx, gy0 + 10), (mx, gy0 + gh)]); k.stroke(TEAL, 3, 0.5, dash=[10, 10])
            k.text(str(p.get("mark") or "structure starts").upper(), mx, gy0 + 6, 28, TEAL, F_BLACK, clamp((t - d * 0.4) / 0.3))
    elif len(pts) > 1:
        k.line(pts); k.neon(col, 8, a)
    if pts:
        hx, hy = pts[-1]
        k.glow_dot(hx, hy, 60, TEAL if good and hx > gx0 + gw * 0.5 else col, 0.9)
        k.circle(hx, hy, 13); k.fill(CREAM, 1)
        if e >= len(ys) - 1.01:
            g = t - max(0.9, d * 0.72)
            if mode == "flat":
                k.big("=", hx - 40, hy - 100, 110, PINK, clamp(g / 0.15), 0.8 + 0.2 * back(g / 0.25))
            elif good:
                icon(k, "arrow_up", hx - 30, hy - 110, 90 * (0.7 + 0.3 * back(g / 0.25)), TEAL)
    source_line(k, p.get("source_text"), t)
    k.pop()


def b_bars(k, t, d, p, sd):
    """Two bars compared. a_label, b_label ; a, b in 0..1 ; b is the highlighted one"""
    paint_bg(k, "lab", sd % 2)
    _cam(k, t, d, 1.0, 1.04, 540, 1050)
    x0, y0, pw, ph_ = 130, 620, 820, 800
    a = clamp(t / 0.2)
    panel(k, x0, y0, pw, ph_, VIOLET, a)
    va, vb = clamp(float(p.get("a", 0.9)), 0.08, 1), clamp(float(p.get("b", 0.3)), 0.08, 1)
    tone = p.get("tone", "good")
    colb = TEAL if tone == "good" else PINK
    base = y0 + ph_ - 170; mh = ph_ - 290
    bw = 230
    xs = (x0 + pw * 0.28 - bw / 2, x0 + pw * 0.72 - bw / 2)
    k.line([(x0 + 60, base), (x0 + pw - 60, base)]); k.stroke(MUTED, 4, a)
    ea, eb = ease_out(seg(t, 0.25, 0.9)), ease_out(seg(t, 0.75, 1.5))
    ha, hb = mh * va * ea, mh * vb * eb
    if ha > 4:
        k.rrect(xs[0], base - ha, bw, ha, 14); k.fill((40, 38, 66), 0.95, keep=True); k.neon(MUTED, 4.5, a, 0.4)
    if hb > 4:
        k.rrect(xs[1], base - hb, bw, hb, 14); k.fill(mix(BG1, colb, 0.45), 0.95, keep=True); k.neon(colb, 5.5, a)
    if eb > 0.05:
        k.line([(xs[0] + bw, base - mh * va), (xs[1] + bw / 2, base - mh * va), (xs[1] + bw / 2, base - hb - 8)]); k.stroke(GOLD, 3, 0.8 * eb, dash=[10, 10])
    for i, (lab, col) in enumerate(((p.get("a_label") or "Before", MUTED), (p.get("b_label") or "After", colb))):
        lines = wrap(str(lab).upper(), 32, 330, F_BLACK)
        for li, l in enumerate(lines[:2]):
            k.text(l, xs[i] + bw / 2, base + 46 + li * 40, 32, col, F_BLACK, a)
    if p.get("big") and t > 1.3:
        g = t - 1.3
        bs, btxt = 92, str(p["big"]).upper()
        while bs > 44 and text_w(btxt, bs, F_BLACK) > W - 150:
            bs -= 4
        k.big(btxt, W / 2, y0 + ph_ + 90, bs, GOLD, clamp(g / 0.15), 0.8 + 0.2 * back(g / 0.3))
    source_line(k, p.get("source_text"), t, y0 + ph_ - 34)
    k.pop()


def b_week(k, t, d, p, sd):
    """A training week. mode: binge | daily | compare"""
    mode = p.get("mode", "compare")
    paint_bg(k, "lab", sd % 2)
    _cam(k, t, d, 1.0, 1.04, 540, 1050)
    x0, y0, pw, ph_ = 90, 640, 900, 760
    a = clamp(t / 0.2)
    panel(k, x0, y0, pw, ph_, VIOLET, a)
    base = y0 + ph_ - 130; mh = ph_ - 260
    cw = (pw - 100) / 7
    sw = 0.0 if mode == "binge" else 1.0 if mode == "daily" else ease(seg(t, d * 0.45, d * 0.45 + 0.6))
    k.line([(x0 + 40, base), (x0 + pw - 40, base)]); k.stroke(MUTED, 4, a)
    for i, day in enumerate("MTWTFSS"):
        cx = x0 + 50 + cw * i + cw / 2
        k.text(day, cx, base + 48, 38, MUTED, F_BLACK, a)
        binge = (1.0 if i == 6 else 0.0) * ease_out(seg(t, 0.3, 0.9))
        daily = 0.2 * ease_out(seg(t, (0.3 if mode == "daily" else d * 0.45) + i * 0.08, (0.3 if mode == "daily" else d * 0.45) + i * 0.08 + 0.3))
        h = mh * lerp(binge, daily, sw)
        col = mix(PINK, TEAL, sw)
        if h > 3:
            k.rrect(cx - cw * 0.34, base - h, cw * 0.68, h, 12); k.fill(mix(BG1, col, 0.45), 0.95, keep=True); k.neon(col, 5, a)
        if sw > 0.9 and daily > 0.19:
            icon(k, "check", cx, base - h - 44, 34, TEAL, a)
    if mode != "daily" and sw < 0.5:
        k.text(str(p.get("binge_label") or "3 hours on Sunday").upper(), x0 + pw / 2, y0 + 64, 38, PINK, F_BLACK, a * (1 - sw * 2))
    if sw >= 0.5:
        k.text(str(p.get("daily_label") or "A little every day").upper(), x0 + pw / 2, y0 + 64, 38, TEAL, F_BLACK, a * clamp(sw * 2 - 1))
    k.pop()


def b_versus(k, t, d, p, sd):
    """Two columns: what doesn't work vs what does. left_title, left[], right_title, right[]"""
    paint_bg(k, "lab", sd % 2)
    _cam(k, t, d, 1.0, 1.03, 540, 1050)
    L = [str(x) for x in (p.get("left") or [])][:3]; R = [str(x) for x in (p.get("right") or [])][:3]
    n = max(len(L), len(R), 1)
    ph_ = 190 + n * 170
    y0 = 1040 - ph_ / 2
    half = d * 0.46
    for side, (ttl, items, col, x0) in enumerate(((p.get("left_title") or "Playing", L, PINK, 50), (p.get("right_title") or "Training", R, TEAL, 550))):
        ts = 0.0 if side == 0 else half
        a = clamp((t - ts) / 0.2)
        if a <= 0:
            continue
        panel(k, x0, y0, 480, ph_, col, a * (0.6 if side == 0 and t > half else 1))
        k.text(str(ttl).upper(), x0 + 240, y0 + 76, 46 if len(str(ttl)) < 12 else 38, col, F_BLACK, a)
        k.line([(x0 + 50, y0 + 126), (x0 + 430, y0 + 126)]); k.stroke(col, 3, 0.5 * a)
        for i, it in enumerate(items):
            ti = ts + 0.3 + i * min(0.45, (half - 0.5) / max(1, len(items)))
            ai = clamp((t - ti) / 0.15)
            if ai <= 0:
                continue
            yy = y0 + 220 + i * 170
            icon(k, "cross" if side == 0 else "check", x0 + 70, yy, 40 * (0.6 + 0.4 * back((t - ti) / 0.25)), col, ai)
            for li, l in enumerate(wrap(it, 38, 330, F_UI)[:3]):
                k.text(l, x0 + 116, yy - 22 + li * 48 if len(wrap(it, 38, 330, F_UI)) > 1 else yy, 38, CREAM if side else MUTED, F_UI, ai, 1, "l")
    k.pop()


# ======================================================================= ideas: brain, clock, iceberg, icon
_HEAD = [(505, 690), (690, 730), (800, 880), (822, 1010), (872, 1100), (822, 1140), (818, 1215), (776, 1300), (660, 1318),
         (636, 1450), (385, 1450), (372, 1270), (262, 1150), (226, 1000), (300, 800), (410, 712)]


def b_brain(k, t, d, p, sd):
    """Inside the child's head. mode: patterns | overload | autopilot"""
    mode = p.get("mode", "patterns")
    paint_bg(k, "lab", sd % 2)
    _cam(k, t, d, 1.0, 1.05, 540, 1050)
    col = {"patterns": TEAL, "overload": PINK, "autopilot": ORANGE}[mode]
    k.smooth(_HEAD + [_HEAD[0]]); k.c.close_path(); k.fill((18, 16, 34), 0.9, keep=True); k.neon(ORANGE, 6, 1.0)
    rng = random.Random(7)
    nodes = []
    while len(nodes) < 20:
        x, y = rng.uniform(290, 760), rng.uniform(770, 1180)
        if ((x - 520) / 255) ** 2 + ((y - 975) / 215) ** 2 < 1 and all(math.hypot(x - a, y - b) > 76 for a, b in nodes):
            nodes.append((x, y))
    edges = [(i, j) for i in range(len(nodes)) for j in range(i + 1, len(nodes)) if math.hypot(nodes[i][0] - nodes[j][0], nodes[i][1] - nodes[j][1]) < 150]
    if mode == "patterns":
        prog = ease(seg(t, 0.2, max(1.0, d * 0.75)))
        for n_, (i, j) in enumerate(edges):
            if n_ / len(edges) <= prog:
                k.line([nodes[i], nodes[j]]); k.neon(TEAL, 4, 0.75, 0.9)
        for i, (x, y) in enumerate(nodes):
            on = i / len(nodes) <= prog * 1.1
            k.circle(x, y, 12 if on else 8); k.fill(TEAL if on else DIM, 1)
            if on:
                k.glow_dot(x, y, 40 + 10 * math.sin(t * 3 + i), TEAL, 0.7)
        for i in range(3):
            ti = 0.6 + i * 0.5
            if t > ti:
                g = t - ti; bx, by = 880 + (i % 2) * 60, 760 + i * 150
                sc = 0.6 + 0.4 * back(g / 0.3)
                k.c.save(); k.c.translate(bx, by); k.c.scale(sc, sc)
                k.rrect(-52, -52, 104, 104, 12); k.fill((20, 18, 38), 1, keep=True); k.neon(TEAL, 4, 1)
                for r in range(3):
                    for f in range(3):
                        if (r + f) % 2 == 0:
                            k.rrect(-39 + f * 26, -39 + r * 26, 26, 26, 2); k.fill(TEAL, 0.45)
                k.c.restore()
                k.line([(bx - 60, by), nodes[(i * 5) % len(nodes)]]); k.stroke(TEAL, 3, 0.4, dash=[8, 10])
    elif mode == "overload":
        for n_, (i, j) in enumerate(edges):
            fl = math.sin(t * 17 + n_ * 2.1) > 0.2
            k.line([nodes[i], nodes[j]]); k.neon(PINK if fl else DIM, 4 if fl else 2, 0.8 if fl else 0.4, 1.0 if fl else 0)
        for i, (x, y) in enumerate(nodes):
            fl = math.sin(t * 13 + i * 1.7) > 0
            k.circle(x + math.sin(t * 40 + i) * 3, y, 11); k.fill(PINK if fl else MUTED, 1)
        for i in range(3):
            ph = (t * 1.3 + i * 0.33) % 1
            icon(k, "bolt", 330 + i * 190, 640 - ph * 40, 70, GOLD, 1 - ph)
    else:   # autopilot: one loop running without thinking
        cx, cy, r = 520, 975, 150
        k.circle(cx, cy, r); k.stroke(DIM, 6, 0.6, dash=[4, 18])
        a0 = t * 4.2
        k.arc(cx, cy, r, a0, a0 + 2.2); k.neon(ORANGE, 12, 1.0)
        hx, hy = cx + math.cos(a0 + 2.2) * r, cy + math.sin(a0 + 2.2) * r
        k.glow_dot(hx, hy, 70, ORANGE, 0.9); k.circle(hx, hy, 14); k.fill(CREAM, 1)
        k.text(str(p.get("loop") or "see it, play it").upper(), cx, cy, 34, CREAM, F_BLACK, 0.9)
    k.pop()


def b_clock(k, t, d, p, sd):
    """Time. mode: rush | think | low"""
    mode = p.get("mode", "rush")
    paint_bg(k, "lab", sd % 2)
    _cam(k, t, d, 1.0, 1.05, 540, 1050)
    cx, cy, r = 540, 1050, 310
    col = {"rush": PINK, "think": TEAL, "low": PINK}[mode]
    k.circle(cx, cy, r + 26); k.fill((16, 14, 30), 0.9, keep=True); k.neon(VIOLET, 5, 0.9)
    for i in range(60):
        an = i * TAU / 60 - TAU / 4
        r0 = r - (34 if i % 5 == 0 else 16)
        k.line([(cx + math.cos(an) * r0, cy + math.sin(an) * r0), (cx + math.cos(an) * r, cy + math.sin(an) * r)]); k.stroke(MUTED if i % 5 else CREAM, 5 if i % 5 == 0 else 2.5, 0.8)
    if mode == "rush":
        an = t * 7.5
        for i in range(8):
            a_ = an - i * 0.09
            k.line([(cx, cy), (cx + math.cos(a_) * (r - 60), cy + math.sin(a_) * (r - 60))]); k.neon(PINK, 9, (1 - i / 8) * 0.9, 1.0 if i == 0 else 0.3)
        k.big(str(p.get("text") or "1 SEC"), cx, cy + 150, 78, PINK, clamp(t / 0.2), 1 + 0.06 * pulse(t, 3))
    elif mode == "think":
        prog = clamp(t / max(1.0, d - 0.5))
        k.arc(cx, cy, r - 70, -TAU / 4, -TAU / 4 + TAU * prog); k.neon(TEAL, 16, 1.0)
        br = 90 + 30 * math.sin(t * 2.0)
        k.circle(cx, cy, br); k.fill(TEAL, 0.14, keep=True); k.neon(TEAL, 4, 0.8)
        k.text(str(p.get("text") or "BREATHE"), cx, cy, 40, CREAM, F_BLACK, 0.95)
    else:
        an = -TAU / 4 - 0.5 + 0.42 * clamp(t / max(1, d))
        sh = math.sin(t * 38) * 4 * (0.5 + 0.5 * pulse(t, 2))
        k.c.new_path(); k.c.move_to(cx, cy); k.c.arc(cx, cy, r - 60, an, -TAU / 4); k.c.close_path(); k.fill(PINK, 0.3 + 0.2 * pulse(t, 2.5))
        k.line([(cx + sh, cy), (cx + sh + math.cos(an) * (r - 60), cy + math.sin(an) * (r - 60))]); k.neon(PINK, 10, 1.0)
        k.big(str(p.get("text") or "0:27"), cx, cy + 150, 92, PINK, 1, 1 + 0.07 * pulse(t, 2.5))
    if mode != "think":
        k.circle(cx, cy, 18); k.fill(CREAM, 1)
    k.pop()


def b_iceberg(k, t, d, p, sd):
    """What you see (top) vs what decides it (below). top = word above water, below = up to 3 items under it"""
    paint_bg(k, "lab", sd % 2)
    _cam(k, t, d, 1.0, 1.05, 540, 1050, 0, -30 * ease(seg(t, 0.8, d)))
    wy = 900
    k.rrect(-40, wy, W + 80, 900, 0); k.fill((20, 60, 110), 0.20)
    pts = [(x, wy + math.sin(x / 90 + t * 2) * 8) for x in range(-20, W + 40, 30)]
    k.line(pts); k.neon(VIOLET, 5, 0.8)
    k.line([(450, wy), (500, 740), (560, 690), (610, 760), (650, wy)], True); k.shape(CREAM, 5, 1, 0.5)
    k.line([(330, wy + 6), (750, wy + 6), (860, 1080), (800, 1330), (640, 1500), (470, 1480), (300, 1320), (240, 1090)], True)
    k.fill((22, 30, 62), 0.85, keep=True); k.neon(TEAL, 5, 0.6 + 0.4 * ease(seg(t, 0.6, 1.2)))
    a = clamp(t / 0.25)
    k.text(str(p.get("top") or "Rating").upper(), 820, 780, 46, CREAM, F_BLACK, a)
    k.line([(690, 790), (630, 800)]); k.stroke(CREAM, 3, 0.7 * a)
    items = [str(x) for x in (p.get("below") or ["Habits", "Focus", "Review"])][:3]
    for i, it in enumerate(items):
        ti = 0.8 + i * min(0.7, (d - 1.2) / max(1, len(items)))
        g = t - ti
        if g > 0:
            k.text(it.upper(), 550, 1040 + i * 130, 50 if len(it) < 14 else 40, TEAL, F_BLACK, clamp(g / 0.15), 0.8 + 0.2 * back(g / 0.3))
    k.pop()


def b_big(k, t, d, p, sd):
    """One strong symbol. icon: heart | tear | question | bolt | trophy | star | clock | pawn | king | check | cross ; tone"""
    name = p.get("icon", "question"); col = TONE.get(p.get("tone", "brand"), ORANGE)
    paint_bg(k, "stage" if name in ("trophy", "star") else "lab", sd % 2); particles(k, t, sd, 12, col)
    _cam(k, t, d, 1.0, 1.06, 540, 1050)
    for i in range(3):
        ph = (t * 0.5 + i / 3) % 1
        k.circle(540, 1050, 190 + ph * 300); k.neon(col, 4, (1 - ph) * 0.5, 0.6)
    k.circle(540, 1050, 220); k.fill((18, 16, 34), 0.9, keep=True); k.neon(col, 6, 1)
    sc = (0.6 + 0.4 * back(t / 0.35)) * (1 + 0.04 * math.sin(t * 3))
    k.c.save(); k.c.translate(540, 1050); k.c.scale(sc, sc); k.c.translate(-540, -1050)
    icon(k, name, 540, 1050, 250, col, 1, t)
    k.c.restore()
    k.pop()


# ======================================================================= endings
def _phone(k, x, y, w, h, col=VIOLET, a=1.0):
    k.rrect(x, y, w, h, 60); k.fill((14, 13, 26), 0.97 * a, keep=True); k.neon(col, 6, a)
    k.rrect(x + w / 2 - 70, y + 22, 140, 22, 11); k.fill((40, 38, 60), a)


def b_share(k, t, d, p, sd):
    """Ending: send this reel to another chess parent."""
    paint_bg(k, "lab", sd % 2); particles(k, t, sd, 12, ORANGE)
    _cam(k, t, d, 1.0, 1.04, 540, 1080)
    x, y, w, h = 250, 610, 580, 960
    _phone(k, x, y, w, h)
    kid = Person("child", ORANGE, 62, 1)
    kid.draw(k, kid.pose((480, 900), True, 0.2, 0.25, (600, 880)), 0.5, 0.3)
    k.rrect(x + 20, y + 70, w - 40, 420, 30); k.stroke(DIM, 3, 0.5)
    up = ease_out(seg(t, 0.2, 0.6))
    sy = y + h - 30 - 430 * up
    k.c.save(); k.rrect(x + 6, y + 6, w - 12, h - 12, 56); k.c.clip()
    k.rrect(x + 14, sy, w - 28, 470, 36); k.fill((244, 240, 234), 0.97)
    k.text("Send to", x + 56, sy + 60, 40, (30, 28, 40), F_UI, 1, 1, "l")
    names = [("Chess mom", ORANGE), ("Coach", TEAL), ("Dad", VIOLET)]
    tap = 0.95
    for i, (nm, col) in enumerate(names):
        cx = x + 120 + i * 170; cy = sy + 190
        sel = i == 0 and t > tap
        k.circle(cx, cy, 56); k.fill(col, 1)
        k.text(nm[0], cx, cy, 52, (255, 255, 255), F_BLACK)
        if sel:
            k.circle(cx, cy, 68); k.stroke((30, 28, 40), 6, 1)
        k.text(nm, cx, cy + 96, 30, (30, 28, 40), F_UI2)
    if t > tap + 0.25:
        g = t - tap - 0.25
        k.rrect(x + 120, sy + 340, w - 240, 84, 42); k.fill(TEAL, clamp(g / 0.15))
        k.text("Sent", x + w / 2 - 20, sy + 382, 42, (10, 30, 26), F_BLACK, clamp(g / 0.15))
        icon(k, "check", x + w / 2 + 62, sy + 380, 34, (10, 30, 26), clamp(g / 0.15))
    k.c.restore()
    if 0.6 < t < tap + 0.5:                                   # the finger tap
        g = seg(t, 0.6, tap); cx, cy = lerp2((x + 330, sy + 420), (x + 120, sy + 200), ease(g))
        k.circle(cx + 14, cy + 18, 30); k.fill(CREAM, 0.9, keep=True); k.stroke((30, 28, 40), 4, 1)
        if t > tap:
            k.circle(x + 120, sy + 190, 60 + (t - tap) * 160); k.neon(ORANGE, 5, clamp(1 - (t - tap) / 0.4))
    import brand
    k.text("@" + brand.IG_HANDLE, W / 2, y + h + 56, 38, MUTED, F_UI, clamp(t / 0.4))
    k.pop()


def b_plan(k, t, d, p, sd):
    """Ending: comment the keyword and get the free training video."""
    import brand
    kw = brand.KEYWORD
    paint_bg(k, "lab", sd % 2); particles(k, t, sd, 12, ORANGE)
    _cam(k, t, d, 1.0, 1.04, 540, 1080)
    x, y, w, h = 110, 700, 860, 560
    panel(k, x, y, w, h, ORANGE, clamp(t / 0.2))
    k.circle(x + 96, y + 110, 46); k.fill(VIOLET, 1); k.text("You", x + 96, y + 110, 30, (255, 255, 255), F_UI)
    k.rrect(x + 170, y + 62, w - 230, 96, 48); k.fill((30, 28, 50), 1, keep=True); k.neon(ORANGE, 4, 1)
    n = int(clamp((t - 0.4) / 0.14, 0, len(kw)))
    k.text(kw[:n], x + 210, y + 110, 58, CREAM, F_BLACK, 1, 1, "l")
    if int(t * 3) % 2 == 0 and n < len(kw) + 1:
        k.line([(x + 216 + text_w(kw[:n], 58, F_BLACK), y + 82), (x + 216 + text_w(kw[:n], 58, F_BLACK), y + 138)]); k.stroke(CREAM, 4, 1)
    ts = 0.4 + 0.14 * len(kw) + 0.35
    if t > ts:
        g = t - ts
        k.sprite(logo_sprite(120), x + 96, y + 330, 1.0, clamp(g / 0.2))
        bubble_text(k, "Here's your free training video", x + 500, y + 330, TEAL, (-330, 0), clamp(g / 0.15), 0.8 + 0.2 * back(g / 0.3), 44, 560)
        if g > 0.5:
            k.rrect(x + 250, y + 420, 500, 90, 20); k.fill(mix(BG1, TEAL, 0.3), 1, keep=True); k.neon(TEAL, 4, clamp((g - 0.5) / 0.2))
            icon(k, "play", x + 310, y + 465, 46, TEAL, clamp((g - 0.5) / 0.2))
            k.text("Watch now", x + 360, y + 465, 40, CREAM, F_UI, clamp((g - 0.5) / 0.2), 1, "l")
    k.text("@" + brand.IG_HANDLE, W / 2, y + h + 70, 40, MUTED, F_UI, clamp(t / 0.4))
    k.pop()


BLOCKS = {"hall": b_hall, "coach": b_coach, "home": b_home, "car": b_car, "talk": b_talk, "ladder": b_ladder, "board": b_board,
          "tiles": b_tiles, "line": b_line, "bars": b_bars, "week": b_week, "versus": b_versus, "brain": b_brain,
          "clock": b_clock, "iceberg": b_iceberg, "big": b_big, "share": b_share, "plan": b_plan}


def draw_scene(k, sc, t, d, sd, words, chunks, t_global, first=False):
    """One full frame of a scene: art + label + captions + brand."""
    BLOCKS[sc["block"]](k, t, d, sc.get("params") or {}, sd)
    if not first:
        cut_flash(k, t)
    lab = sc.get("label")
    if lab:
        label(k, lab, t - (0.0 if first else sc.get("label_at", 0.25)) + (0.5 if first else 0), sc.get("tone", "brand"),
              strike_at=sc.get("strike_at"))
    captions(k, words, chunks, t_global, sc.get("highlight") or ())
    watermark(k)
