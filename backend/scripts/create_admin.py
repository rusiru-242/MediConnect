"""Admin Account Provisioning Script for MediConnect.

Enables secure bootstrap of an initial administrative user for development and operations.
Accepts credentials via command line arguments, environment variables, or interactive input.
Never hardcodes credentials or exposes passwords in logs.
"""

import argparse
import getpass
import os
import sys
from pymongo import MongoClient

# Ensure app module is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config.settings import settings
from app.models.user import AccountStatus, UserDocument, UserRole, utc_now
from app.utils.security import hash_password


def create_admin():
    parser = argparse.ArgumentParser(description="Bootstrap an administrative user for MediConnect.")
    parser.add_argument("--email", help="Admin email address", default=os.getenv("ADMIN_EMAIL"))
    parser.add_argument("--password", help="Admin password", default=os.getenv("ADMIN_PASSWORD"))
    parser.add_argument("--name", help="Admin full name", default=os.getenv("ADMIN_FULL_NAME", "MediConnect Administrator"))
    parser.add_argument("--phone", help="Admin phone number", default=os.getenv("ADMIN_PHONE", "0770000000"))

    args = parser.parse_args()

    email = args.email
    password = args.password
    name = args.name
    phone = args.phone

    if not email:
        email = input("Enter Admin Email: ").strip()
    if not password:
        password = getpass.getpass("Enter Admin Password: ")
    if not name:
        name = input("Enter Admin Full Name: ").strip()

    if not email or not password or not name:
        print("Error: Email, password, and full name are required to create an admin account.", file=sys.stderr)
        sys.exit(1)

    normalized_email = email.strip().lower()

    if len(password) < 8:
        print("Error: Admin password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    # Connect to MongoDB
    client = MongoClient(settings.MONGODB_URI)
    db = client[settings.DATABASE_NAME]
    users_collection = db["users"]

    # Check for duplicate
    existing = users_collection.find_one({"email": normalized_email})
    if existing:
        if existing.get("role") == UserRole.ADMIN.value:
            print(f"User with email '{normalized_email}' already exists as ADMIN.")
            sys.exit(0)
        else:
            print(f"Error: Email '{normalized_email}' is already in use by a {existing.get('role')} account.", file=sys.stderr)
            sys.exit(1)

    # Hash password securely
    hashed_pwd = hash_password(password)

    admin_doc = UserDocument(
        fullName=name.strip(),
        email=normalized_email,
        phone=phone.strip() if phone else None,
        passwordHash=hashed_pwd,
        role=UserRole.ADMIN,
        emailVerified=True,
        accountStatus=AccountStatus.ACTIVE,
        authProviders=["LOCAL"],
        createdAt=utc_now(),
        updatedAt=utc_now(),
    )

    result = users_collection.insert_one(admin_doc.to_mongo_dict())
    print(f"Admin account created successfully! User ID: {result.inserted_id}, Email: {normalized_email}")


if __name__ == "__main__":
    create_admin()
