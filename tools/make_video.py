#!/usr/bin/env python3
"""Build a silent, captioned slide video from a JSON spec.

Usage: python3 tools/make_video.py spec.json OUTPUT_DIR

Outputs in OUTPUT_DIR:
  <slug>.mp4        1920x1080, 30 fps, silent AAC track
  <slug>.en.srt     English captions built from the slide text
  chapters.txt      YouTube chapter lines (first is 0:00, each >= 10 s)
  slides/*.png      individual slide images (for review)

Spec format (see examples/ransomware-proof-archival-storage.json):
{
  "slug": "article-handle",
  "title_lines": ["Line one:", "Line two (gold)"],
  "subtitle": "A guide for ...",
  "slides": [
    {"type": "answer",  "heading": "...", "body": "...", "callout": "..."},
    {"type": "bullets", "heading": "...", "items": ["..."], "footnote": "Source: ..."},
    {"type": "table",   "heading": "...", "columns": ["..."], "rows": [["..."]], "highlight_row": 3},
    {"type": "steps",   "heading": "...", "steps": [["Title", "detail"]]},
    {"type": "qa",      "heading": "...", "items": [["Question", "Answer"]]}
  ],
  "cta": {"headline": "...", "lines": ["..."], "contact": ["+65 ...", "email", "url"], "footer": ["..."]}
}
"""
import json, os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
NAVY, BLUE, GOLD = (11, 37, 69), (31, 111, 235), (224, 165, 38)
WHITE, LIGHT, PANEL, PANEL_HI = (255, 255, 255), (214, 226, 242), (21, 52, 94), (34, 84, 150)
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BRAND = "MICROGRAPHICS DATA  |  Singapore  |  since 1989"


def font(size, bold=False):
    return ImageFont.truetype(FB if bold else FR, size)


def wrap(d, text, fnt, maxw):
    lines, cur = [], ""
    for w in str(text).split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def base(heading=None):
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 24, H], fill=GOLD)
    d.text((90, 1020), BRAND, font=font(26, True), fill=LIGHT)
    if heading:
        hs = 60
        while d.textlength(heading, font=font(hs, True)) > 1740 and hs > 40:
            hs -= 2
        d.text((90, 70), heading, font=font(hs, True), fill=GOLD)
        d.rectangle([90, 160, 330, 166], fill=BLUE)
    return im, d


def fit_block(d, items, maxw, start_size, avail_h, gap_ratio=0.8):
    """Pick the largest font size so all wrapped items fit in avail_h."""
    size = start_size
    while size > 26:
        f = font(size)
        total = 0
        for it in items:
            total += len(wrap(d, it, f, maxw)) * (size + 12) + int(size * gap_ratio)
        if total <= avail_h:
            return size
        size -= 2
    return size


def slide_title(spec):
    im, d = base()
    f = font(84, True)
    y = 250
    lines = spec["title_lines"]
    for i, ln in enumerate(lines):
        col = GOLD if (i == len(lines) - 1 and len(lines) > 1) else WHITE
        for sub in wrap(d, ln, f, 1700):
            d.text((90, y), sub, font=f, fill=col)
            y += 100
    y += 40
    d.rectangle([90, y, 400, y + 6], fill=BLUE)
    y += 50
    if spec.get("subtitle"):
        d.text((90, y), spec["subtitle"], font=font(44), fill=LIGHT)
    text = " ".join(lines) + ". " + spec.get("subtitle", "")
    return im, text


def slide_answer(s):
    im, d = base(s["heading"])
    f = font(50)
    y = 230
    for ln in wrap(d, s["body"], f, 1620):
        d.text((90, y), ln, font=f, fill=WHITE)
        y += 70
    if s.get("callout"):
        y += 30
        f2 = font(44, True)
        cl = wrap(d, s["callout"], f2, 1660)
        h = 48 + 58 * len(cl)
        d.rectangle([90, y, 1830, y + h], fill=PANEL)
        yy = y + 24
        for ln in cl:
            d.text((120, yy), ln, font=f2, fill=GOLD)
            yy += 58
    return im, s["body"] + " " + s.get("callout", "")


def slide_bullets(s):
    im, d = base(s["heading"])
    avail = 940 - 230 - (60 if s.get("footnote") else 0)
    size = fit_block(d, s["items"], 1620, 44, avail)
    f = font(size)
    y = 230
    for it in s["items"]:
        d.ellipse([100, y + size // 3, 100 + size // 2, y + size // 3 + size // 2], fill=GOLD)
        for ln in wrap(d, it, f, 1620):
            d.text((150, y), ln, font=f, fill=WHITE)
            y += size + 12
        y += int(size * 0.8)
    if s.get("footnote"):
        d.text((90, 950), s["footnote"], font=font(28), fill=LIGHT)
    return im, " ".join(s["items"]) + " " + s.get("footnote", "")


def slide_table(s):
    im, d = base(s["heading"])
    cols, rows = s["columns"], s["rows"]
    n = len(cols)
    total_w = 1740
    weights = []
    for i in range(n):
        longest = max([len(cols[i]) * 0.8] + [len(str(r[i])) * 0.8 for r in rows])
        weights.append(min(max(longest, 9), 30))
    sw = sum(weights)
    widths = [int(total_w * w / sw) for w in weights]
    xs, x = [], 90
    for w in widths:
        xs.append(x)
        x += w
    size = 30
    while True:
        fh, fc = font(size - 2, True), font(size)
        head_lines = max(len(wrap(d, c, fh, widths[i] - 14)) for i, c in enumerate(cols))
        row_h = []
        for r in rows:
            row_h.append(max(len(wrap(d, str(c), fc, widths[i] - 14)) for i, c in enumerate(r)) * (size + 8) + 36)
        total_h = head_lines * (size + 4) + 30 + sum(row_h) + 12 * len(rows)
        if total_h <= 760 or size <= 22:
            break
        size -= 2
    y = 210
    hh = head_lines * (size + 4) + 24
    d.rectangle([80, y, 1840, y + hh], fill=BLUE)
    for i, c in enumerate(cols):
        ly = y + 12
        for ln in wrap(d, c, fh, widths[i] - 14):
            d.text((xs[i], ly), ln, font=fh, fill=WHITE)
            ly += size + 4
    y += hh + 10
    hi = s.get("highlight_row")
    for ri, r in enumerate(rows):
        h = row_h[ri]
        d.rectangle([80, y, 1840, y + h], fill=PANEL_HI if ri == hi else PANEL)
        for i, c in enumerate(r):
            ff = font(size, ri == hi)
            ly = y + 18
            for ln in wrap(d, str(c), ff, widths[i] - 14):
                d.text((xs[i], ly), ln, font=ff, fill=GOLD if ri == hi else WHITE)
                ly += size + 8
        y += h + 12
    text = " ".join(". ".join(f"{cols[i]}: {c}" for i, c in enumerate(r)) + "." for r in rows)
    return im, text


def slide_steps(s):
    im, d = base(s["heading"])
    steps = s["steps"]
    box = min(200, int(680 / len(steps)) - 20)
    y = 230
    for i, (a, b) in enumerate(steps, 1):
        d.rectangle([90, y, 1830, y + box], fill=PANEL)
        r = box // 2 - 20
        cy = y + box // 2
        d.ellipse([120, cy - r, 120 + 2 * r, cy + r], fill=GOLD)
        nf = font(int(r * 1.3), True)
        tw = d.textlength(str(i), font=nf)
        d.text((120 + r - tw / 2, cy - r * 0.8), str(i), font=nf, fill=NAVY)
        tx = 120 + 2 * r + 40
        d.text((tx, y + int(box * 0.18)), a, font=font(min(54, int(box * 0.27)), True), fill=WHITE)
        d.text((tx, y + int(box * 0.58)), b, font=font(min(40, int(box * 0.2))), fill=LIGHT)
        y += box + 40
    text = " ".join(f"{i}. {a}: {b}." for i, (a, b) in enumerate(steps, 1))
    return im, text


def slide_qa(s):
    im, d = base(s["heading"])
    items = s["items"]
    size = 38
    while size > 26:
        total = sum(62 + len(wrap(d, a, font(size), 1700)) * (size + 12) + 44 for q, a in items)
        if total <= 760:
            break
        size -= 2
    y = 220
    for q, a in items:
        d.text((90, y), q, font=font(size + 6, True), fill=GOLD)
        y += 62
        for ln in wrap(d, a, font(size), 1700):
            d.text((90, y), ln, font=font(size), fill=WHITE)
            y += size + 12
        y += 44
    return im, " ".join(f"{q} {a}" for q, a in items)


def slide_cta(c):
    im, d = base()
    d.text((90, 200), c["headline"], font=font(76, True), fill=WHITE)
    y = 310
    for ln in c.get("lines", []):
        d.text((90, y), ln, font=font(46), fill=LIGHT)
        y += 60
    y += 30
    contact = c["contact"]
    d.rectangle([90, y, 1830, y + 70 + 90 * len(contact)], fill=PANEL)
    yy = y + 30
    for i, t in enumerate(contact):
        d.text((130, yy), t, font=font(64 if i == 0 else 52, i == 0), fill=GOLD if i == 0 else WHITE)
        yy += 100 if i == 0 else 80
    fy = y + 70 + 90 * len(contact) + 50
    for ln in c.get("footer", []):
        d.text((90, fy), ln, font=font(30), fill=LIGHT)
        fy += 46
    text = c["headline"] + ". " + " ".join(c.get("lines", [])) + " " + " ".join(contact) + " " + " ".join(c.get("footer", []))
    return im, text


RENDER = {"answer": slide_answer, "bullets": slide_bullets, "table": slide_table, "steps": slide_steps, "qa": slide_qa}


def secs_for(text):
    return max(10, min(26, round(len(text.split()) / 3.0) + 4))


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def cues(text, start, end, maxchars=170):
    sents = re.split(r"(?<=[.?!])\s+", re.sub(r"\s+", " ", text).strip())
    chunks, cur = [], ""
    for s in sents:
        if cur and len(cur) + len(s) + 1 > maxchars:
            chunks.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        chunks.append(cur)
    total = sum(len(c) for c in chunks) or 1
    out, t = [], start + 0.5
    span = end - start - 1.0
    for c in chunks:
        dur = span * len(c) / total
        out.append((t, t + dur, c))
        t += dur
    return out


def main(spec_path, out):
    spec = json.load(open(spec_path))
    os.makedirs(os.path.join(out, "slides"), exist_ok=True)
    slides = []  # (heading, image, text)
    im, text = slide_title(spec)
    slides.append(("Introduction", im, text, 8))
    for s in spec["slides"]:
        im, text = RENDER[s["type"]](s)
        slides.append((s["heading"], im, text, secs_for(text)))
    im, text = slide_cta(spec["cta"])
    slides.append(("Next steps", im, text, 10))

    segs, srt, chapters, t = [], [], [], 0.0
    for i, (head, im, text, secs) in enumerate(slides, 1):
        png = os.path.join(out, "slides", f"s{i}.png")
        im.save(png)
        seg = os.path.join(out, f"seg{i}.mp4")
        fade = f"fade=t=in:st=0:d=0.5,fade=t=out:st={secs - 0.5}:d=0.5"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", str(secs), "-i", png,
                        "-f", "lavfi", "-t", str(secs), "-i", "anullsrc=r=44100:cl=stereo",
                        "-vf", fade + ",format=yuv420p", "-r", "30", "-c:v", "libx264", "-preset", "medium",
                        "-crf", "20", "-c:a", "aac", "-shortest", seg], check=True)
        segs.append(seg)
        chapters.append(f"{int(t) // 60}:{int(t) % 60:02d} {head}")
        for a, b, c in cues(text, t, t + secs):
            srt.append((a, b, c))
        t += secs
    lst = os.path.join(out, "list.txt")
    open(lst, "w").write("".join(f"file '{os.path.abspath(s)}'\n" for s in segs))
    final = os.path.join(out, spec["slug"] + ".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", final], check=True)
    with open(os.path.join(out, spec["slug"] + ".en.srt"), "w") as fh:
        for n, (a, b, c) in enumerate(srt, 1):
            fh.write(f"{n}\n{srt_time(a)} --> {srt_time(b)}\n{c}\n\n")
    open(os.path.join(out, "chapters.txt"), "w").write("\n".join(chapters) + "\n")
    for s in segs:
        os.remove(s)
    os.remove(lst)
    print(final, round(t), "seconds")
    print("\n".join(chapters))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
