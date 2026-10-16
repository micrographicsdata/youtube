# Blog-to-YouTube pipeline runbook

1. Find work: read `state/videos.json`. Also query Shopify for blog articles published after the newest `published` date that are not in the file (published only, never `auto-draft` unpublished drafts); add them as `pending` with the next tier.
2. For each pending article (batch of 3 per run, new posts first, then tier order):
   a. Read the full article body (Shopify Admin GraphQL `article(id)`), confirm the public URL loads:
      `https://www.micrographicsdata.com/blogs/<blog>/<article>`.
   b. Write a spec JSON like `examples/ransomware-proof-archival-storage.json` using ONLY facts in the article (answer slide, 1-2 bullets or table slides, steps, Q&A, CTA). Never name competitors. No invented statistics.
   c. `python3 tools/make_video.py spec.json videos/<article>/` then view 2-3 slide PNGs to check nothing overflows.
   d. Write `videos/<article>/metadata.md` (title <= 70 chars with "Singapore" where relevant; answer-first description; chapters from `chapters.txt`; source credit; contact block; exactly 3 hashtags; 8-12 tags under 500 chars).
   e. Commit and push to `main`, then confirm the raw URL returns HTTP 200:
      `https://raw.githubusercontent.com/micrographicsdata/youtube/main/videos/<article>/<slug>.mp4`
   f. Schedule via Metricool `createScheduledPost` (blogId 6847926, network `youtube`, media = raw URL, youtubeData title/type video/privacy per mode/tags/madeForKids false), date a few minutes ahead, timezone Asia/Singapore.
3. Update `state/videos.json` (status, video_url if known) and push.
4. Notify the owner: which videos were scheduled, visibility, any failures.

Visibility mode: set in `state/mode.txt` (`private` or `public`). Default `private` until the owner switches it.
Captions (`.en.srt`) cannot be attached through Metricool; they are kept in the repo for manual upload in YouTube Studio.
