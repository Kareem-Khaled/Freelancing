# Fiverr Gig Images — What to Make

Fiverr allows **3 images + 1 video**. Specs: **1280×769 px**, JPG/PNG, under 5MB.
The first image is your thumbnail — it competes in a grid against thousands of
others, so it carries most of the weight.

Everything below is buildable from screens that already exist in your apps.

---

## The principle

Most AI gig thumbnails are stock robots, glowing brains, or a ChatGPT logo. They
say *"I am one of eight thousand"*.

Yours should say: **this is real software, and here is proof it works.**

So: real screenshots, real numbers, no stock imagery.

---

## Image 1 — Thumbnail (the one that gets clicked)

**Concept:** the scoreboard. Your proof, readable at grid size.

```
┌──────────────────────────────────────────────┐
│                                              │
│   AI That Answers From YOUR Documents        │
│   — and refuses when it can't                │
│                                              │
│   ┌────────┐  ┌────────┐  ┌────────┐         │
│   │ 25/25  │  │   0    │  │  100%  │         │
│   │ cited  │  │  made  │  │  off-  │         │
│   │answers │  │  up    │  │ topic  │         │
│   │        │  │refs    │  │refused │         │
│   └────────┘  └────────┘  └────────┘         │
│                                              │
│   [ faded screenshot of chat + citation ]    │
│                                              │
└──────────────────────────────────────────────┘
```

**Rules for this one:**

- Headline text **at least 40px** — it gets shrunk to a card in search results
- Three numbers maximum. `0` is your strongest, because no competitor claims it
- Screenshot goes *behind* at ~20% opacity — texture, not detail
- Dark background, one accent colour. Matches your app's existing style
- No face, no logo, no stock art

**Build it in:** Canva (free, has 1280×769 custom size) or Figma.

---

## Image 2 — The refusal

**Concept:** the single most persuasive screenshot you own.

Take a real screenshot of your app answering an off-topic question:

> **Q:** "What is the capital of France?"
> **A:** "I could not find this in the available documents."

Caption above it:

> **Other chatbots guess. Mine says "I don't know."**

**Why this is image 2 and not image 3:** it is counter-intuitive. Everyone else
sells capability; you're selling restraint. A buyer who has been burned by a
hallucinating bot will stop scrolling here.

Add a small callout arrow pointing at the refusal text.

---

## Image 3 — Citations you can click

**Concept:** show the verification that everything else rests on.

Screenshot your app mid-answer with a citation expanded — the answer on top, the
source passage underneath, filename visible.

Caption:

> **Every answer traces back to the exact passage — click and check it yourself.**

Annotate with two arrows:
- → pointing at the `[1]` marker in the answer
- → pointing at the source passage below

**Use a question with a real, specific answer** — e.g. the P1 response target
returning *"30 minutes, 24x7 [1]"* with the policy PDF underneath. Specific beats
generic.

---

## Video (optional, but the biggest single conversion lever)

Fiverr reports gigs with video get materially more orders, and yours has a
natural 60-second arc.

### 60-second script

| Time | On screen | Say / caption |
| --- | --- | --- |
| 0:00–0:05 | Empty knowledge base | "Your company's answers are buried in PDFs." |
| 0:05–0:12 | Drag 3–4 PDFs into the dropzone, chunks counter rises | "Upload your documents. Policies, contracts, manuals." |
| 0:12–0:25 | Type a real question, answer appears with `[1]` | "Ask in plain language." |
| 0:25–0:38 | **Click the citation, source passage expands** | "Every answer shows its source. Click to verify." |
| 0:38–0:50 | Ask "What is the capital of France?" → refusal | "And when your documents don't have the answer — it says so." |
| 0:50–1:00 | Scoreboard card: 25/25 · 0 · 100% | "Measured on a real corpus. Send me your documents." |

**Production notes:**

- Screen recording only — no webcam, no voiceover needed. Captions are fine and
  work better on mute, which is how most people browse
- Record at 1920×1080, zoom the browser to ~125% so text is legible on mobile
- QuickTime (`Cmd+Shift+5`) records this natively on macOS
- Keep the pause on the refusal a full 2 seconds. Let it land

---

## If you later split into multiple gigs

Images for the other two projects, both already screenshot-able:

**Document extraction** — the `Document detail` panel showing extracted JSON
beside the source invoice, with a validation finding visible. Caption: *"The
totals are actually checked, not just transcribed."*

**Ticket triage** — the `Rule activity` panel showing an escalation firing.
Caption: *"Business rules the AI cannot override."*

---

## Before uploading

1. **Sanitise.** Corpus is synthetic (NovaDesk / Acme) — confirm no real client
   or personal data appears in any frame, including browser tabs and bookmarks.
2. **Hide the URL bar** or use `localhost` cleanly. `127.0.0.1:8950` looks
   unfinished; consider a clean browser window in presentation mode.
3. **Check mobile legibility.** Shrink each image to 300px wide — if the headline
   is unreadable, the font is too small.
4. **Consistent palette** across all three so the set looks deliberate.

---

## Priority if short on time

1. **Image 1** (thumbnail) — decides whether anyone clicks at all
2. **Image 2** (refusal) — decides whether they trust you
3. **Video** — decides whether they order
4. Image 3 — reinforcement

A strong thumbnail plus the refusal screenshot will outperform three polished
but generic graphics.
