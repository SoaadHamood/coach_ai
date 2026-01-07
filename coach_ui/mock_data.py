from dataclasses import dataclass


@dataclass
class WaitingCall:
    call_id: str
    customer: str
    topic: str
    wait_time: str
    risk: str  # low/med/high


@dataclass
class PastCall:
    call_id: str
    customer: str
    topic: str
    when: str
    grade: str


def waiting_calls():
    return [
        WaitingCall("W-1042", "Dana Levi", "Double charge", "02:10", "high"),
        WaitingCall("W-1045", "Omar Hassan", "Delivery delay", "01:12", "med"),
        WaitingCall("W-1049", "Noa Cohen", "Cancel subscription", "00:45", "low"),
    ]


def past_calls():
    return [
        PastCall("H-991", "Maya S.", "Refund status", "Yesterday", "A-"),
        PastCall("H-987", "Eli B.", "Login issue", "2 days ago", "B+"),
        PastCall("H-982", "Rami K.", "Upgrade plan", "Last week", "A"),
    ]


def live_script(call_id: str):
    transcript = [
        ("Customer", "Hi, I was charged twice this month and I’m really frustrated."),
        ("Agent", "I’m sorry — I can hear how frustrating that is. Let’s fix it together right now."),
        ("Customer", "I already called earlier and no one helped."),
        ("Agent", "Thank you for telling me. I’ll take ownership and stay with you until it’s resolved."),
        ("Customer", "Okay… so what do you need from me?"),
        ("Agent", "One quick thing: can you confirm the last 4 digits of the card and the billing date?"),
        ("Customer", "It’s 4421, and the date is the 3rd."),
        ("Agent", "Got it. I see the duplicate charge — I’m submitting a reversal now and sending you a confirmation email."),
        ("Customer", "When will the money actually return?"),
        ("Agent", "Within 3–5 business days. If it doesn’t show by then, I’ll open a priority ticket and update you."),
        ("Customer", "Okay… thank you. That’s the first clear answer I got."),
        ("Agent", "You deserve clarity — I’m sorry it took multiple calls. I’ll stay on the line until the email arrives."),
    ]

    suggestions = {
        1: ("De-escalate + validate", "One empathy line + ownership. Avoid policy details yet.", "high"),
        3: ("Restore trust", "Acknowledge prior failed attempt; commit to a clear next step.", "med"),
        5: ("Ask one thing", "Reduce cognitive load: ask for a single verification item at a time.", "med"),
        9: ("Clarity contract", "Action + timeframe + fallback plan if timeline fails.", "low"),
        11: ("Positive close", "Reflect relief and confirm you will remain available until completion.", "low"),
    }
    return transcript, suggestions


# NEW: Post-call analysis mock
def post_call_summary(call_id: str):
    return {
        "call_id": call_id,
        "overall": "Strong recovery after a frustrated opener. You established ownership early and closed with clear expectations.",
        "highlights": [
            "Used empathy + validation quickly (reduced escalation).",
            "Took ownership after the ‘I already called’ complaint (rebuilt trust).",
            "Provided a concrete timeline + fallback plan (clarity under pressure).",
        ],
        "improvements": [
            "After asking for verification, consider repeating the purpose in one short clause (keeps customer oriented).",
            "When giving timelines, confirm the channel (SMS/email) and next update step explicitly.",
            "Add one micro-check: “Does that plan work for you?” before closing.",
        ],
        "metrics": {
            "Empathy": 4.5,
            "Clarity": 4.2,
            "Control": 4.0,
            "Professionalism": 4.6,
        },
        "supervisor_note": "Customer was initially escalated; agent recovered well. Recommend reinforcing ‘plan confirmation’ before closing.",
    }
