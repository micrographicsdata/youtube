import os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
W, H = 1920, 1080
NAVY = (11, 37, 69)
BLUE = (31, 111, 235)
GOLD = (224, 165, 38)
WHITE = (255, 255, 255)
LIGHT = (214, 226, 242)
PANEL = (21, 52, 94)

FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
def font(size, bold=False):
    return ImageFont.truetype(FB if bold else FR, size)

def wrap(draw, text, fnt, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def base(title=None):
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 24, H], fill=GOLD)
    d.text((90, 1020), "MICROGRAPHICS DATA  |  Singapore  |  since 1989", font=font(26, True), fill=LIGHT)
    if title:
        d.text((90, 70), title, font=font(60, True), fill=GOLD)
        d.rectangle([90, 160, 330, 166], fill=BLUE)
    return im, d

def bullets(d, items, y=230, size=42, gap=34, maxw=1620):
    f = font(size)
    for it in items:
        d.ellipse([100, y + 16, 122, y + 38], fill=GOLD)
        lines = wrap(d, it, f, maxw)
        for ln in lines:
            d.text((150, y), ln, font=f, fill=WHITE)
            y += size + 12
        y += gap
    return y

slides = []  # (filename, seconds)

# 1 Title
im, d = base()
f = font(84, True)
y = 250
for ln in wrap(d, "Ransomware-Proof Archival Storage:", f, 1700):
    d.text((90, y), ln, font=f, fill=WHITE); y += 100
d.text((90, y), "Where Offline Microfilm Fits", font=f, fill=GOLD); y += 140
d.rectangle([90, y, 400, y + 6], fill=BLUE); y += 50
d.text((90, y), "A guide for Singapore records and IT teams", font=font(44), fill=LIGHT)
slides.append(("s1", 8, im))

# 2 Short answer
im, d = base("The short answer")
f = font(50)
y = 230
txt = ("No storage that stays connected to a network is fully ransomware-proof. "
       "CISA recommends offline, encrypted backups of critical data, tested regularly, "
       "because ransomware seeks out and encrypts reachable backups.")
for ln in wrap(d, txt, f, 1620):
    d.text((90, y), ln, font=f, fill=WHITE); y += 70
y += 30
d.rectangle([90, y, 1830, y + 170], fill=PANEL)
f2 = font(44, True)
t2 = "For long-term records, archival microfilm adds a copy that is offline by nature and cannot be encrypted by malware."
yy = y + 24
for ln in wrap(d, t2, f2, 1660):
    d.text((120, yy), ln, font=f2, fill=GOLD); yy += 58
slides.append(("s2", 14, im))

# 3 CISA recommends
im, d = base("What CISA recommends for backups")
bullets(d, [
    "Keep offline, encrypted backups of critical data.",
    "Test backup availability and integrity regularly in a recovery exercise.",
    "Keep \"golden images\" of critical systems so they can be rebuilt quickly.",
    "Use immutable cloud storage with caution: it may not meet every compliance requirement, and misconfiguration is costly.",
], size=44)
d.text((90, 940), "Source: CISA #StopRansomware Guide", font=font(28), fill=LIGHT)
slides.append(("s3", 16, im))

# 4 Comparison table
im, d = base("How archival storage options compare")
cols = ["Option", "Offline?", "Can malware alter it?", "Readable without software?", "Format migration"]
rows = [
    ["Network or cloud backup", "No", "Yes, if credentials are compromised", "No", "Ongoing"],
    ["Immutable cloud (object lock)", "No", "Protected if configured correctly", "No", "Ongoing"],
    ["Offline tape or disk", "Yes, when disconnected", "Only while connected", "No", "Every few years"],
    ["Archival microfilm", "Yes, always", "No", "Yes", "None"],
]
xs = [90, 520, 820, 1290, 1640]
widths = [420, 290, 450, 340, 190]
y = 210
fh = font(28, True); fc = font(28)
d.rectangle([80, y, 1840, y + 80], fill=BLUE)
for x, wd, c in zip(xs, widths, cols):
    ly = y + 10
    for ln in wrap(d, c, fh, wd - 10)[:2]:
        d.text((x, ly), ln, font=fh, fill=WHITE); ly += 32
y += 90
for i, r in enumerate(rows):
    hl = (i == 3)
    d.rectangle([80, y, 1840, y + 150], fill=(34, 84, 150) if hl else PANEL)
    for x, wd, c in zip(xs, widths, r):
        ly = y + 20
        for ln in wrap(d, c, font(30, hl), wd - 10)[:3]:
            d.text((x, ly), ln, font=font(30, hl), fill=GOLD if hl else WHITE); ly += 38
    y += 162
slides.append(("s4", 20, im))

# 5 What microfilm does / does not
im, d = base("What microfilm does and does not protect")
bullets(d, [
    "It protects records: registers, contracts, drawings and financial records, as human-readable images.",
    "It does not restore systems. Databases, applications and live files still need offline digital backups.",
    "It must be made and stored correctly: ISO 18901 film, processed to ISO 18917, stored to ISO 18911.",
    "It needs physical security: a controlled vault, ideally with a duplicate at a second site.",
], size=42, gap=26)
slides.append(("s5", 18, im))

# 6 Layered plan
im, d = base("A layered plan for long-term records")
steps = [("1", "Working copy", "on your systems for daily access"),
         ("2", "Offline, encrypted digital backup", "tested regularly, for system recovery"),
         ("3", "Microfilm preservation master", "for records that must survive any digital failure")]
y = 250
for n, a, b in steps:
    d.rectangle([90, y, 1830, y + 200], fill=PANEL)
    d.ellipse([120, y + 40, 240, y + 160], fill=GOLD)
    d.text((158, y + 52), n, font=font(80, True), fill=NAVY)
    d.text((290, y + 38), a, font=font(54, True), fill=WHITE)
    d.text((290, y + 112), b, font=font(40), fill=LIGHT)
    y += 240
slides.append(("s6", 14, im))

# 7 FAQ
im, d = base("Common questions")
qa = [("Is any storage truly ransomware-proof?", "Only storage that is offline and cannot be rewritten is beyond ransomware's reach."),
      ("Does microfilm replace digital backups?", "No. Microfilm preserves records. Offline digital backups restore systems and live data."),
      ("How does digital data get onto microfilm?", "A COM system, or archive writer, writes digital images onto 16 mm or 35 mm film.")]
y = 220
for q, a in qa:
    d.text((90, y), q, font=font(44, True), fill=GOLD); y += 62
    for ln in wrap(d, a, font(38), 1700):
        d.text((90, y), ln, font=font(38), fill=WHITE); y += 50
    y += 44
slides.append(("s7", 20, im))

# 8 CTA
im, d = base()
d.text((90, 200), "Plan your preservation copy", font=font(76, True), fill=WHITE)
d.text((90, 310), "Talk to Micrographics Data about microfilm,", font=font(46), fill=LIGHT)
d.text((90, 370), "document scanning and archive storage in Singapore.", font=font(46), fill=LIGHT)
d.rectangle([90, 480, 1830, 760], fill=PANEL)
d.text((130, 510), "+65 6472 7255", font=font(64, True), fill=GOLD)
d.text((130, 610), "sales@micrographicsdata.com", font=font(52), fill=WHITE)
d.text((130, 690), "www.micrographicsdata.com", font=font(52), fill=WHITE)
d.text((90, 840), "Read the full article: Ransomware-Proof Archival Storage: Where Offline Microfilm Fits", font=font(32), fill=LIGHT)
d.text((90, 890), "Source: Cybersecurity and Infrastructure Security Agency, #StopRansomware Guide", font=font(32), fill=LIGHT)
slides.append(("s8", 10, im))

segs = []
for name, secs, im in slides:
    png = os.path.join(OUT, name + ".png")
    im.save(png)
    seg = os.path.join(OUT, name + ".mp4")
    fade = f"fade=t=in:st=0:d=0.5,fade=t=out:st={secs-0.5}:d=0.5"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", str(secs), "-i", png,
                    "-f", "lavfi", "-t", str(secs), "-i", "anullsrc=r=44100:cl=stereo",
                    "-vf", fade + ",format=yuv420p", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-c:a", "aac", "-shortest", seg], check=True)
    segs.append(seg)
lst = os.path.join(OUT, "list.txt")
open(lst, "w").write("".join(f"file '{s}'\n" for s in segs))
final = os.path.join(OUT, "ransomware-proof-archival-storage-singapore.mp4")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", final], check=True)
print(final, sum(s for _, s, _ in slides))
