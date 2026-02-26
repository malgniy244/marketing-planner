from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import os
import json
import psycopg
from psycopg.rows import dict_row
from functools import wraps
from datetime import datetime

app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'mkt-planner-secret-2026')
CORS(app, supports_credentials=True)

APP_PASSWORD = os.environ.get('APP_PASSWORD', 'crystal2026')

DATABASE_URL = (
    os.environ.get('POSTGRES_URL') or
    os.environ.get('DATABASE_PUBLIC_URL') or
    os.environ.get('DATABASE_URL')
)

# ─── DB Connection ─────────────────────────────────────────────────────────────
def get_db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

# ─── DB Init ───────────────────────────────────────────────────────────────────
def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            # Auction cycles table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS auction_cycles (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    auction_date_start DATE,
                    auction_date_end DATE,
                    location TEXT DEFAULT 'Hong Kong',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Ideas bank - master list of all marketing ideas/tasks
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ideas (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT,         -- e.g. 'eblast', 'social_media', 'print', 'video', 'logistics', 'admin'
                    phase TEXT,            -- 'pre_auction', 'on_show', 'post_auction', 'recurring'
                    description TEXT,
                    first_done_cycle TEXT,
                    times_done INT DEFAULT 0,
                    is_recurring BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Per-cycle task decisions
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cycle_tasks (
                    id SERIAL PRIMARY KEY,
                    cycle_id INT REFERENCES auction_cycles(id) ON DELETE CASCADE,
                    idea_id INT REFERENCES ideas(id) ON DELETE SET NULL,
                    title TEXT NOT NULL,
                    category TEXT,
                    phase TEXT,
                    status TEXT DEFAULT 'idea',  -- 'idea', 'confirmed', 'in_progress', 'completed', 'skipped'
                    decision TEXT DEFAULT 'undecided', -- 'do', 'skip', 'defer', 'undecided'
                    due_date DATE,
                    assigned_to TEXT DEFAULT 'Ceci Yeung',
                    notes TEXT,
                    repeat_flag TEXT DEFAULT 'undecided', -- 'always_do', 'never_again', 'case_by_case', 'undecided'
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Comments on tasks
            cur.execute("""
                CREATE TABLE IF NOT EXISTS task_comments (
                    id SERIAL PRIMARY KEY,
                    cycle_task_id INT REFERENCES cycle_tasks(id) ON DELETE CASCADE,
                    author TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
        conn.commit()
    seed_data()

def seed_data():
    """Seed initial auction cycles and ideas bank from historical data."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # Check if already seeded
            cur.execute("SELECT COUNT(*) as cnt FROM ideas")
            row = cur.fetchone()
            if row['cnt'] > 0:
                return

            # ── Seed Auction Cycles ──
            cycles = [
                ('APR HK26', '2026-04-13', '2026-04-21', 'Hong Kong'),
                ('JUN 2026',  '2026-06-01', '2026-06-07', 'Hong Kong'),
                ('OCT 2026',  '2026-10-01', '2026-10-07', 'Hong Kong'),
                ('DEC 2026',  '2026-12-01', '2026-12-07', 'Hong Kong'),
            ]
            for c in cycles:
                cur.execute("""
                    INSERT INTO auction_cycles (name, auction_date_start, auction_date_end, location)
                    VALUES (%s, %s, %s, %s) ON CONFLICT (name) DO NOTHING
                """, c)

            # ── Seed Ideas Bank ──
            # Derived from: HKofficeTasksMatrix-Ceci.csv history + Ideasofmarketing.csv
            ideas = [
                # --- EBLAST ---
                ('E-Catalog Preview Eblast', 'eblast', 'pre_auction', 'Send eblast announcing the e-catalog is live with preview highlights.', 'OCT 2025', 5, True),
                ('Session Highlights Eblast (per session)', 'eblast', 'pre_auction', 'Individual eblast for each session highlighting key lots. Repeat per session A/B/C etc.', 'OCT 2025', 5, True),
                ('Lot Viewing Schedule Eblast', 'eblast', 'pre_auction', 'Eblast with full lot viewing schedule and location details.', 'OCT 2025', 5, True),
                ('Bid Limit & Phone Bid Details Eblast', 'eblast', 'pre_auction', 'Eblast explaining how to increase bid limit and arrange phone bids.', 'OCT 2025', 4, True),
                ('HKCS Details Eblast', 'eblast', 'pre_auction', 'Eblast with Hong Kong Coin Show details and schedule.', 'OCT 2025', 4, True),
                ('Countdown Eblast (per session)', 'eblast', 'pre_auction', 'Countdown eblast for each session, sent 1-2 days before session starts.', 'OCT 2025', 5, True),
                ('Show Notice Eblast', 'eblast', 'pre_auction', 'Eblast announcing upcoming coin show (SG, TH, PH, etc.).', 'OCT 2025', 5, True),
                ('Consignment Deadline Eblast', 'eblast', 'pre_auction', 'Eblast reminding clients of consignment deadline for next auction.', 'OCT 2025', 4, True),
                ('Call for Consignment Eblast', 'eblast', 'pre_auction', 'General call for consignment eblast, mention TIB coins, grading, Z-lots, roll-overs.', 'OCT 2025', 3, True),
                ('Price Realized Eblast (post-auction)', 'eblast', 'post_auction', 'Send price realized results after auction concludes.', 'OCT 2025', 5, True),
                ('Mid-Autumn Festival / Holiday Greeting Eblast', 'eblast', 'pre_auction', 'Seasonal greeting eblast tied to upcoming holiday.', 'OCT 2025', 3, False),
                ('US Auction Highlights Eblast', 'eblast', 'pre_auction', 'Promote US auction session highlights to HK client base.', 'AUG 2025', 3, False),

                # --- SOCIAL MEDIA & WECHAT ---
                ('Social Media Post - E-Catalog & Preview Schedule', 'social_media', 'pre_auction', 'Post on IG/FB/WeChat announcing e-catalog and preview schedule.', 'OCT 2025', 5, True),
                ('Social Media Post - Session Highlights (per session)', 'social_media', 'pre_auction', 'Individual highlight posts per session on all platforms.', 'OCT 2025', 5, True),
                ('Social Media Post - Countdown (per session)', 'social_media', 'pre_auction', 'Countdown posts for each session across IG/FB/WeChat.', 'OCT 2025', 5, True),
                ('Social Media Post - Show Notice', 'social_media', 'pre_auction', 'Post announcing upcoming coin show attendance.', 'OCT 2025', 5, True),
                ('Social Media Post - Price Realized', 'social_media', 'post_auction', 'Post top price realized results after auction.', 'OCT 2025', 5, True),
                ('Coin / Banknote of the Week (Reel)', 'social_media', 'pre_auction', 'Weekly reel featuring a notable coin or banknote from the upcoming auction.', 'OCT 2025', 4, True),
                ('Reel - Lot Viewing', 'social_media', 'on_show', 'Short reel filmed during lot viewing period.', 'OCT 2025', 4, True),
                ('Reel - Coin Show Floor', 'social_media', 'on_show', 'Reel filmed at the coin show floor during the event.', 'OCT 2025', 4, True),
                ('Reel - Auctioneer on Stage', 'social_media', 'on_show', 'Reel of auctioneer in action during live session.', 'OCT 2025', 4, True),
                ('Reel - Rarities Night Highlights', 'social_media', 'on_show', 'Reel of Rarities Night top lots and atmosphere.', 'OCT 2025', 2, False),
                ('Reel - Ship Out Orders', 'social_media', 'post_auction', 'Reel showing order packing and shipping after auction.', 'OCT 2025', 1, False),
                ('Reel - Preview / Expert Insight', 'social_media', 'pre_auction', 'Expert commentary reel on a significant lot (coin or banknote).', 'OCT 2025', 3, True),
                ('Fun Friday Reel (repost funny coin/BN content)', 'social_media', 'recurring', 'Weekly fun Friday reel - repost amusing numismatic content.', 'AUG 2025', 3, True),
                ('WeChat Public Page - Full Schedule + E-Catalog', 'social_media', 'pre_auction', 'Post full auction schedule and e-catalog link on WeChat public page.', 'OCT 2025', 5, True),
                ('WhatsApp Channel Post', 'social_media', 'pre_auction', 'Push key messages to WhatsApp channel (schedule, consignment DDL, preview).', 'OCT 2025', 2, False),
                ('Red Note (Xiaohongshu) Post', 'social_media', 'pre_auction', 'Post on Red Note / Xiaohongshu for mainland China audience.', 'OCT 2025', 2, False),
                ('Red Note - Wallpaper (Lot Feature)', 'social_media', 'pre_auction', 'Post a lot image formatted as a wallpaper on Red Note.', 'OCT 2025', 2, False),
                ('Social Media Monthly Plan', 'social_media', 'pre_auction', 'Prepare and schedule the full monthly social media content calendar.', 'MAY 2025', 5, True),
                ('Facebook Banner Update', 'social_media', 'pre_auction', 'Update Facebook page banner to reflect upcoming auction.', 'OCT 2025', 4, True),
                ('Guess the Grade (Interactive Post)', 'social_media', 'pre_auction', 'Post a coin image and ask followers to guess the grade. Engagement driver.', None, 0, False),
                ('Guess the Coin (Cropped Image Post)', 'social_media', 'pre_auction', 'Post a cropped/bite-sized image of a coin or banknote and ask followers to identify it.', None, 0, False),
                ('AI Voice Clone - Expert Insight Video', 'social_media', 'pre_auction', 'Use AI voice cloning to create an expert commentary video for a key lot.', 'OCT 2025', 1, False),
                ('AI Video - Coin/BN with Interesting Story', 'social_media', 'pre_auction', 'Create an AI-generated video for a coin or banknote with a compelling historical story.', None, 0, False),
                ('Office Introduction Video/Post', 'social_media', 'recurring', 'Behind-the-scenes office introduction content for social media.', None, 0, False),
                ('Group Photo / Team Video Post', 'social_media', 'pre_auction', 'Post a team group photo or short video on social media.', 'OCT 2025', 2, False),
                ('Catalog Printing Sound Reel', 'social_media', 'pre_auction', 'Short satisfying reel of catalogs being printed/shipped.', 'OCT 2025', 1, False),
                ('Send Highlights to PCGS / NGC', 'social_media', 'pre_auction', 'Share auction highlights with PCGS and NGC for potential reposting.', 'OCT 2025', 3, True),
                ('KOL Collaboration', 'social_media', 'pre_auction', 'Engage a Key Opinion Leader (KOL) for sponsored post or collaboration.', 'OCT 2025', 1, False),

                # --- PRINT MATERIALS ---
                ('Auction Flyer (General)', 'print', 'pre_auction', 'Design and print the main auction flyer for distribution.', 'APR 2026', 5, True),
                ('Highlights Booklet (Coin)', 'print', 'pre_auction', 'Print highlights booklet for coin sessions.', 'OCT 2025', 5, True),
                ('Highlights Booklet (Banknotes)', 'print', 'pre_auction', 'Print highlights booklet for banknote sessions.', 'OCT 2025', 4, True),
                ('Reference Booklet (Coin + BN combined)', 'print', 'pre_auction', 'Comprehensive reference booklet combining coin and banknote highlights.', 'FEB 2026', 2, False),
                ('Easel Stand (Auction Entry)', 'print', 'pre_auction', 'Design and print easel stand for office/venue entry.', 'OCT 2025', 5, True),
                ('Easel Stand (Rarities Night)', 'print', 'pre_auction', 'Easel stand specifically for Rarities Night event.', 'OCT 2025', 4, True),
                ('Foam Board - VIP / Buffet Lunch', 'print', 'pre_auction', 'Foam board for VIP-only Buffet Lunch area.', 'OCT 2025', 3, False),
                ('Foam Board - Press Area', 'print', 'pre_auction', 'Foam board for press/media area at the auction venue.', 'OCT 2025', 2, False),
                ('Table Easel Stand / QR Code Board', 'print', 'pre_auction', 'Table-top easel stand with QR code for lot browsing or bidding.', 'OCT 2025', 4, True),
                ('Roll-Up Banner', 'print', 'pre_auction', 'Roll-up banner for office entrance or show booth.', 'OCT 2025', 4, True),
                ('Buffet Lunch Invitation Card', 'print', 'pre_auction', 'Design and print invitation cards for VIP buffet lunch.', 'OCT 2025', 3, False),
                ('Insert Card (Catalog)', 'print', 'pre_auction', 'Insert card to be placed inside catalog packages.', 'OCT 2025', 3, False),
                ('Lot Viewing Info Card (HKCS)', 'print', 'pre_auction', 'Info card with lot viewing schedule for HKCS.', 'OCT 2025', 3, True),
                ('Display Showcase Canvas', 'print', 'pre_auction', 'Canvas artwork for display showcase at auction venue.', 'OCT 2025', 3, False),
                ('Wall Artwork (Coin Highlights)', 'print', 'pre_auction', 'Large wall artwork featuring key coin highlights.', 'OCT 2025', 3, False),
                ('Podium Sticker', 'print', 'pre_auction', 'Branded sticker for the auctioneer podium.', 'OCT 2025', 3, True),
                ('Name Card Reprint / Revision', 'print', 'recurring', 'Reprint or revise staff name cards as needed.', 'APR 2026', 2, False),
                ('Auction Schedule Print', 'print', 'pre_auction', 'Print physical copies of the full auction schedule.', 'DEC 2025', 4, True),
                ('One-Page Press Brief (A4)', 'print', 'pre_auction', 'One-page press brief for media distribution.', 'DEC 2025', 2, False),
                ('Sycee Booklet', 'print', 'pre_auction', 'Specialty booklet for sycee lots.', 'OCT 2025', 2, False),

                # --- VIDEO ---
                ('HKCS Video (Lot Filming)', 'video', 'pre_auction', 'Film and edit video of key lots at HKCS for promotional use.', 'OCT 2025', 4, True),
                ('Rarities Night Shooting', 'video', 'on_show', 'Photo/video shooting at Rarities Night event.', 'OCT 2025', 4, True),
                ('HKCS Shooting (Afternoon)', 'video', 'on_show', 'Photo/video shooting at HKCS during afternoon hours.', 'OCT 2025', 4, True),
                ('Coin Motion Video (single lot)', 'video', 'pre_auction', 'Animated motion video for a featured lot.', 'OCT 2025', 3, False),
                ('Preview Reel (Expert/Specialist)', 'video', 'pre_auction', 'Preview reel featuring a specialist or expert discussing key lots.', 'OCT 2025', 3, True),
                ('10 Coins Take Video', 'video', 'pre_auction', 'Short video featuring 10 highlighted coins from the auction.', 'OCT 2025', 3, False),
                ('Auction Progress WeChat Updates (live)', 'video', 'on_show', 'Live WeChat updates during auction sessions reporting progress every 30-60 mins.', 'OCT 2025', 5, True),

                # --- SHOW LOGISTICS ---
                ('Pack Show Material (Flyers, Catalogs)', 'logistics', 'pre_auction', 'Pack and ship promotional materials to coin show venue.', 'OCT 2025', 5, True),
                ('Show Backdrop Design & Print', 'logistics', 'pre_auction', 'Design and print backdrop for coin show booth.', 'OCT 2025', 4, True),
                ('Show A4/A5 Ad Design', 'logistics', 'pre_auction', 'Design ad for coin show program book (A4 or A5 size).', 'OCT 2025', 5, True),
                ('Show Leaflet Card (print & ship)', 'logistics', 'pre_auction', 'Print and ship leaflet cards for distribution at coin show.', 'OCT 2025', 4, True),
                ('Show Notice Post (Social + Eblast)', 'logistics', 'pre_auction', 'Post show notice on social media and send eblast.', 'OCT 2025', 5, True),
                ('Send Catalog to Show Organizer / Partner', 'logistics', 'pre_auction', 'Send physical catalogs to show organizer or partner (e.g. MSIF, KLINF).', 'OCT 2025', 4, True),
                ('Send Promotional Material to Show', 'logistics', 'pre_auction', 'Ship full set of promotional materials to show venue.', 'OCT 2025', 4, True),
                ('Shipping Declaration', 'logistics', 'pre_auction', 'Prepare customs declaration for shipping promotional materials.', 'OCT 2025', 5, True),
                ('LED Screen Ad (Show Venue)', 'logistics', 'pre_auction', 'Design ad for LED screen at show venue (e.g. KLINF 1920x1024px).', 'FEB 2026', 2, False),
                ('Show Video (Booth Screen)', 'logistics', 'pre_auction', 'Video for display on booth screen at coin show.', 'OCT 2025', 3, True),
                ('Table Cloth / Table Setup', 'logistics', 'pre_auction', 'Arrange table cloth or QR code board for show table setup.', 'OCT 2025', 2, False),

                # --- DIGITAL / WEB ---
                ('Website Banner Update (Shouxi / Partner)', 'digital', 'pre_auction', 'Update web banner on Shouxi or partner websites.', 'OCT 2025', 4, True),
                ('Website Banner Update (Facebook)', 'digital', 'pre_auction', 'Update Facebook page cover banner for upcoming auction.', 'OCT 2025', 4, True),
                ('HK Landing Page Content Update', 'digital', 'pre_auction', 'Update the HK auction landing page with new content and images.', 'OCT 2025', 3, True),
                ('Google Business Profile Update', 'digital', 'recurring', 'Update Google Business Profile with latest auction info.', 'OCT 2025', 2, False),
                ('WeChat Payment Page Update', 'digital', 'recurring', 'Update WeChat payment page with current credit card fee info.', 'DEC 2025', 2, False),
                ('Expert Page Photo Retouch & IT Request', 'digital', 'recurring', 'Retouch expert/specialist photos and submit IT request for website update.', 'JUN 2025', 2, False),
                ('Meta Ad Campaign', 'digital', 'pre_auction', 'Run paid Meta (Facebook/Instagram) ad campaign for auction promotion.', 'OCT 2025', 3, False),
                ('Shouxi Ad Booking', 'digital', 'pre_auction', 'Book and submit ad for Shouxi numismatic platform.', 'OCT 2025', 4, True),
                ('ESC Ad (Coin Show Program)', 'digital', 'pre_auction', 'Submit ad for ESC (European/other) coin show program.', 'JUL 2025', 3, False),
                ('Split PDF & Distribute (QR, Groups, WTS)', 'digital', 'pre_auction', 'Split catalog PDF and distribute to 123 group, QR code, Ping, WTS channel.', 'JUN 2025', 4, True),
                ('Social Media Report', 'digital', 'post_auction', 'Compile social media performance report after auction cycle.', 'APR 2026', 3, True),
                ('Followers Growth Tracking', 'digital', 'post_auction', 'Track and record follower growth on IG and FB during auction cycle.', 'OCT 2025', 3, True),
                ('Order Tracking Report', 'digital', 'post_auction', 'Compile order tracking summary report after auction.', 'JUN 2025', 4, True),
                ('Marketing Report', 'digital', 'post_auction', 'Full marketing performance report for the auction cycle.', 'NOV 2025', 3, True),

                # --- ADMIN / RECURRING ---
                ('Invoice and Packing List', 'admin', 'recurring', 'Prepare invoice and packing list for shipments.', 'APR 2026', 5, True),
                ('Petty Cash Submission (by 20th)', 'admin', 'recurring', 'Submit petty cash claims to accounting by the 20th of each month.', 'OCT 2025', 5, True),
                ('Order Bonaqua Water', 'admin', 'recurring', 'Order Bonaqua water for office/auction use.', 'OCT 2025', 5, True),
                ('Leave Record Update', 'admin', 'recurring', 'Update monthly leave record.', 'OCT 2025', 5, True),
                ('Marketing Plan (Monthly)', 'admin', 'pre_auction', 'Prepare monthly marketing plan document.', 'MAY 2025', 5, True),
                ('Rarity Night Price Realized Report', 'admin', 'post_auction', 'Compile and send Rarities Night price realized report to relevant parties.', 'OCT 2025', 4, True),
                ('Send Highlights to Jordan / Partners', 'admin', 'post_auction', 'Send auction highlights to Jordan and other partners post-auction.', 'JUN 2025', 3, True),
                ('Credit Card Payment (Eblast + WeChat)', 'admin', 'recurring', 'Process credit card payment for eblast and WeChat page services.', 'APR 2026', 3, True),
                ('Photo Taking Session', 'admin', 'pre_auction', 'Arrange photo taking session for key lots.', 'FEB 2026', 4, True),
            ]

            for idea in ideas:
                cur.execute("""
                    INSERT INTO ideas (title, category, phase, description, first_done_cycle, times_done, is_recurring)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, idea)

        conn.commit()

# ─── Auth ──────────────────────────────────────────────────────────────────────
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if data.get('password') == APP_PASSWORD:
        session['authenticated'] = True
        return jsonify({'ok': True})
    return jsonify({'error': 'Invalid password'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/check-auth')
def check_auth():
    return jsonify({'authenticated': bool(session.get('authenticated'))})

# ─── Auction Cycles ────────────────────────────────────────────────────────────
@app.route('/api/cycles', methods=['GET'])
@require_auth
def get_cycles():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM auction_cycles ORDER BY auction_date_start DESC")
            return jsonify(cur.fetchall())

@app.route('/api/cycles', methods=['POST'])
@require_auth
def create_cycle():
    data = request.get_json()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO auction_cycles (name, auction_date_start, auction_date_end, location)
                VALUES (%s, %s, %s, %s) RETURNING *
            """, (data['name'], data.get('auction_date_start'), data.get('auction_date_end'), data.get('location', 'Hong Kong')))
            result = cur.fetchone()
        conn.commit()
    return jsonify(result)

# ─── Ideas Bank ────────────────────────────────────────────────────────────────
@app.route('/api/ideas', methods=['GET'])
@require_auth
def get_ideas():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM ideas ORDER BY category, phase, title")
            return jsonify(cur.fetchall())

@app.route('/api/ideas', methods=['POST'])
@require_auth
def create_idea():
    data = request.get_json()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ideas (title, category, phase, description, is_recurring)
                VALUES (%s, %s, %s, %s, %s) RETURNING *
            """, (data['title'], data.get('category', 'other'), data.get('phase', 'pre_auction'),
                  data.get('description', ''), data.get('is_recurring', False)))
            result = cur.fetchone()
        conn.commit()
    return jsonify(result)

@app.route('/api/ideas/<int:idea_id>', methods=['PATCH'])
@require_auth
def update_idea(idea_id):
    data = request.get_json()
    allowed = ['title', 'category', 'phase', 'description', 'is_recurring', 'times_done']
    sets = []
    vals = []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            vals.append(data[key])
    if not sets:
        return jsonify({'error': 'No fields to update'}), 400
    vals.append(idea_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE ideas SET {', '.join(sets)} WHERE id = %s RETURNING *", vals)
            result = cur.fetchone()
        conn.commit()
    return jsonify(result)

@app.route('/api/ideas/<int:idea_id>', methods=['DELETE'])
@require_auth
def delete_idea(idea_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ideas WHERE id = %s", (idea_id,))
        conn.commit()
    return jsonify({'ok': True})

# ─── Cycle Tasks ───────────────────────────────────────────────────────────────
@app.route('/api/cycles/<int:cycle_id>/tasks', methods=['GET'])
@require_auth
def get_cycle_tasks(cycle_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ct.*, i.times_done as idea_times_done, i.first_done_cycle, i.is_recurring as idea_recurring
                FROM cycle_tasks ct
                LEFT JOIN ideas i ON ct.idea_id = i.id
                WHERE ct.cycle_id = %s
                ORDER BY ct.phase, ct.category, ct.title
            """, (cycle_id,))
            return jsonify(cur.fetchall())

@app.route('/api/cycles/<int:cycle_id>/tasks', methods=['POST'])
@require_auth
def add_task_to_cycle(cycle_id):
    data = request.get_json()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cycle_tasks (cycle_id, idea_id, title, category, phase, status, decision, due_date, assigned_to, notes, repeat_flag)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *
            """, (cycle_id, data.get('idea_id'), data['title'], data.get('category', 'other'),
                  data.get('phase', 'pre_auction'), data.get('status', 'idea'),
                  data.get('decision', 'undecided'), data.get('due_date'),
                  data.get('assigned_to', 'Ceci Yeung'), data.get('notes', ''),
                  data.get('repeat_flag', 'undecided')))
            result = cur.fetchone()
        conn.commit()
    return jsonify(result)

@app.route('/api/tasks/<int:task_id>', methods=['PATCH'])
@require_auth
def update_task(task_id):
    data = request.get_json()
    allowed = ['status', 'decision', 'due_date', 'assigned_to', 'notes', 'repeat_flag', 'title', 'category', 'phase']
    sets = []
    vals = []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            vals.append(data[key])
    if not sets:
        return jsonify({'error': 'No fields to update'}), 400
    sets.append("updated_at = NOW()")
    vals.append(task_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE cycle_tasks SET {', '.join(sets)} WHERE id = %s RETURNING *", vals)
            result = cur.fetchone()
        conn.commit()
    return jsonify(result)

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@require_auth
def delete_task(task_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cycle_tasks WHERE id = %s", (task_id,))
        conn.commit()
    return jsonify({'ok': True})

# ─── Bulk add ideas to cycle ───────────────────────────────────────────────────
@app.route('/api/cycles/<int:cycle_id>/add-ideas', methods=['POST'])
@require_auth
def bulk_add_ideas(cycle_id):
    data = request.get_json()
    idea_ids = data.get('idea_ids', [])
    override_phase = data.get('override_phase')  # optional: from drag-and-drop to specific phase zone
    added = []
    with get_db() as conn:
        with conn.cursor() as cur:
            for idea_id in idea_ids:
                # Check not already added
                cur.execute("SELECT id FROM cycle_tasks WHERE cycle_id=%s AND idea_id=%s", (cycle_id, idea_id))
                if cur.fetchone():
                    continue
                cur.execute("SELECT * FROM ideas WHERE id=%s", (idea_id,))
                idea = cur.fetchone()
                if idea:
                    phase = override_phase if override_phase else idea['phase']
                    cur.execute("""
                        INSERT INTO cycle_tasks (cycle_id, idea_id, title, category, phase, status, decision)
                        VALUES (%s, %s, %s, %s, %s, 'idea', 'undecided') RETURNING *
                    """, (cycle_id, idea_id, idea['title'], idea['category'], phase))
                    added.append(cur.fetchone())
        conn.commit()
    return jsonify(added)

# ─── Comments ──────────────────────────────────────────────────────────────────
@app.route('/api/tasks/<int:task_id>/comments', methods=['GET'])
@require_auth
def get_comments(task_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM task_comments WHERE cycle_task_id=%s ORDER BY created_at ASC", (task_id,))
            return jsonify(cur.fetchall())

@app.route('/api/tasks/<int:task_id>/comments', methods=['POST'])
@require_auth
def add_comment(task_id):
    data = request.get_json()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO task_comments (cycle_task_id, author, comment)
                VALUES (%s, %s, %s) RETURNING *
            """, (task_id, data.get('author', 'Team'), data['comment']))
            result = cur.fetchone()
        conn.commit()
    return jsonify(result)

# ─── Stats ─────────────────────────────────────────────────────────────────────
@app.route('/api/cycles/<int:cycle_id>/stats', methods=['GET'])
@require_auth
def get_cycle_stats(cycle_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE decision='do') as confirmed,
                    COUNT(*) FILTER (WHERE decision='skip') as skipped,
                    COUNT(*) FILTER (WHERE decision='defer') as deferred,
                    COUNT(*) FILTER (WHERE decision='undecided') as undecided,
                    COUNT(*) FILTER (WHERE status='completed') as completed,
                    COUNT(*) as total
                FROM cycle_tasks WHERE cycle_id=%s
            """, (cycle_id,))
            return jsonify(cur.fetchone())

# ─── Initialize DB on startup (runs when gunicorn imports the module) ──────────
with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f'DB init error: {e}')

# ─── Serve frontend ────────────────────────────────────────────────────────────
@app.route('/')
@app.route('/<path:path>')
def serve(path='index.html'):
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
