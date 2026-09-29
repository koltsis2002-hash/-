import random
from datetime import date, datetime, time, timedelta

from app.models.entities import Activity, Appointment, Contact, FollowUp, Goal, Production

# Fictional people only. Phones use the 69000xxxxx range and emails use example.com.
FIRST_NAMES = ["Γιώργος", "Μαρία", "Νίκος", "Ελένη", "Κώστας", "Αικατερίνη", "Δημήτρης", "Σοφία", "Γιάννης", "Άννα"]
LAST_NAMES = ["Παπαδόπουλος", "Νικολάου", "Γεωργίου", "Οικονόμου", "Αντωνίου", "Δημητρίου", "Ιωάννου", "Βασιλείου"]
COMPANIES = [None, "Φαρμακείο", "Κατάστημα", "Συνεργείο", "Λογιστικό γραφείο", "Εστιατόριο"]
PRODUCTS = ["Life", "Health", "Pension", "Savings", "Property"]
SOURCES = ["referral", "cold call", "event", "website"]


def _at(day: date, hour: int) -> str:
    return datetime.combine(day, time(hour)).isoformat(timespec="minutes")


def seed(services, today: date, contact_count: int = 30, rng_seed: int = 7) -> dict[str, int]:
    rng = random.Random(rng_seed)
    crm, planner, performance = services.crm, services.planner, services.performance

    contacts = []
    for i in range(contact_count):
        status = rng.choice(["lead", "lead", "prospect", "client", "inactive"])
        contacts.append(crm.contacts.add(Contact(
            first_name=rng.choice(FIRST_NAMES), last_name=rng.choice(LAST_NAMES),
            phone=f"69000{i:05d}", email=f"contact{i}@example.com", company=rng.choice(COMPANIES),
            source=rng.choice(SOURCES), status=status, product_interest=rng.choice(PRODUCTS),
            client_flag=status == "client",
        )))

    for c in contacts:
        if c.status == "lead" and rng.random() < 0.5:
            continue
        for _ in range(rng.randint(1, 3)):
            crm.activities.add(Activity(
                contact_id=c.id, activity_type=rng.choice(["call", "call", "meeting", "email"]),
                timestamp=_at(today - timedelta(days=rng.randint(1, 30)), rng.randint(9, 18)),
                outcome=rng.choice(["reached", "not_reached"]), product=c.product_interest, notes="Sample activity",
            ))

    for c in rng.sample(contacts, k=min(10, len(contacts))):
        planner.follow_ups.add(FollowUp(
            contact_id=c.id, due_at=_at(today + timedelta(days=rng.randint(-3, 5)), rng.randint(9, 17)),
            priority=rng.choice(["low", "normal", "high"]), reason="Sample follow-up",
        ))

    for offset, hour in [(0, 10), (0, 15), (1, 11), (3, 12)]:
        c = rng.choice(contacts)
        day = today + timedelta(days=offset)
        planner.appointments.add(Appointment(
            contact_id=c.id, start_at=_at(day, hour), end_at=_at(day, hour + 1),
            location="Office", purpose=f"{c.product_interest} review",
        ))

    year_start, year_end = date(today.year, 1, 1), date(today.year, 12, 31)
    month_start = today.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    for metric, yearly in [("calls", 2400), ("first_meetings", 240), ("contracts", 60), ("production", 120000)]:
        performance.goals.add(Goal(metric=metric, period_type="year", period_start=year_start.isoformat(),
                                   period_end=year_end.isoformat(), target_value=yearly))
        performance.goals.add(Goal(metric=metric, period_type="month", period_start=month_start.isoformat(),
                                   period_end=month_end.isoformat(), target_value=round(yearly / 12, 2)))

    for c in [c for c in contacts if c.status == "client"]:
        performance.production.add(Production(
            contact_id=c.id, product=c.product_interest,
            date=(today - timedelta(days=rng.randint(1, 60))).isoformat(),
            value=rng.choice([600, 900, 1200, 2500]), status=rng.choice(["pending", "issued"]),
        ))

    return {
        "contacts": crm.contacts.count(), "activities": crm.activities.count(),
        "follow_ups": planner.follow_ups.count(), "appointments": planner.appointments.count(),
        "goals": performance.goals.count(), "production": performance.production.count(),
    }
