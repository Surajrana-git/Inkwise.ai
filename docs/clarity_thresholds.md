# Guideline Clarity Insights: thresholds

Insights uses only decisions that were actually logged in this workspace (creator accept /
edit / reject on findings, manager approve / reject). It makes no claims about campaign
outcomes. The numbers below are constants in `engine/workflow.py`; change them there.

| Name | Value | Meaning |
|---|---|---|
| `UNCLEAR_MIN_SHOWN` | 5 | A guideline is only judged after its findings were shown at least 5 times in the selected range |
| `UNCLEAR_OVERRIDE_RATE` | 0.40 | Override = the creator edited the suggested fix. 40% or more of decisions |
| `UNCLEAR_REJECT_RATE` | 0.30 | Reject = the creator or an approver rejected the finding. 30% or more of decisions |
| `REPEAT_MIN_COUNT` | 3 | The same category from the same creator 3 or more times in range is a repeat issue |
| `EXPIRING_SOON_DAYS` | 30 | Fact Register: a fact that expires within 30 days is "expiring soon" |

**Likely unclear** = shown ≥ 5 **and** (override rate ≥ 40% **or** reject rate ≥ 30%).

The reason text is generated from the counts, for example
"Rejected 4 of 9 times (44%) by 3 different users".

Rates are computed over decisions in the selected date range; the role filter keeps only
decisions made by users of that role (demo accounts carry their role). "Shown" counts
findings on content created in the range.

Suggested rewording comes from Gemini (template fallback when the key is missing or the
model is unavailable) and is cached. Only an admin can accept it; acceptance is written to
the audit log as `guideline_reworded` and applied to the loaded brand kit. The JSON brand
kit file is never modified by the app.
