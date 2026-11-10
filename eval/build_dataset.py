"""Build the labelled dev and test sets from the Lumora brand kit.

Every planted error comes from a catalogue tied to a real brand-kit ID, so each label
is correct by construction. Clean sentences use approved terms, good examples and
facts that have not expired. Run:  python eval/build_dataset.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Sentences that break no rule (approved terms, current facts, good examples)
CLEAN = [
    "Send money in a few taps with Lumora Pay.",
    "Your transfer is on its way.",
    "Explore tools that can help you plan your spending.",
    "Open Lumora Pay to view your account activity.",
    "Use Spend Insights to review your monthly spending.",
    "See the transfer estimate shown before you confirm.",
    "Available features may depend on eligibility.",
    "Review any applicable fee before you confirm.",
    "Check the app for current availability in your area.",
    "Track upcoming payments in one place.",
    "Review the details, then select Confirm to continue.",
    "Choose the option that works for you.",
    "Select Continue. The status is shown as Approved.",
    "Customers can turn on transaction notifications in app settings.",
    "Spend Insights groups eligible transactions by spending category.",
    "You can download a monthly activity statement from the Lumora app.",
    "Every transfer goes through a confirmation step before you submit it.",
    "If something looks wrong, in-app support can help you find the dispute form.",
    "Set a monthly spending target in Spend Insights to stay on plan.",
    "Sign in with biometrics on compatible devices.",
    "Transfer timing can depend on the destination and payment method.",
    "Update your contact details in profile settings at any time.",
    "A scheduled payment is a payment sent on a date you choose.",
    "Eligible customers will see the new option in their account.",
]

# (sentence, exact_span, id, type, explanation, suggested_fix)
ERRORS = [
    # terminology: banned variants from the glossary
    ("Open LumoraPay to view your activity.", "LumoraPay", "T01", "terminology", "Banned variant of the product name.", "Lumora Pay"),
    ("Pay your bills with Lumora pay today.", "Lumora pay", "T01", "terminology", "Product name must be two capitalised words.", "Lumora Pay"),
    ("Download LPay and start saving time.", "LPay", "T01", "terminology", "Abbreviation of the product name is not allowed.", "Lumora Pay"),
    ("Check SpendInsight to see where your money goes.", "SpendInsight", "T02", "terminology", "Banned variant of the feature name.", "Spend Insights"),
    ("Spending Insights now shows your weekly trends.", "Spending Insights", "T02", "terminology", "Feature name must be used exactly.", "Spend Insights"),
    ("Everything is easier in the Lumora application.", "the Lumora application", "T03", "terminology", "Use the approved name.", "the Lumora app"),
    ("Start a money push to a friend in seconds.", "money push", "T04", "terminology", "Use the plain term.", "transfer"),
    ("Set up an auto debit for your rent.", "auto debit", "T05", "terminology", "Use the approved plain-language term.", "scheduled payment"),
    ("Turn on a txn alert for large payments.", "txn alert", "T06", "terminology", "Spell out notification.", "transaction notification"),
    ("Create a monthly budget cap that keeps you on track.", "monthly budget cap", "T07", "terminology", "Implies the optional target blocks spending.", "monthly spending target"),
    ("Scroll your money timeline to find a payment.", "money timeline", "T08", "terminology", "Use the approved term.", "account activity"),
    ("Questions? Call the Lumora hotline.", "Lumora hotline", "T09", "terminology", "Use the approved term.", "in-app support"),
    ("Each spend bucket shows what you spent this month.", "spend bucket", "T10", "terminology", "Use the approved term.", "spending category"),
    ("Change your email in the user console.", "user console", "T11", "terminology", "Use the approved label.", "profile settings"),
    ("Download your monthly ledger as a PDF.", "monthly ledger", "T14", "terminology", "Use the approved term.", "monthly activity statement"),
    ("Every pre-qualified member gets the upgrade.", "pre-qualified member", "T15", "terminology", "Implies guaranteed approval.", "eligible customer"),
    # outdated_fact: expired facts F01-F08
    ("Lumora Pay has 2 million registered users.", "Lumora Pay has 2 million registered users.", "F01", "outdated_fact", "Repeats a fact that expired on 2026-09-30.", "Ask the Comms team for the current figure."),
    ("Join over 2M people who use Lumora Pay.", "Join over 2M people who use Lumora Pay.", "F01", "outdated_fact", "Reworded version of an expired fact.", "Ask the Comms team for the current figure."),
    ("Lumora Pay supports transfers in 12 currencies.", "Lumora Pay supports transfers in 12 currencies.", "F02", "outdated_fact", "Repeats a fact that expired on 2026-08-31.", "Check the current availability sheet."),
    ("The Lumora app has a 4.8 out of 5 average rating.", "The Lumora app has a 4.8 out of 5 average rating.", "F03", "outdated_fact", "Repeats a fact that expired on 2026-07-31.", "Use a current app store rating."),
    ("Lumora customers made 5 million transfers in Q1 2026.", "Lumora customers made 5 million transfers in Q1 2026.", "F04", "outdated_fact", "Repeats a fact that expired on 2026-06-30.", "Ask the Data team for current figures."),
    ("Lumora Pay is available in 8 markets.", "Lumora Pay is available in 8 markets.", "F07", "outdated_fact", "Repeats a fact that expired on 2026-08-15.", "Check the current market list."),
    ("Onboarding takes under 6 minutes on average, based on Lumora's Q1 2026 data.", "Onboarding takes under 6 minutes on average, based on Lumora's Q1 2026 data.", "F08", "outdated_fact", "Repeats a fact that expired on 2026-07-15.", "Ask Growth analytics for a current figure."),
    # claim
    ("Lumora Pay is the fastest payment app in India.", "the fastest payment app in India", "G07", "claim", "Superlative with no approved source.", "a quick way to pay"),
    ("Every transfer arrives instantly.", "Every transfer arrives instantly", "G07", "claim", "Unsupported claim; timing depends on destination.", "See the transfer estimate before you confirm"),
    ("Lumora is the best app for managing money.", "the best app for managing money", "G07", "claim", "Superlative with no approved source.", "an app that helps you manage money"),
    ("You are guaranteed to save money every month.", "guaranteed to save money every month", "G08", "claim", "Guarantees savings.", "able to track your savings each month"),
    ("Approval is guaranteed for everyone.", "Approval is guaranteed for everyone", "G08", "claim", "Guarantees approval.", "Available features may depend on eligibility"),
    ("All transfers are always free.", "All transfers are always free", "G09", "claim", "Fee claim without current approved details.", "Review any applicable fee before you confirm"),
    # tone
    ("Revolutionize your financial journey with our paradigm-shifting platform.", "Revolutionize your financial journey with our paradigm-shifting platform", "G01", "tone", "Hype and jargon.", "Manage your money in one simple app"),
    ("We would like to take this opportunity to inform you that your transfer has now been initiated.", "We would like to take this opportunity to inform you that", "G02", "tone", "Wordy; main point comes late.", "Your transfer is on its way."),
    ("Sign up now or miss your chance to get rich.", "Sign up now or miss your chance to get rich", "G03", "tone", "Pressure and promised outcome.", "Explore tools that can help you plan"),
    ("Act now before it's too late.", "Act now before it's too late", "G03", "tone", "Pushy urgency.", "Take a look when it suits you"),
    # accessibility
    ("Tap the green button above to continue.", "Tap the green button above", "G15", "accessibility", "Relies on colour and position alone.", "Select Continue"),
    ("When the icon turns red, your payment failed.", "When the icon turns red", "G15", "accessibility", "Status shown by colour only.", "When the status shows Failed"),
    ("Every smart investor knows what to do.", "Every smart investor knows what to do", "G14", "accessibility", "Assumes the reader's experience.", "Choose the option that works for you"),
    # messaging
    ("Our new infrastructure migration is now live.", "Our new infrastructure migration is now live", "G12", "messaging", "Leads with internal technology, not customer value.", "Payments now load faster for you"),
    ("Our engineering team rebuilt the payments backend this quarter.", "Our engineering team rebuilt the payments backend this quarter", "G12", "messaging", "Internal priorities before customer value.", "Your payments history now loads faster"),
    ("You're all set.", "You're all set", "G13", "messaging", "Doesn't say what happens next.", "Your transfer is submitted. We'll notify you when it arrives"),
]

FORMATS = ["social post", "email", "landing page", "push notification", "press snippet"]


def build(n: int, n_clean: int, prefix: str, seed: int) -> list[dict]:
    rng = random.Random(seed)
    out = []
    plan = [True] * n_clean + [False] * (n - n_clean)
    rng.shuffle(plan)
    for i, clean in enumerate(plan, 1):
        sents = rng.sample(CLEAN, rng.randint(2, 3))
        errors = []
        if not clean:
            for sent, span, sid, typ, why, fix in rng.sample(ERRORS, rng.randint(1, 3)):
                sents.insert(rng.randint(0, len(sents)), sent)
                errors.append({"type": typ, "exact_span": span, "rule_or_fact_id": sid,
                               "explanation": why, "suggested_fix": fix})
        text = " ".join(sents)
        assert all(e["exact_span"] in text for e in errors)
        out.append({"id": f"{prefix}{i:03d}", "format": rng.choice(FORMATS), "text": text,
                    "is_clean": clean, "errors": errors})
    return out


if __name__ == "__main__":
    for name, n, clean, seed in (("dev", 50, 12, 7), ("test", 100, 25, 2026)):
        rows = build(n, clean, f"{name}-", seed)
        (ROOT / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        print(name, len(rows), "samples,", sum(len(r["errors"]) for r in rows), "labels")
