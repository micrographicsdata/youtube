# Blog-to-YouTube with OpenMontage — local runbook (Windows PC)

Owner policy (Kelvin, 9 Nov 2026): **no more silent slideshows.** Every video is a narrated OpenMontage
motion-graphics explainer (voice: Piper `en_GB-cori-high`, music bed, HyperFrames render) and is
**published immediately as public** (or whatever `state/mode.txt` says). The owner has pre-authorised all
OpenMontage approval gates for these runs; `om_run.py stages` records that as an `approval_policy` decision.

Read `openmontage/OWNER_RULES.md` first. It overrides everything here.

## Paths and tools

- OpenMontage: `C:\Users\User\OpenMontage` (venv `.venv`, Python 3.11). Never use bare `python`.
- This repo: `C:\Users\User\mgd-youtube` (push to `main`; commit as `-c user.name="Micrographics Data" -c user.email="micrographicsdata@gmail.com"`).
- Helper: `$py = "C:\Users\User\OpenMontage\.venv\Scripts\python.exe"; $om = "C:\Users\User\mgd-youtube\openmontage\om_run.py"` then `& $py $om <command>`.
  It fixes PATH itself (ffmpeg, node, npx, piper).
- Connectors: Shopify (Admin GraphQL) and Metricool (blogId `6847926`, timezone `Asia/Singapore`).
- Edit JSON/HTML files with the Write/Edit tools only. Never round-trip files through PowerShell
  `Get-Content`/`Set-Content` (it garbles UTF-8 characters such as · and ✓; `inject` refuses garbled files).

## Each run

**0. Sync.** `git -C C:\Users\User\mgd-youtube pull`.

**A. Record earlier uploads.** Metricool `getScheduledPosts` (last 14 days, `extendedRange` true). For each YouTube post
with status PUBLISHED whose article has no link yet: if it was a narrated upload, `state <article> om_status=done om_video_url=<publicUrl>`;
otherwise set `video_url` and status `done` as before. FAILED posts: report the error, retry once this run.

**B. Find new articles.** Shopify: published articles newer than the newest `published` date in `state/videos.json`
and not already listed (ignore unpublished drafts). For each: `add <handle> <blog-handle> <YYYY-MM-DD>`.
Never include "Latest Awarded Projects" unless it is the only pending item (and then name no clients beyond the article).

**C. Work list.** `worklist` prints this run's items: every new tier-0 article, then 1 never-made pending article, then
3 slideshow redos (oldest first). Do them in that order. Expect ~20 minutes per video.

**D. For each item** (`project_id` = article handle):
1. Read the full article via Shopify `article` body and confirm `https://www.micrographicsdata.com/blogs/<blog>/<article>` returns 200.
2. Write the spec `C:\Users\User\OpenMontage\projects\_specs\<article>.json` (copy the shape of
   `projects\_specs\singapore-cyber-resilience-mandate-2026.json`):
   title ≤ 70 chars ("Singapore" where relevant), 5–7 sections, 150–190 words total, answer-first hook,
   last section = CTA ending "Request a quote at micrographicsdata dot com.". Facts **only from the article** and allowed by
   OWNER_RULES (no prices, grant amounts/percentages, invented stats, superlatives, competitor or maker names; LE-500 is "to ISO 18901").
   `say` maps hard words to phonetics for the voice (e.g. `"FADGI": "FAD-jee"`).
3. `stages <spec>` → `audio <article>` → `edit <article>` (prints section and sentence times).
4. Author `projects\<article>\hyperframes\scenes.json` = `{"styles", "sections", "tweens"}`: one `<section class="clip scene"
   data-track-index="1">` per beat, all ending by the end-card start, every element animated at the global time its sentence is spoken.
   Bespoke motifs for the topic (shapes, icons, diagrams, timelines, checklists) built with CSS/divs. Use the brand classes in
   `openmontage/brand/template.html` (`kicker h1 h2 body card chip pill rule`). Mechanics reference: `openmontage/brand/reference-nhb.html`
   and `C:\Users\User\OpenMontage\projects\singapore-cyber-resilience-mandate-2026\hyperframes\scenes.json`. No static bullet slides.
   HyperFrames rules: timeline tweens only, no `repeat:-1`, animate only opacity/transform/colours, no `<br>` in body text.
5. `inject <article>` then in `projects\<article>\hyperframes`: `npx --yes hyperframes snapshot . --at <one time per scene> --no-end -o ..\review\pre`
   and **look at the contact sheet**. Fix overflow, overlap with the bottom film strip (keep content above y≈940), wrapping, empty scenes; re-inject.
6. `render <article>` — must print `"ok": true` (audio present, loudness ≈ −14 LUFS, motion ratio ≥ 0.35). Look at 2–3 of the printed snapshots.
7. `package <article>` → prints raw URL, chapters and music credit.
8. Metadata in `videos/<article>/`: new article → `metadata.md`; redo → `metadata-narrated.md` (start from the old `metadata.md`; add
   "Replaces silent slideshow: <slideshow_url>"). Answer-first first 150 chars; chapters from `package`; credit third-party sources and the music;
   end with the contact block (+65 6472 7255, sales@micrographicsdata.com, https://www.micrographicsdata.com, 115A Commonwealth Drive #02-16,
   Singapore 149596); exactly 3 hashtags; 8–12 tags.
9. Commit + push the folder, confirm the raw URL returns 200/206.
10. Metricool `createScheduledPost`: network youtube, media = raw URL, text = description, youtubeData {title, type "video",
    privacy = contents of `state/mode.txt`, tags, category "EDUCATION", madeForKids false}, date = 3 minutes from now
    (Asia/Singapore), stagger further videos by 15 minutes, draft false, autoPublish true.
11. State: new/pending → `state <article> status=scheduled-public om_status=scheduled`; redo → `state <article> om_status=scheduled`.
    Step A next run records the link and sets `om_status=done`.
12. Redo only: append `| <date> | <title> | <slideshow_url> | |` to `openmontage/UNLIST.md` (step G unlists it).

**E.** Do step G below, then commit + push `state/videos.json` and `openmontage/UNLIST.md`. Order per run: 0, A, B, C, D, G, E, F.

**G. Captions and unlisting in YouTube Studio (do this yourself; never hand it to Kelvin).** Owner standing instruction, 9 Nov 2026:
captions and unlisting are part of every run. Use **Claude in Chrome** (`mcp__claude-in-chrome__*`, Kelvin's Chrome is signed in to the
Micrographics Data channel `UCyHSOix7_kCIH4gk0Esm50Q`). Do not use the built-in browser pane: it is signed in to a different Google account.
Wait until this run's Metricool posts show PUBLISHED (re-check `getScheduledPosts` every few minutes, up to ~20 minutes) so you have their
`publicUrl`; anything still pending is handled by step A + G of the next run. Covers every video with a link and `captions` not `done`.
1. **Captions.** Copy the video's srt (`-narrated.en.srt` for redos, `.en.srt` for new) into `C:\Users\User\OpenMontage\projects\_captions\`
   (Chrome uploads only accept files under the OpenMontage folder). Open `https://studio.youtube.com/video/<id>/translations`.
   - If it asks for a video language: untick "Make this the default for my channel", pick **English (United Kingdom)**, Confirm, reload.
   - Click **Edit subtitles** (not "Upload manual": its hidden input leaves YouTube's auto-transcript as the draft). In the editor, ⋮ menu →
     **Upload file** → "With timing" dialog stays open → `file_upload` the srt to the dialog's file-input ref.
   - Check the first cue matches the srt's first line (not YouTube's auto text such as "[music]" or misspelt "microraphixdata"). Then **Publish**.
   - `state <article> captions=done`.
2. **Unlist (redos only).** Only after the narrated replacement shows **Public** in Studio content. Open
   `https://studio.youtube.com/video/<old slideshow id>/edit` → Visibility → **Unlisted** → Done → **Save** ("Changes saved").
   Fill the UNLIST.md row's Done column with `Unlisted <date>`; `state <article> unlisted=done`.
3. If Chrome is not connected or Studio is signed out, skip G, say so in the final message, and leave it for the next run (never ask Kelvin to do it).

**F. Final message to Kelvin (under 150 words):** videos published (title, visibility, time, kind new/redo), links recorded from earlier runs,
captions published and old slideshows unlisted by step G, failures, counts left (pending / redo). Do not ask Kelvin to upload captions or unlist.

If Shopify or Metricool is unavailable, or a render keeps failing after two fixes, say so plainly and stop rather than guessing.
Never fall back to the old silent slideshow script (`tools/make_video.py` is retired).
