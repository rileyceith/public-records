import argparse
import getpass
import re

from sqlalchemy import select

from app.core.security import hash_password
from app.database import SessionLocal, initialize_database
from app.models import User


def create_admin() -> None:
    initialize_database()
    import os

    email = (os.environ.get("ADMIN_EMAIL") or input("Administrator email: ")).strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise SystemExit("Enter a valid email address.")
    full_name = (os.environ.get("ADMIN_NAME") or input("Administrator name: ")).strip()
    if os.environ.get("ADMIN_PASSWORD"):
        password = confirmation = os.environ["ADMIN_PASSWORD"]
    else:
        password = getpass.getpass("Password (at least 12 characters): ")
        confirmation = getpass.getpass("Confirm password: ")
    if len(full_name) < 2:
        raise SystemExit("Enter a name with at least two characters.")
    if len(password) < 12:
        raise SystemExit("Choose a password with at least 12 characters.")
    if password != confirmation:
        raise SystemExit("The passwords do not match.")

    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == email)):
            raise SystemExit("An account with that email already exists.")
        db.add(
            User(email=email, full_name=full_name, password_hash=hash_password(password), role="admin", is_verified=True)
        )
        db.commit()
    print(f"Administrator account created for {email}.")


DEMO_AGENCIES = (
    ("Land Registry", "LAND", "Capital Region", "land@example.gov"),
    ("District Court", "COURT", "Capital Region", "court@example.gov"),
    ("City Planning Office", "PLAN", "Metro Area", "planning@example.gov"),
)
DEMO_TYPES = (
    ("Land title", "public", "12.50"),
    ("Court ruling", "restricted", "25.00"),
    ("Planning permit", "public", "5.00"),
)


def seed_demo() -> None:
    """Load sample agencies, record types and records so the catalog has something to browse."""
    from datetime import date
    from decimal import Decimal
    import uuid

    from app.models import Agency, Record, RecordType

    initialize_database()
    with SessionLocal() as db:
        if db.scalar(select(Agency.id)):
            raise SystemExit("Reference data already exists; demo data was not loaded.")
        agencies = {code: Agency(name=name, code=code, region=region, contact_email=email) for name, code, region, email in DEMO_AGENCIES}
        types = {name: RecordType(name=name, default_access=access, fee=Decimal(fee)) for name, access, fee in DEMO_TYPES}
        db.add_all([*agencies.values(), *types.values()])
        db.flush()
        samples = (
            ("LT-2024-0001", "Title deed, 12 Harbour Road", "Transfer of freehold title for 12 Harbour Road.", "Land title", "LAND", "published", "public", date(2024, 3, 14), 51.5072, -0.1276, ["property", "transfer"]),
            ("CR-2023-0457", "Ruling in Alvarez v. City Council", "Judgment on a zoning dispute; party details restricted.", "Court ruling", "COURT", "published", "restricted", date(2023, 11, 2), 51.5155, -0.1419, ["zoning", "appeal"]),
            ("PP-2025-0112", "Planning permit, riverside footbridge", "Permit for a new pedestrian footbridge.", "Planning permit", "PLAN", "published", "public", date(2025, 1, 20), 51.5033, -0.1195, ["infrastructure"]),
            ("PP-2025-0150", "Draft permit, market hall extension", "Awaiting review.", "Planning permit", "PLAN", "draft", "public", date(2025, 5, 9), 51.5, -0.12, ["draft"]),
        )
        for number, title, summary, type_name, code, record_status, access, event, lat, lng, tags in samples:
            db.add(
                Record(
                    id=str(uuid.uuid4()),
                    record_number=number,
                    title=title,
                    summary=summary,
                    record_type_id=types[type_name].id,
                    agency_id=agencies[code].id,
                    status=record_status,
                    access_level=access,
                    date_of_event=event,
                    date_filed=event,
                    latitude=lat,
                    longitude=lng,
                    location_address="London, UK",
                    tags=tags,
                )
            )
        db.commit()
    print("Demo agencies, record types and records loaded.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Public records maintenance commands")
    parser.add_argument("command", choices=["create-admin", "seed-demo"])
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin()
    elif args.command == "seed-demo":
        seed_demo()


if __name__ == "__main__":
    main()
