import sqlite3
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Bangkok")
DB = "bookings.db"
OPEN_HOUR, CLOSE_HOUR = 10, 19
CLOSED_WEEKDAY = 2
MAX_DAYS_AHEAD = 14
CANCEL_HOURS = 3

SERVICES = {
    "womens_cut": {"name": "ตัดผมหญิง", "minutes": 45, "price": 350, "staff": "Fon"},
    "mens_cut": {"name": "ตัดผมชาย", "minutes": 30, "price": 250, "staff": "Ake"},
    "wash_blow_dry": {"name": "สระไดร์", "minutes": 30, "price": 200, "staff": "Mint"},
    "full_color": {"name": "ทำสีทั้งศีรษะ", "minutes": 120, "price": 1200, "staff": "Fon"},
    "highlights": {"name": "ไฮไลท์", "minutes": 150, "price": 1800, "staff": "Fon"},
    "treatment": {"name": "ทรีตเมนต์", "minutes": 45, "price": 600, "staff": "Mint"},
    "gel_manicure": {"name": "ทำเล็บเจล", "minutes": 60, "price": 450, "staff": "Mint"},
}


def connect():
    db = sqlite3.connect(DB)
    db.execute(
        "CREATE TABLE IF NOT EXISTS bookings ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT NOT NULL, "
        "service TEXT NOT NULL, staff TEXT NOT NULL, start TEXT NOT NULL, "
        "end TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'booked', created TEXT NOT NULL)"
    )
    return db


def now():
    return datetime.now(TZ).replace(tzinfo=None)


def day_problem(day):
    today = now().date()
    if day < today:
        return "That date is in the past."
    if day > today + timedelta(days=MAX_DAYS_AHEAD):
        return f"Bookings open only {MAX_DAYS_AHEAD} days ahead."
    if day.weekday() == CLOSED_WEEKDAY:
        return "The shop is closed on Wednesdays."
    return None


def is_busy(db, staff, start, end):
    row = db.execute(
        "SELECT COUNT(*) FROM bookings WHERE staff=? AND status='booked' AND start < ? AND end > ?",
        (staff, end.isoformat(), start.isoformat()),
    ).fetchone()
    return row[0] > 0


def check_availability(date_str, service):
    if service not in SERVICES:
        return {"error": f"Unknown service. Choose one of: {', '.join(SERVICES)}"}
    try:
        day = date.fromisoformat(date_str)
    except ValueError:
        return {"error": "Date must be YYYY-MM-DD."}
    problem = day_problem(day)
    if problem:
        return {"error": problem}

    s = SERVICES[service]
    length = timedelta(minutes=s["minutes"])
    slot = datetime.combine(day, time(OPEN_HOUR))
    closing = datetime.combine(day, time(CLOSE_HOUR))
    free = []
    with connect() as db:
        while slot + length <= closing:
            if slot > now() and not is_busy(db, s["staff"], slot, slot + length):
                free.append(slot.strftime("%H:%M"))
            slot += timedelta(minutes=30)
    return {"date": date_str, "service": s["name"], "staff": s["staff"], "free_times": free}


def book_appointment(customer, date_str, time_str, service):
    time_str = time_str[:5]
    available = check_availability(date_str, service)
    if "error" in available:
        return available
    if time_str not in available["free_times"]:
        return {"error": f"{time_str} is not free.", "free_times": available["free_times"]}

    s = SERVICES[service]
    start = datetime.fromisoformat(f"{date_str}T{time_str}")
    end = start + timedelta(minutes=s["minutes"])
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO bookings (customer, service, staff, start, end, created) VALUES (?, ?, ?, ?, ?, ?)",
            (customer, service, s["staff"], start.isoformat(), end.isoformat(), now().isoformat()),
        )
    return {
        "booking_id": cursor.lastrowid,
        "customer": customer,
        "service": s["name"],
        "staff": s["staff"],
        "start": start.strftime("%Y-%m-%d %H:%M"),
        "price_thb": s["price"],
    }


def cancel_appointment(booking_id, customer):
    with connect() as db:
        row = db.execute("SELECT customer, start, status FROM bookings WHERE id=?", (int(booking_id),)).fetchone()
        if not row or row[0].strip().lower() != customer.strip().lower():
            return {"error": "No booking with that id under this name."}
        if row[2] != "booked":
            return {"error": "This booking is already cancelled."}
        if datetime.fromisoformat(row[1]) - now() < timedelta(hours=CANCEL_HOURS):
            return {"error": f"Less than {CANCEL_HOURS} hours before the appointment. Please contact staff."}
        db.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (int(booking_id),))
    return {"cancelled_booking_id": int(booking_id)}

THAI_DAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]


def upcoming_days():
    today = now().date()
    lines = []
    for i in range(MAX_DAYS_AHEAD + 1):
        d = today + timedelta(days=i)
        label = "today" if i == 0 else "tomorrow" if i == 1 else ""
        closed = "CLOSED" if d.weekday() == CLOSED_WEEKDAY else ""
        lines.append(" ".join(p for p in [d.isoformat(), d.strftime("%a"), f"({THAI_DAYS[d.weekday()]})", label, closed] if p))
    return "; ".join(lines)
