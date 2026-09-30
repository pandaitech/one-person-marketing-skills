"""Wizard content per platform: console steps, fields.

Mirrors guides/02-meta-app-fb-ig-threads.md. Keep this in sync if that guide
changes.
"""

META_FIELDS = [
    {"key": "fb_ig_token", "label": "Token Facebook + Instagram", "type": "password",
     "placeholder": "EAAG..."},
    {"key": "page_id", "label": "Page ID", "type": "text", "placeholder": "1234567890"},
    {"key": "ig_business_id", "label": "Instagram Business ID", "type": "text",
     "placeholder": "1789..."},
    {"key": "threads_token", "label": "Token Threads", "type": "password",
     "placeholder": "THQV..."},
]

PLATFORMS = {
    "meta": {
        "title": "Sambung Facebook, Instagram & Threads",
        "subtitle": "Satu app Meta untuk tiga platform. Tampal nilai yang anda salin dari setiap langkah.",
        "guide_section": "guides/02-meta-app-fb-ig-threads.md",
        "fields": META_FIELDS,
        "steps": [
            {
                "heading": "1. Cipta app Meta",
                "body": "Login, cipta app baharu (Create App), pilih ketiga-tiga use case: "
                        "Manage everything on your Page, Manage messaging & content on Instagram, "
                        "Access the Threads API. Pilih Business Portfolio yang ada Page dan IG anda.",
                "button_label": "Buka Meta for Developers",
                "url": "https://developers.facebook.com/apps",
            },
            {
                "heading": "2. Tambah permission",
                "body": "Dalam Use cases, Customize use case Page: tambah pages_manage_posts dan "
                        "pages_read_engagement. Customize use case Instagram (API setup with Facebook "
                        "login): tambah instagram_basic dan instagram_content_publish.",
                "button_label": "Buka Use cases app anda",
                "url": "https://developers.facebook.com/apps",
            },
            {
                "heading": "3. System user & assign assets",
                "body": "Dalam Business Settings: Users -> System users, buat/guna satu (role Admin). "
                        "Assign assets: Page (Full control), Instagram account (Full control), App "
                        "'Content API' (Full control).",
                "button_label": "Buka Business Settings",
                "url": "https://business.facebook.com/settings",
            },
            {
                "heading": "4. Generate token Facebook + Instagram",
                "body": "Dalam System users, klik Generate token. Select app anda, Expiration: Never. "
                        "Tanda: pages_show_list, pages_read_engagement, pages_manage_posts, "
                        "instagram_basic, instagram_content_publish, business_management. Copy token "
                        "dan tampal di bawah.",
                "button_label": "Buka Business Settings",
                "url": "https://business.facebook.com/settings",
            },
            {
                "heading": "5. Dapatkan Page ID & Instagram ID",
                "body": "Buka Graph API Explorer, tampal token di atas dalam kotak Access Token, taip "
                        "me/accounts?fields=name,id,instagram_business_account dan Submit. Catat id "
                        "Page dan id dalam instagram_business_account, tampal di bawah.",
                "button_label": "Buka Graph API Explorer",
                "url": "https://developers.facebook.com/tools/explorer",
            },
            {
                "heading": "6. Token Threads",
                "body": "Customize use case Access the Threads API (pastikan threads_basic dan "
                        "threads_content_publish ada). App roles -> Roles -> Add People -> Threads "
                        "Tester -> username Threads anda. Di telefon, buka app Threads, Settings -> "
                        "Account -> Website permissions -> Invites -> Accept. Balik ke Customize "
                        "Threads -> User Token Generator -> Generate Access Token -> Copy.",
                "button_label": "Buka Use cases app anda",
                "url": "https://developers.facebook.com/apps",
            },
        ],
    },
}


def get(platform):
    return PLATFORMS[platform]
