# Outreach homepage concepts, revision 2

Two replacement middle sections for the public homepage. The user asked for less interface detail, clearer reasons to care, and drawings or generated layouts rather than exhaustive feature demonstrations.

These are visual concepts only. No application code, email settings, or sending behavior changed. The approved hero and FAQ remain unchanged in the v1 folder.

## Page order

1. [Approved hero, unchanged](../public-homepage-v1/01-approved-hero.png)
2. [Personalization with profile photos](02-personalization-profiles.png)
3. [Scheduling and control](03-scheduling-and-control.png)
4. [Approved FAQ and final invitation, unchanged](../public-homepage-v1/04-faq-and-get-started.png)

## What changed

- Personalization leads with the repetitive editing problem. The latest refinement replaces the fruit example with three fictional profile photos beside a personal email. Sam is selected, and the name and company match the highlighted fields in the preview. Import controls, email addresses, the template editor, and the numbered walkthrough stay removed.
- The [earlier fruit illustration](02-personalization.png) is preserved for reference. [Profile edit prompt and checks](profile-edit-prompt.md).
- Reusable templates and checking each person's version are quieter supporting points. Templates are supported by the existing product.
- Scheduling uses a weekly planner and paper airplane instead of a full settings form. Send now, scheduled sending, Autopilot, timezone, and daily limits remain understandable without exposing every control.
- Sender choice, review before launch, and pausing future sends use simple illustrations instead of three miniature application panels.

## Design direction

- Palette: paper #FFFFFF, ink #0B174B, cobalt #0754FF, mist #F5F8FF, edge #D6E3F4. Green #00B985 is reserved for actual status where needed.
- Type: retain the references' bold geometric sans for headlines and clean regular sans for body copy. No new serif or typography identity.
- Layout: a large benefit statement paired with one paper illustration, then a restrained supporting row.
- Signature: the blue thread connecting the selected recipient to a personal note. The calendar's flight path extends the same visual language.
- The first idea of another three-step diagram was rejected because it repeated the original dense tutorial. The final concepts focus on one visual explanation per section.

## Checks and implementation boundaries

The 1536 x 1024 PNGs were inspected for legible copy, intact margins, reference-style continuity, and accurate feature claims. The latest personalization image pairs Sam with Brightside; the calendar reads Monday through Friday, 9 AM to 4 PM, UTC. All profiles, example data, and the schedule are illustrative.

- The example is not interactive and sends no email.
- Profile photos are fictional illustrations, not actual customers or a promise of profile-photo importing.
- Scheduling and Autopilot require launch. Pausing affects future sends; it does not recall sent emails.
- Gmail is the supported sender service described here. No unverified integrations, outcome metrics, pricing, or AI claims were introduced.
- These PNGs are design references, not responsive production components. If implemented, recreate the copy and layout as accessible HTML, export the illustrations separately, preserve keyboard access and focus states, and adjust the composition for mobile.
- No performance or conversion improvement has been measured.

Generated with the built-in image generation tool. [Exact prompts](generation-prompts.md).
