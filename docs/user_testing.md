# User testing

Live app: https://inkwiseai-jobnp9jkgfoutv5jeuvvs7.streamlit.app/

## Round 3 test (16 Nov 2026): five people who did not build Inkwise

**Method.** Each person was given only the live link, no explanation, and asked to check a draft and get it
approved. We noted how long they spent (where they told us), where they got stuck, and what they said.

| Tester | Time spent | Where they got stuck | What they said |
|---|---|---|---|
| Mukul | 5 min | Adding an image to the draft | No errors, but the app felt a little complicated |
| Prashant | 10 min | Importing a PDF: it was refused the first time, then accepted | A little complicated; not easy for a new user to understand |
| Gautam | not recorded | — | Hard to understand at first; a video or demo would help |
| Suryadeep | not recorded | — | Hard to understand at first; a video or demo would help |
| Vaidehi | not recorded | — | Hard to understand at first; a video or demo would help |

**What we found.** Nobody hit an error, and both people who timed themselves finished in 5 to 10 minutes. All five
said the app was hard to understand at the start. The two concrete problems had one cause:

- The only file box visible on the Review page was the **image** box, which accepts PNG and JPG only. Prashant
  dropped his PDF there and it was refused; the real PDF import was hidden inside a small "Import..." popover, so he
  found it only on the second try.
- Mukul could not tell what the image box was for, because it had no label.

## What we changed the same day

| Problem | Change |
|---|---|
| A PDF in the image box was refused | **Either file box accepts any file and sends it to the right place**: a PDF, Word or text file goes to the copy, a PNG or JPG becomes the campaign image, with a one-line note saying where it went |
| The PDF import was hidden in a popover | The document box is now always visible, under the copy, with a label |
| The image box had no label | "Drop a PNG or JPG image here, or browse", next to "Use sample banner" |
| The Review page did not say what to do in what order | **Three numbered steps**: 1 Your copy · 2 Campaign image (optional) · 3 Run the check |
| Hard to know where to start | **A welcome card on each person's first Home**: who you are, what you do here in two sentences, and one button to start (Asha: "Check a sample draft", Meera: "Open the approval queue", Ravi: "Open the Fact Register") |
| "A video or demo would help" | **A 2½-minute demo video** recorded from the real app, with a voice-over and captions: on every person's first Home, at the top of the Help Centre, and linked in the README |
| (Before the test) everyone saw every page | Each person already has their own workspace with only the tabs they need |

New automated tests cover the numbered steps, the visible file boxes and the welcome card
(`tests/test_app_pages.py`).

**Not yet done.** We have not re-tested with the same five people after these changes. That, with timed tasks for
everyone, is the first item on the roadmap.

## Round 2 test (10 Nov 2026)

Five recorded review workflows on the live app; three drafts approved and two returned, with satisfaction scores from
2 to 5 out of 5. These showed the journey worked end to end but did not record time taken or the reasons behind the
scores, which we named as a gap in our Round 2 submission. In Round 3, Insights also measures real review times from
the audit log (check, creator decisions, sign-off, end to end).
