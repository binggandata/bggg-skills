# TikTok Editing Heuristics

Use these rules after `analyze_video.py` has generated video context.

## Four Layers To Read

1. Semantic layer: transcript, phrases, claims, CTA.
2. Visual layer: contact sheet, keyframes, product proof, screenshots, screen text.
3. Rhythm layer: scene changes, silence spans, repeated setup, energy changes.
4. Business layer: audience, offer, trust points, conversion goal.

Codex is strongest at the fourth layer. Do not only summarize the video; translate the context into a publishing or ad objective.

## Hook Selection

Strong hooks usually contain one of:

- Specific money claim: cheaper, saved, price comparison, hidden cost.
- Risk reversal: QC proof, PayPal, tracking, inspection, refund, warehouse.
- Visual interruption: product reveal, before/after, order page, package opening.
- Curiosity gap: "I wish I knew this before...", "Nobody shows this part...", "Check this before shipping..."

For TikTok, the first 2 seconds should either show proof or create a question. Avoid generic intros, logos, greetings, and dead air.

## Segment Types

Use labels like:

- `hook`: first attention grabber.
- `problem`: buyer pain or uncertainty.
- `proof`: QC photo, warehouse, shipping, payment, product close-up.
- `process`: how the user does it.
- `comparison`: price, before/after, original vs received.
- `cta`: what to do next.
- `broll`: visual support under a spoken claim.

An edit plan should normally include one hook, one or two proof/process sections, and one CTA.

## Cut Rules

- Remove silence longer than about 0.6-0.8s unless it supports suspense or reveal.
- Remove repeated setup and repeated claims.
- Keep source timestamps tight; a segment can start mid-scene if transcript timing supports it.
- Prefer visual proof over talking-head explanation when both say the same thing.
- If a segment has useful audio but weak visuals, keep it short and cover it with B-roll from a proof scene.

## Ecommerce Trust Signals

For cross-border ecommerce, search for:

- QC photos, warehouse inspection, product checking.
- Order page, cart, shipping status, tracking, delivery proof.
- Real product close-up, packaging, labels, size/material proof.
- Payment trust: PayPal, refund terms, buyer protection.
- Comparison: retail price vs landed cost, original listing vs received item.

If the user provides a specific platform/product/audience, prioritize that business context over generic viral style.

## Caption Rules

- Keep captions short, spoken, and readable.
- Use the original language unless translation is requested.
- Put the clearest claim in the hook caption.
- Do not caption every filler word.
- For ads, captions should preserve claims accurately; do not invent prices, shipping time, or guarantees.

## Output Checklist

Before rendering, `output/edit_plan.json` should answer:

- What is the target audience?
- What is the promise or question in the first 2 seconds?
- Which visual scenes prove the claim?
- Which dead-air or filler spans were removed?
- What CTA does the final video end on?
- Which captions are burned and what language are they in?
