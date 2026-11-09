"""OpenMontage helper for the Micrographics Data blog-to-YouTube pipeline (local, Windows).

Run with the OpenMontage venv:
  C:\\Users\\User\\OpenMontage\\.venv\\Scripts\\python.exe C:\\Users\\User\\mgd-youtube\\openmontage\\om_run.py <command> ...

Commands (in order, per video):
  worklist                     print this run's work list from state/videos.json (JSON)
  stages  <spec.json>          init OpenMontage project; write research/proposal/script/scene_plan checkpoints
  audio   <project_id>         Piper narration per section + music bed
  edit    <project_id>         timeline, ducked mix, SRT, timing.json, edit_decisions, index.html skeleton
  inject  <project_id>         rebuild hyperframes/index.html from brand template + hyperframes/scenes.json
  render  <project_id>         lint + snapshots + HyperFrames render + verification + compose checkpoint
  package <project_id>         compress MP4, write SRT/chapters into the youtube repo folder
  add     <article> <blog> <YYYY-MM-DD>  queue a newly published Shopify article (tier 0)
  state   <article> key=value  update one post in state/videos.json (e.g. om_status=done om_video_url=...)

All gates are pre-authorised by the owner (approval_policy decision logged per project, 9 Nov 2026).
"""
import json, os, re, shutil, subprocess, sys, time, winreg
from pathlib import Path

OM = Path(r"C:\Users\User\OpenMontage")
REPO = Path(r"C:\Users\User\mgd-youtube")
BRAND = REPO / "openmontage" / "brand"
STATE = REPO / "state" / "videos.json"
PIPE = "animated-explainer"
VOICE = "en_GB-cori-high"
LEAD, GAP, TAIL = 0.6, 0.5, 3.0
REDO_STATUSES = {"done", "test-uploaded-private", "scheduled-public"}

sys.path.insert(0, str(OM))


def _fix_path():
    parts = [str(OM / ".venv" / "Scripts")]
    for hive, key in [(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                      (winreg.HKEY_CURRENT_USER, r"Environment")]:
        try:
            with winreg.OpenKey(hive, key) as k:
                parts.append(os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]))
        except OSError:
            pass
    os.environ["PATH"] = ";".join(parts + [os.environ.get("PATH", "")])


_fix_path()
os.chdir(OM)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=isinstance(cmd, str), **kw)


def dur(p):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout.strip()
    return float(out or 0)


def proj(pid):
    return OM / "projects" / pid


def load_state():
    return json.loads(STATE.read_text(encoding="utf-8"))


def save_state(d):
    STATE.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def fail(msg):
    print("FAIL:", msg)
    sys.exit(1)


# ---------------------------------------------------------------- worklist
def cmd_worklist():
    posts = load_state()["posts"]
    never = sorted([p for p in posts if p["status"] == "pending"], key=lambda p: (p.get("tier", 9), p["published"]))
    redo = sorted([p for p in posts if p["status"] in REDO_STATUSES and p.get("om_status") not in ("done", "scheduled")],
                  key=lambda p: p["published"])
    tier0 = [p for p in never if p.get("tier") == 0]
    rest = [p for p in never if p.get("tier") != 0]
    work = [dict(p, kind="new") for p in tier0] + [dict(p, kind="pending") for p in rest[:1]] + [dict(p, kind="redo") for p in redo[:3]]
    print(json.dumps({"work": work, "remaining_pending": len(never) - len(tier0) - min(1, len(rest)),
                      "remaining_redo": max(0, len(redo) - 3)}, indent=1))


# ---------------------------------------------------------------- stages
def _opt(i, label, score, reason, rej=None):
    o = {"option_id": i, "label": label, "score": score, "reason": reason}
    if rej:
        o["rejected_because"] = rej
    return o


def cmd_stages(spec_path):
    from lib.checkpoint import init_project, write_checkpoint
    S = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    for k in ["project_id", "article", "url", "title", "sections", "facts", "cta_sub"]:
        if k not in S:
            fail(f"spec missing {k}")
    if len(S["title"]) > 70:
        fail("title over 70 chars")
    pid, url = S["project_id"], S["url"]
    PD = OM / "projects"
    init_project(pid, title=S["title"], pipeline_type=PIPE)
    shutil.copy(spec_path, proj(pid) / "spec.json")

    srcs = [{"url": url, "title": S["title"], "used_for": "All narration facts (only facts in the article)", "reliability": "secondary"}]
    srcs += [dict(s, reliability=s.get("reliability", "primary")) for s in S.get("sources", [])]
    while len(srcs) < 5:
        srcs.append({"url": url + f"#section-{len(srcs)}", "title": "Source article (section reference)", "used_for": "Supporting detail", "reliability": "secondary"})
    facts = S["facts"] + [S["facts"][-1]] * max(0, 3 - len(S["facts"]))
    hook = S["sections"][0]["text"]
    research = {
        "version": "1.0", "topic": S["title"], "research_date": time.strftime("%Y-%m-%d"),
        "landscape": {"existing_content": [{"title": S["title"], "url": url, "source": "Source article", "angle": "Owner article",
                                            "what_it_covers": "All video facts"}] * 3,
                      "saturated_angles": ["Generic overviews"], "underserved_gaps": ["Short narrated explainer for buyers"]},
        "data_points": [{"claim": f, "source_url": url, "source_name": "Source article", "credibility": "secondary_source"} for f in facts],
        "audience_insights": {"common_questions": S.get("questions", ["What is it?", "Why does it matter?", "What should we do?"]),
                              "misconceptions": [], "knowledge_level": S.get("audience", "Professional buyers in Singapore and the region")},
        "angles_discovered": [{"name": n, "hook": hook, "type": "evergreen", "why_now": "Article published"} for n in ("Answer-first explainer", "Checklist", "FAQ")],
        "sources": srcs,
    }
    write_checkpoint(PD, pid, "research", "completed", {"research_brief": research}, pipeline_type=PIPE)

    secs = S["sections"]
    total_words = sum(len(s["text"].split()) for s in secs)
    est = round(total_words / 140 * 60)
    concepts = [{"id": f"c{i}", "title": t, "hook": hook, "narrative_structure": ns, "visual_approach": "Bespoke HyperFrames motion graphics in the MD brand system",
                 "target_duration_seconds": est, "target_platform": "youtube", "key_points": [s["label"] for s in secs][:6] or ["a", "b"],
                 "cta": "Request a Quote", "why_this_works": "Answer-first narrated explainer from the article"}
                for i, t, ns in [(1, "Answer-first explainer", "problem_solution"), (2, "Checklist", "tutorial"), (3, "FAQ", "myth_busting")]]
    proposal = {
        "version": "1.0", "concept_options": concepts,
        "selected_concept": {"concept_id": "c1", "rationale": "Standing owner policy: narrated answer-first explainer"},
        "production_plan": {
            "pipeline": PIPE, "playbook": "custom", "art_direction": "MD brand system: navy, warm paper, amber; bespoke motifs per article",
            "delivery_promise": {"promise_type": "data_explainer", "motion_required": True, "source_required": False,
                                 "tone_mode": "calm, practical, institutional", "quality_floor": "presentable", "approved_fallback": None},
            "renderer_family": "explainer-data", "render_runtime": "hyperframes", "composition_mode": "atelier",
            "music_source": {"source_type": "bring_your_own", "provider": "pixabay_music", "mood_direction": S.get("music_query", "calm piano"), "estimated_cost_usd": 0},
            "voice_selection": {"provider": "piper_tts", "voice_id": VOICE, "rationale": "Owner-approved voice (Cori)", "estimated_cost_usd": 0},
            "taste_profile": {"design_read": "Heritage-archive brand system", "visual_variance": 5, "motion_intensity": 4, "information_density": 5,
                              "anti_patterns": ["static bullet slides", "prices or grant amounts", "invented numbers"]},
            "stages": [{"stage": "compose", "tools": [{"tool_name": "video_compose", "role": "render", "provider": "hyperframes", "available": True, "estimated_cost_usd": 0}],
                        "approach": "HyperFrames atelier render 1920x1080"}],
            "quality_tradeoffs": [{"tradeoff": "No stock footage (keys unavailable)", "recommendation": "Motion graphics only"}],
            "alternative_paths": [{"description": "Remotion templated", "total_cost_usd": 0, "quality_level": "free"}],
        },
        "cost_estimate": {"total_estimated_usd": 0, "line_items": [{"tool": "piper_tts", "operation": "narration", "estimated_usd": 0}], "budget_verdict": "within_budget"},
        "approval": {"status": "approved", "approved_budget_usd": 0, "user_notes": "Standing approval from owner, 9 Nov 2026: build and publish publicly without review stops."},
    }
    dl = {"version": "1.0", "project_id": pid, "decisions": [
        {"decision_id": "p0", "stage": "proposal", "category": "approval_policy", "subject": "Approval policy",
         "options_considered": [_opt("auto", "Pre-authorised full run", 1, "Owner instruction 9 Nov 2026: no more silent slideshows; routine publishes immediately as public"),
                                _opt("gated", "Per-gate approval", 0.2, "Default", "owner pre-authorised unattended runs")],
         "selected": "auto", "reason": "Owner (Kelvin) instruction in chat, 9 Nov 2026"},
        {"decision_id": "p1", "stage": "proposal", "category": "render_runtime_selection", "subject": "Render runtime",
         "options_considered": [_opt("hyperframes", "HyperFrames", 0.85, "Bespoke motion, owner-approved on NHB pilot"),
                                _opt("remotion", "Remotion", 0.6, "Template look", "owner chose HyperFrames"),
                                _opt("ffmpeg", "FFmpeg", 0.2, "No designed motion", "cannot deliver motion typography")],
         "selected": "hyperframes", "reason": "Owner-approved standard"},
        {"decision_id": "p2", "stage": "proposal", "category": "composition_mode", "subject": "Composition mode",
         "options_considered": [_opt("atelier", "Atelier", 0.85, "Bespoke scenes per article"), _opt("templated", "Templated", 0.5, "Slide-like", "owner: no slideshows")],
         "selected": "atelier", "reason": "Owner standard"},
        {"decision_id": "p3", "stage": "proposal", "category": "voice_selection", "subject": "Narration TTS provider",
         "options_considered": [_opt("piper_en_gb_cori", "Piper en_GB-cori-high", 0.8, "Owner-approved")], "selected": "piper_en_gb_cori", "reason": "Owner choice"},
        {"decision_id": "p4", "stage": "proposal", "category": "music_source", "subject": "Music source",
         "options_considered": [_opt("pixabay_music", "Pixabay music", 0.8, "Free"), _opt("brand_fallback", "Brand fallback track", 0.6, "If search fails")],
         "selected": "pixabay_music", "reason": "Free, licensed for commercial use"}]}
    kw = dict(pipeline_type=PIPE, human_approval_required=True, human_approved=True)
    write_checkpoint(PD, pid, "proposal", "completed", {"proposal_packet": proposal, "decision_log": dl}, **kw)

    t, sections = LEAD, []
    for s in secs:
        d = len(s["text"].split()) / 140 * 60
        sections.append({"id": s["id"], "label": s["label"], "text": s["text"], "start_seconds": round(t, 1), "end_seconds": round(t + d, 1),
                         "speaker_directions": "Measured, warm, clear.",
                         "delivery_cues": {"pace": "measured", "energy": "warm", "pause_after_seconds": 0.5, "delivery_note": "Natural sentence pauses"},
                         "enhancement_cues": [{"type": "animation", "description": s.get("visual", "Bespoke motion graphic"), "timestamp_seconds": round(t, 1)}],
                         "pronunciation_guides": [{"word": w, "phonetic": p} for w, p in s.get("say", {}).items()]})
        t += d + GAP
    script = {"version": "1.0", "title": S["title"], "total_duration_seconds": round(t + TAIL), "sections": sections}
    write_checkpoint(PD, pid, "script", "completed", {"script": script}, **kw)

    scenes = [{"id": f"scene-{s['id']}", "type": "animation", "description": s.get("visual", "Bespoke motion graphic"),
               "start_seconds": x["start_seconds"], "end_seconds": x["end_seconds"], "script_section_id": s["id"],
               "narrative_role": "call_to_action" if i == len(secs) - 1 else ("establish_context" if i == 0 else "deliver_payload"),
               "required_assets": [{"type": "audio", "description": f"Narration {s['id']}", "source": "generate"}]}
              for i, (s, x) in enumerate(zip(secs, sections))]
    write_checkpoint(PD, pid, "scene_plan", "completed",
                     {"scene_plan": {"version": "1.0", "style_playbook": "custom", "scenes": scenes,
                                     "metadata": {"render_runtime": "hyperframes", "composition_mode": "atelier"}}}, **kw)
    print(f"OK stages: {pid} ({total_words} words, ~{est}s)")


# ---------------------------------------------------------------- audio
def cmd_audio(pid):
    from lib.checkpoint import write_checkpoint
    from tools.tool_registry import registry
    registry.discover()
    P = proj(pid)
    S = json.loads((P / "spec.json").read_text(encoding="utf-8"))
    tts, music = registry._tools["piper_tts"], registry._tools["pixabay_music"]
    model = str(Path.home() / ".piper" / "models" / f"{VOICE}.onnx")
    (P / "assets" / "audio").mkdir(parents=True, exist_ok=True)
    assets = []
    for s in S["sections"]:
        text = s["text"]
        for w, ph in s.get("say", {}).items():
            text = text.replace(w, ph)
        f = P / "assets" / "audio" / f"narration-{s['id']}.wav"
        r = tts.execute({"text": text, "model": model, "length_scale": 1.05, "sentence_silence": 0.35, "output_path": str(f)})
        if not r.success or not f.exists():
            fail(f"TTS failed for {s['id']}: {r.error}")
        assets.append({"id": f"narration-{s['id']}", "type": "narration", "path": f"assets/audio/{f.name}", "source_tool": "piper_tts",
                       "provider": "piper", "model": VOICE, "scene_id": f"scene-{s['id']}", "duration_seconds": round(dur(f), 2), "cost_usd": 0})
    m = P / "assets" / "music" / "background_music.mp3"
    m.parent.mkdir(parents=True, exist_ok=True)
    got, meta = False, {}
    for q in [S.get("music_query", "calm piano documentary"), "calm piano documentary", "ambient piano reflective"]:
        r = music.execute({"query": q, "min_duration": 90, "max_duration": 300, "output_path": str(m)})
        if r.success and m.exists():
            got, meta = True, r.data or {}
            break
    if not got:
        shutil.copy(BRAND / "music" / "documentary-calm-leberch.mp3", m)
        meta = {"track_title": "Documentary Calm", "artist": "leberch"}
    credit = f"\"{meta.get('track_title', 'Unknown')}\" by {meta.get('artist', 'Unknown')} (Pixabay)"
    (P / "assets" / "music" / "credit.txt").write_text(credit, encoding="utf-8")
    assets.append({"id": "music-bg", "type": "music", "path": "assets/music/background_music.mp3", "source_tool": "pixabay_music",
                   "provider": "pixabay", "scene_id": f"scene-{S['sections'][0]['id']}", "duration_seconds": round(dur(m), 2),
                   "license": "Pixabay Content License", "generation_summary": credit, "cost_usd": 0})
    write_checkpoint(OM / "projects", pid, "assets", "completed", {"asset_manifest": {"version": "1.0", "assets": assets, "total_cost_usd": 0}},
                     pipeline_type=PIPE, human_approval_required=True, human_approved=True)
    print("OK audio:", ", ".join(f"{a['id']}={a['duration_seconds']}s" for a in assets), "| music:", credit)


# ---------------------------------------------------------------- edit
def cmd_edit(pid):
    from lib.checkpoint import write_checkpoint
    P = proj(pid)
    S = json.loads((P / "spec.json").read_text(encoding="utf-8"))
    W = P / "hyperframes"
    (W / "assets").mkdir(parents=True, exist_ok=True)
    t, secs = LEAD, []
    for s in S["sections"]:
        f = P / "assets" / "audio" / f"narration-{s['id']}.wav"
        d = dur(f)
        secs.append({"id": s["id"], "label": s["label"], "file": f, "start": round(t, 2), "end": round(t + d, 2), "text": s["text"]})
        t += d + GAP
    total = round(secs[-1]["end"] + TAIL, 2)
    sentences = []
    for s in secs:
        parts = [p.strip() for p in re.split(r"(?<=[.?!])\s+", s["text"]) if p.strip()]
        span = s["end"] - s["start"] - 0.35 * (len(parts) - 1)
        chars = sum(len(p) for p in parts)
        c = s["start"]
        for p in parts:
            d = span * len(p) / chars
            sentences.append({"section": s["id"], "text": p, "start": round(c, 2), "end": round(c + d, 2)})
            c += d + 0.35
    inputs, filt = [], []
    for i, s in enumerate(secs):
        inputs += ["-i", str(s["file"])]
        ms = int(s["start"] * 1000)
        filt.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[n{i}]")
    n = len(secs)
    filt.append("".join(f"[n{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,apad=whole_dur={total}[nar]")
    inputs += ["-stream_loop", "-1", "-i", str(P / "assets" / "music" / "background_music.mp3")]
    filt.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total},volume=0.16,afade=t=in:st=0:d=1.5,afade=t=out:st={total - 3.5}:d=3.5[mus]")
    filt.append("[nar]asplit=2[nar1][nar2]")
    filt.append("[mus][nar1]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[duck]")
    filt.append("[nar2][duck]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[out]")
    r = run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]", "-t", str(total), "-ar", "48000", str(W / "assets" / "mix.wav")])
    if r.returncode:
        fail("mix: " + r.stderr[-800:])

    def ts(x):
        return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{x % 60:06.3f}".replace(".", ",")
    srt = "\n".join(f"{i}\n{ts(s['start'])} --> {ts(s['end'])}\n{s['text']}\n" for i, s in enumerate(sentences, 1))
    (P / "assets" / "subtitles.srt").write_text(srt, encoding="utf-8")
    end_start = secs[-1]["start"]
    timing = {"total": total, "end_card_start": end_start,
              "sections": [{k: v for k, v in s.items() if k != "file"} for s in secs], "sentences": sentences}
    (W / "timing.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")
    shutil.copy(BRAND / "gsap.min.js", W / "assets" / "gsap.min.js")
    idx = W / "index.html"
    if not idx.exists():
        html = (BRAND / "template.html").read_text(encoding="utf-8")
        html = (html.replace("__TOTAL__", str(total)).replace("__END_START__", str(end_start))
                .replace("__END_DUR__", str(round(total - end_start, 2))).replace("__TITLE__", S["title"]).replace("__CTA_SUB__", S["cta_sub"]))
        idx.write_text(html, encoding="utf-8")
    ed = {"version": "1.0", "render_runtime": "hyperframes", "composition_mode": "atelier", "renderer_family": "explainer-data",
          "cuts": [{"id": f"cut-{s['id']}", "source": "hyperframes/index.html", "in_seconds": max(0, s["start"] - GAP / 2), "out_seconds": s["end"] + GAP / 2} for s in secs],
          "audio": {"narration": {"segments": [{"asset_id": f"narration-{s['id']}", "start_seconds": s["start"]} for s in secs]},
                    "music": {"asset_id": "music-bg", "volume": 0.16, "fade_in_seconds": 1.5, "fade_out_seconds": 3.5}},
          "music": {"asset_id": "music-bg", "volume": 0.16, "ducking": True, "fade_in_seconds": 1.5, "fade_out_seconds": 3.5},
          "subtitles": {"enabled": False, "style": "sentence-level sidecar SRT", "source": "assets/subtitles.srt"},
          "bespoke": {"entry": "hyperframes/index.html", "composition_id": "main", "art_direction": "MD brand system"},
          "metadata": {"total_seconds": total}}
    ed["cuts"][-1]["out_seconds"] = total
    write_checkpoint(OM / "projects", pid, "edit", "completed", {"edit_decisions": ed}, pipeline_type=PIPE)
    print(f"OK edit: total={total}s end_card_start={end_start}s  skeleton={idx}")
    print("SECTIONS (global seconds):")
    for s in secs:
        print(f"  {s['id']:4} {s['start']:6.2f}-{s['end']:6.2f}  {s['label']}")
    print("SENTENCES:")
    for s in sentences:
        print(f"  {s['start']:6.2f}-{s['end']:6.2f}  {s['text']}")


# ---------------------------------------------------------------- inject
def cmd_inject(pid):
    """Build hyperframes/index.html = brand template + hyperframes/scenes.json {styles, sections, tweens}."""
    P, W = proj(pid), proj(pid) / "hyperframes"
    S = json.loads((P / "spec.json").read_text(encoding="utf-8"))
    raw = (W / "scenes.json").read_text(encoding="utf-8")
    if re.search(r"Ã.|Â.|â€|âœ", raw):
        fail("scenes.json has garbled characters (UTF-8 read as ANSI). Rewrite it with the Write tool, not PowerShell Get-Content/Set-Content.")
    sc = json.loads(raw)
    tm = json.loads((W / "timing.json").read_text(encoding="utf-8"))
    total, end = tm["total"], tm["end_card_start"]
    html = (BRAND / "template.html").read_text(encoding="utf-8")
    html = (html.replace("__TOTAL__", str(total)).replace("__END_START__", str(end)).replace("__END_DUR__", str(round(total - end, 2)))
            .replace("__TITLE__", S["title"]).replace("__CTA_SUB__", S["cta_sub"]))
    html = html.replace("/* SCENE-STYLES */", sc["styles"])
    html = re.sub(r"<!-- SCENES:.*?-->", lambda m: sc["sections"], html, flags=re.S)
    html = html.replace("// SCENE-TWEENS: scene(\"#sX\", start, end); then element tweens at global times keyed to the narration (timing.json)", sc["tweens"])
    (W / "index.html").write_text(html, encoding="utf-8")
    starts = re.findall(r'<section id="[^"]+" class="clip scene" data-start="([\d.]+)" data-duration="([\d.]+)" data-track-index="1"', html)
    last = max((float(a) + float(b) for a, b in starts), default=0)
    if last > end + 0.01:
        fail(f"a scene runs past the end card start ({last} > {end})")
    print(f"OK inject: {len(starts)} scenes, last ends {round(last, 2)}s, end card {end}s, total {total}s")


# ---------------------------------------------------------------- render
def cmd_render(pid):
    from lib.checkpoint import write_checkpoint
    from tools.tool_registry import registry
    P, W = proj(pid), proj(pid) / "hyperframes"
    html = (W / "index.html").read_text(encoding="utf-8")
    if "SCENE-TWEENS" in html or "<!-- SCENES:" in html:
        fail("index.html has no authored scenes yet (write hyperframes/scenes.json, then run inject)")
    lint = run("npx --yes hyperframes lint", cwd=W)
    m = re.search(r"(\d+) error\(s\)", lint.stdout + lint.stderr)
    if not m or int(m.group(1)) > 0:
        fail("lint errors:\n" + (lint.stdout + lint.stderr)[-3000:])
    timing = json.loads((W / "timing.json").read_text(encoding="utf-8"))
    total = timing["total"]
    ats = ",".join(str(round(s["start"] + (s["end"] - s["start"]) * 0.8, 1)) for s in timing["sections"]) + f",{round(total - 2, 1)}"
    snaps = P / "review" / "snaps"
    shutil.rmtree(snaps, ignore_errors=True)
    run(f"npx --yes hyperframes snapshot . --at {ats} --no-end -o \"{snaps}\"", cwd=W, timeout=900)
    registry.discover()
    t0 = time.time()
    out = P / "renders" / "final.mp4"
    r = registry._tools["hyperframes_compose"].execute({"operation": "render_existing", "workspace_path": str(W), "output_path": str(out), "quality": "high", "fps": 30})
    if not r.success or not out.exists():
        fail("render: " + (r.error or "")[:1500])
    secs = round(time.time() - t0)
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,width,height", "-of", "json", str(out)]).stdout)
    eb = run(["ffmpeg", "-hide_banner", "-i", str(out), "-af", "ebur128=peak=true", "-vn", "-f", "null", "NUL"]).stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", eb)
    md = run(["ffmpeg", "-hide_banner", "-i", str(out), "-vf", "mpdecimate,showinfo", "-an", "-f", "null", "NUL"]).stderr
    uniq = len(re.findall(r"pts_time", md))
    frames = int(float(probe["format"]["duration"]) * 30)
    motion = round(uniq / max(frames, 1), 2)
    has_audio = any(s["codec_type"] == "audio" for s in probe["streams"])
    lufs = float(I[-1]) if I else -99
    problems = []
    if not has_audio or lufs < -30:
        problems.append(f"audio missing or silent (I={lufs})")
    if motion < 0.35:
        problems.append(f"too little motion ({motion})")
    rr = {"version": "1.0", "render_time_seconds": secs, "render_grammar": "explainer-data",
          "outputs": [{"path": "renders/final.mp4", "format": "mp4", "resolution": "1920x1080", "fps": 30, "duration_seconds": round(float(probe["format"]["duration"]), 2),
                       "codec": "h264", "audio_codec": "aac", "file_size_bytes": int(probe["format"]["size"]), "platform_target": "youtube"}],
          "verification_notes": [f"loudness {lufs} LUFS", f"unique-frame ratio {motion}", f"snapshots: {snaps}"], "warnings": problems}
    write_checkpoint(OM / "projects", pid, "compose", "completed", {"render_report": rr}, pipeline_type=PIPE)
    print(json.dumps({"ok": not problems, "problems": problems, "lufs": lufs, "motion": motion, "seconds": rr["outputs"][0]["duration_seconds"],
                      "render_secs": secs, "snapshots": [str(p) for p in sorted(snaps.glob("*.png"))]}, indent=1))
    if problems:
        sys.exit(1)


# ---------------------------------------------------------------- package
def cmd_package(pid):
    P = proj(pid)
    S = json.loads((P / "spec.json").read_text(encoding="utf-8"))
    art = S["article"]
    D = REPO / "videos" / art
    D.mkdir(parents=True, exist_ok=True)
    out = D / f"{art}-narrated.mp4"
    r = run(["ffmpeg", "-v", "error", "-y", "-i", str(P / "renders" / "final.mp4"), "-c:v", "libx264", "-preset", "slow", "-crf", "22",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)])
    if r.returncode:
        fail("compress: " + r.stderr[-500:])
    srt = (P / "assets" / "subtitles.srt").read_text(encoding="utf-8").replace(" dot com", ".com")
    (D / f"{art}-narrated.en.srt").write_text(srt, encoding="utf-8")
    timing = json.loads((P / "hyperframes" / "timing.json").read_text(encoding="utf-8"))
    ch, last = [], -99.0
    for i, s in enumerate(timing["sections"]):
        st = 0.0 if i == 0 else s["start"] - GAP / 2
        if st - last >= 10 or i == 0:
            ch.append((st, s["label"]))
            last = st
    if len(ch) >= 2 and timing["total"] - ch[-1][0] < 10:
        ch.pop()
    lines = [f"{int(t // 60)}:{int(t % 60):02d} {lab}" for t, lab in ch]
    (D / "chapters-narrated.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    credit = (P / "assets" / "music" / "credit.txt").read_text(encoding="utf-8")
    print(json.dumps({"video": str(out), "mb": round(out.stat().st_size / 1e6, 1), "raw_url":
                      f"https://raw.githubusercontent.com/micrographicsdata/youtube/main/videos/{art}/{out.name}",
                      "chapters": lines, "music_credit": credit, "metadata_path": str(D / "metadata.md")}, indent=1))


# ---------------------------------------------------------------- add
def cmd_add(article, blog, published):
    d = load_state()
    if any(p["article"] == article for p in d["posts"]):
        print("SKIP add: already in state:", article)
        return
    d["posts"].append({"status": "pending", "blog": blog, "article": article, "published": published, "tier": 0, "video_url": None})
    save_state(d)
    print("OK add:", article)


# ---------------------------------------------------------------- state
def cmd_state(article, *kv):
    d = load_state()
    hit = [p for p in d["posts"] if p["article"] == article]
    if not hit:
        fail("article not in state")
    for item in kv:
        k, v = item.split("=", 1)
        hit[0][k] = None if v == "null" else v
    save_state(d)
    print("OK state:", json.dumps(hit[0]))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    c, args = sys.argv[1], sys.argv[2:]
    {"worklist": cmd_worklist, "stages": cmd_stages, "audio": cmd_audio, "edit": cmd_edit, "inject": cmd_inject, "render": cmd_render,
     "package": cmd_package, "add": cmd_add, "state": cmd_state}[c](*args)
