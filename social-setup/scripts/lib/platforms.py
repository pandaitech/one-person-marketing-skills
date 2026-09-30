"""Wizard content per platform: console steps, fields, OAuth config.

Mirrors guides/02-meta-app-fb-ig-threads.md, guides/03-tiktok.md and
guides/04-youtube.md. Keep this in sync if those guides change.
"""

# YouTube deviates from guides/04-youtube.md on ONE point: the guide has the
# student create a "Web application" OAuth client and use Google's OAuth
# Playground to get a refresh token by hand. This wizard instead uses a
# "Desktop app" OAuth client with a local loopback redirect
# (http://127.0.0.1:<port>/oauth/callback), which Google's installed-app flow
# accepts on any port without pre-registering it. Same end result (Client ID /
# Secret / Refresh token), zero copy-pasting through the Playground. Every
# other YouTube step (project, API, branding, scopes, publish) matches the
# guide exactly.

META_FIELDS = [
    {"key": "fb_ig_token", "label": "Token Facebook + Instagram", "type": "password",
     "placeholder": "EAAG..."},
    {"key": "page_id", "label": "Page ID", "type": "text", "placeholder": "1234567890"},
    {"key": "ig_business_id", "label": "Instagram Business ID", "type": "text",
     "placeholder": "1789..."},
    {"key": "threads_token", "label": "Token Threads", "type": "password",
     "placeholder": "THQV..."},
]

TIKTOK_FIELDS = [
    {"key": "client_key", "label": "Client Key", "type": "text", "placeholder": "aw..."},
    {"key": "client_secret", "label": "Client Secret", "type": "password", "placeholder": "•••"},
]

YOUTUBE_FIELDS = [
    {"key": "client_id", "label": "Client ID", "type": "text",
     "placeholder": "xxxx.apps.googleusercontent.com"},
    {"key": "client_secret", "label": "Client Secret", "type": "password", "placeholder": "GOCSPX-..."},
]

PLATFORMS = {
    "meta": {
        "title": "Sambung Facebook, Instagram & Threads",
        "subtitle": "Satu app Meta untuk tiga platform. Tampal nilai yang anda salin dari setiap langkah.",
        "guide_section": "guides/02-meta-app-fb-ig-threads.md",
        "fields": META_FIELDS,
        "oauth": None,
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
    "tiktok": {
        "title": "Sambung TikTok",
        "subtitle": "App belum diaudit, jadi post pertama pergi ke inbox TikTok anda sebagai draft "
                     "-- anda tekan Post sekali di telefon.",
        "guide_section": "guides/03-tiktok.md",
        "fields": TIKTOK_FIELDS,
        "oauth": {
            "provider": "tiktok",
            "callback_path": "/callback",
            "authorize_path": "/tiktok/authorize",
            "scopes": "user.info.basic,video.upload,video.publish",
        },
        "steps": [
            {
                "heading": "1. Connect an app",
                "body": "Login di TikTok for Developers, Manage apps -> Connect an app -> Individual.",
                "button_label": "Buka TikTok for Developers",
                "url": "https://developers.tiktok.com",
            },
            {
                "heading": "2. Isi maklumat app",
                "body": "App icon 1024x1024px, App name: nama bisnes + 'Poster', Category: Business, "
                        "Description ringkas (contoh: hantar video bisnes ke inbox TikTok sendiri). "
                        "Terms of Service URL dan Privacy Policy URL dari website anda. Platform: "
                        "Desktop, dengan URL website anda.",
                "button_label": "Buka TikTok for Developers",
                "url": "https://developers.tiktok.com",
            },
            {
                "heading": "3. Tambah products & redirect URI",
                "body": "Add products -> Login Kit (Redirect URI mesti tepat: {redirect_uri}) dan "
                        "Content Posting API. Scopes: tanda user.info.basic, video.upload, "
                        "video.publish.",
                "button_label": "Buka TikTok for Developers",
                "url": "https://developers.tiktok.com",
            },
            {
                "heading": "4. Sandbox",
                "body": "Tukar ke Sandbox -> Create sandbox -> tambah akaun TikTok anda sebagai "
                        "Target user, login bila diminta.",
                "button_label": "Buka TikTok for Developers",
                "url": "https://developers.tiktok.com",
            },
            {
                "heading": "5. Copy Client Key & Client Secret",
                "body": "Salin Client key dan Client secret sandbox, tampal di bawah.",
                "button_label": "Buka TikTok for Developers",
                "url": "https://developers.tiktok.com",
            },
        ],
    },
    "youtube": {
        "title": "Sambung YouTube",
        "subtitle": "Google Cloud sampai dapat refresh token -- wizard ini log masuk terus, tak "
                     "perlu OAuth Playground.",
        "guide_section": "guides/04-youtube.md",
        "fields": YOUTUBE_FIELDS,
        "oauth": {
            "provider": "youtube",
            "callback_path": "/oauth/callback",
            "authorize_path": "/youtube/authorize",
            "scopes": "https://www.googleapis.com/auth/youtube.upload "
                      "https://www.googleapis.com/auth/youtube.readonly",
        },
        "steps": [
            {
                "heading": "1. Cipta project & enable API",
                "body": "New Project (nama: YouTube Upload) -> APIs & Services -> Library -> cari "
                        "YouTube Data API v3 -> Enable.",
                "button_label": "Buka Google Cloud Console",
                "url": "https://console.cloud.google.com",
            },
            {
                "heading": "2. Google Auth Platform: branding & scope",
                "body": "APIs & Services -> Google Auth Platform -> Get started. App name: YouTube "
                        "Upload, support email anda, Audience: External. Data Access -> Add or remove "
                        "scopes -> tanda youtube.upload dan youtube.readonly -> Save.",
                "button_label": "Buka Google Auth Platform",
                "url": "https://console.cloud.google.com/auth/overview",
            },
            {
                "heading": "3. Publish app",
                "body": "Audience -> Publish app -> Confirm, sampai status jadi 'In production'. "
                        "Jangan skip -- kalau kekal Testing, token mati dalam 7 hari.",
                "button_label": "Buka Audience",
                "url": "https://console.cloud.google.com/auth/audience",
            },
            {
                "heading": "4. Cipta OAuth client (Desktop app)",
                "body": "Clients -> Create client. Application type: Desktop app (BUKAN Web "
                        "application -- Desktop app benarkan wizard ini log masuk terus tanpa "
                        "daftar redirect URI). Name: PandaiTech Local Wizard. Copy Client ID dan "
                        "Client secret, tampal di bawah.",
                "button_label": "Buka Clients",
                "url": "https://console.cloud.google.com/auth/clients",
            },
        ],
    },
}


def get(platform):
    return PLATFORMS[platform]
