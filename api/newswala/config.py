"""
NewsWala — Family & system configuration.
Edit this file to update family details, sources, or quality thresholds.
"""

FAMILY = {
    "parents": ["Yash", "Pooja"],
    "signoff": "Love, Mama & Papa",
    "daughters": [
        {
            "name": "Manishka",
            "age_turning": 18,
            "birthday": "24 October",
            "notes": "Nearly 18 — can handle nuance, complexity, and abstract ideas.",
        },
        {
            "name": "Divyana",
            "age_turning": 11,
            "birthday": "12 July",
            "notes": "Turning 11 — needs warmth, clarity, and simple framing.",
        },
    ],
    "pet": "a cocker spaniel",
}

# Email recipients — each gets a personalised morning digest
EMAIL_RECIPIENTS = [
    {
        "email": "Divyana.erande@oberoi-is.net",
        "name": "Divyana",
        "nickname": "Popcorn",          # used in greeting: "Good morning, Popcorn!"
        "alt_nickname": "Divvydoo",
    },
    {
        "email": "manishka.erande@oberoi-is.net",
        "name": "Manishka",
        "nickname": "Laddoo",
        "alt_nickname": "Mannuu",
    },
    {
        "email": "Pooja.Hathi@gmail.com",
        "name": "Pooja",
        "nickname": "Doll",
        "alt_nickname": "Darling",
    },
]

CATEGORIES = ["Economics", "STEM", "Current Affairs"]

PREFERRED_SOURCES = [
    "Reuters",
    "Associated Press",
    "BBC",
    "Financial Times",
    "The Economist",
    "Mint / LiveMint",
    "The Hindu",
    "Indian Express",
    "Business Standard",
    "ISRO / DRDO / PIB",
    "RBI / SEBI",
    "Nature",
    "Science",
]

AVOID_TOPICS = [
    "celebrity gossip",
    "graphic crime",
    "disturbing violence",
    "partisan political propaganda",
    "clickbait",
    "adult content",
    "fear-mongering",
]

MAX_STORIES = 2
WHATSAPP_MAX_CHARS = 800  # comfortable WhatsApp read length

MODEL = "claude-opus-4-6"
