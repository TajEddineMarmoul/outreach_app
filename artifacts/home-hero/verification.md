# Public homepage hero

Latest timing revision: keep the blue envelope's original entrance unchanged (40ms delay, 300ms popup; letter rises from 130ms through 650ms with its original easing). The thread waits for the template to finish, then draws for three seconds, from 750ms through 3750ms, with a gentler ease-in/ease-out curve. Alex and Sam remain synchronized to the eased line with a 100ms visual lead. Lena now has an explicit 2550ms popup time so she is visible while the final portion of the thread is still drawing. The green circle begins at 3300ms, the white check at 3350ms, the delivery caption at 3450ms, and the full sequence finishes at 3850ms. The corrected ending was captured and reviewed in real time on desktop; evidence is in `responsive/ending-sync-*.png` and `responsive/ending-sync-timing.json`. Phone work is deferred. Earlier timing notes and captures below document comparisons, not the current pacing.

Implemented against the supplied envelope reference. This pass changes the header and hero only; the existing sections below remain in place.

The illustration uses layered SVG and the browser's Web Animations API, with no new dependencies or image downloads. `EnvelopeStory.tsx` owns the sequence; `hero.css` and `envelope-story.css` own layout and styling.

The connecting line is now one continuous SVG path per responsive layout, with a single linear drawing animation. Recipient arrival times come from the line entering each envelope's position. The line keeps advancing while envelopes pop up; the ambient movement applies to the entire curve, so there are no independently moving joins. `continuous-line-check.json` records strictly decreasing stroke offsets across all three former pauses, and `continuous-line-midway.png` shows the line advancing beyond Sam.

## Verified in the browser

- Anonymous request to `/` returns 200. The homepage also renders in the existing signed-in session, with Open app links to `/campaigns`.
- Fast playback: the template appears immediately; Alex begins at 0.694s, Sam at 1.007s, Lena at 1.496s, and the delivery state completes at 1.98s on desktop.
- The completed envelopes and thread continue gently moving. Pause stops the animations; Replay restarts them and brings an offscreen illustration back into view.
- Reduced motion cancels all animation, displays every letter and the full thread, and hides the motion controls.
- Responsive checks now cover both viewport dimensions, including short laptop windows and portrait and landscape phones. See the current matrix below.
- Letter text, including Lena's strawberry, fits within the paper edges.
- Final preview has no browser console errors. The existing Clerk development-key warning remains a development environment notice.
- TypeScript, targeted ESLint, whitespace checks, and the production build pass.

## Captures

- `01-writing.png`: template typing.
- `02-alex.png`: first personalized email.
- `03-sam.png`: second personalized email.
- `hero-desktop.png`: completed desktop composition.
- `hero-mobile.png`: mobile illustration and its connection to the green check.

The examples are decorative and send no email. No authentication protections, campaign data, delivery behavior, or deployment settings were changed in this pass.

## Responsive fitting and smooth-curve revision

The desktop composition scales uniformly to fit both the available width and small viewport height. Portrait layouts up to 1100px stack the text and illustration; the illustration fits the remaining height. Tablet grid columns are explicitly reset so older homepage styles cannot force the new illustration beside the text. The smallest phone layout reserves space between the button and template caption, and all portrait layouts reserve room for animation controls.

Both responsive routes use one continuous cubic B-spline path. Every internal join has matching tangents and second derivatives, removing the abrupt changes of curvature in the previous hand-joined curve. Browser measurements found maximum join errors below 1.4e-12. The vector stroke remains 2 CSS pixels when the drawing scales, with round ends and joins. The phone route passes below the delivery caption rather than through its text.

Checked in the browser at these viewport sizes:

| Width | Height | Layout |
| --- | --- | --- |
| 1848 | 984 | Desktop, matching the reported window |
| 1920 | 900 | Wide desktop |
| 1366 | 600 | Short laptop |
| 1280 | 720 | Laptop |
| 1024 | 768 | Landscape tablet |
| 900 | 900 | Square window |
| 768 | 1024 | Portrait tablet |
| 1024 | 1366 | Large portrait tablet |
| 390 | 844 | Portrait phone |
| 375 | 667 | Short portrait phone |
| 320 | 568 | Small portrait phone |
| 844 | 390 | Landscape phone |
| 667 | 375 | Short landscape phone |
| 568 | 320 | Small landscape phone |
| 2560 | 1080 | Ultrawide desktop |

All 15 sizes showed one visible thread path, no horizontal overflow, no clipped hero text, envelopes, delivery status or controls, and no overlap between the template caption and main copy. Screenshots were visually inspected for desktop, short laptop, portrait tablet, large portrait tablet, portrait phone, the smallest phone and landscape phone. On very small viewports the decorative letters scale down with the illustration; the main copy and buttons retain minimum sizes.

With normal animation enabled, desktop recipient popups begin at 0.694s, 1.007s and 1.496s; portrait popups begin at 0.635s, 0.874s and 1.269s. These timings remain unchanged when resizing within the same layout. The line draws linearly from 0.52s through 1.7s in either layout, and the green delivery text finishes at 1.98s. Sampled offsets decrease continuously while the envelopes appear in the intended order. Reduced-motion rendering was also used to inspect the complete static scene.

The faster sequence was visually inspected on desktop at 0.75s, 1.3s and 1.98s and on a 390×844 phone at completion. Evidence is stored in `responsive/fast-motion-checks.json`, `responsive/fast-*.png`, and `hero-mobile-fast.png`.

Current evidence: `responsive/layout-checks.json`, `responsive/motion-checks.json`, viewport-named PNGs and `responsive/desktop-at-*.png`. The top-level desktop and mobile captures show this revision. Targeted ESLint, whitespace validation and the production build pass after the final changes.
