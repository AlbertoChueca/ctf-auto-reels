"""Generate one story reel without publishing (for review). python story_test.py <level>"""
import datetime, json, os, sys
from pick_puzzles import pick
from make_story import build
level = sys.argv[1] if len(sys.argv) > 1 else "intermediate"
os.makedirs("out", exist_ok=True)
now = datetime.datetime.utcnow()
P = pick(level, seed=f"story-test-{now:%Y%m%d%H%M}")
import strategy
arms = strategy.choose(seed=f"test-{now:%Y%m%d%H%M}", fixed={"difficulty": level})
print("experiment:", {k: strategy.short(v) for k, v in arms.items()})
print(json.dumps(build(P, now.toordinal(), f"out/story_{level}.mp4", arms=arms), indent=1))
