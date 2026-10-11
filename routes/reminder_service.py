
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from pymongo.errors import DuplicateKeyError

from extensions import db, users
from routes.email_service import send_email


IST = ZoneInfo("Asia/Kolkata")

jobs_collection = db["jobs"]
applications_collection = db["applications"]
interviews_collection = db["interviews"]
sent_reminders = db["sent_reminders"]


# Migrate the previous index, which allowed only one reminder per event.
existing_indexes = sent_reminders.index_information()

if "unique_event_reminder" in existing_indexes:
    sent_reminders.drop_index("unique_event_reminder")


# Each event can now have multiple reminder slots.
sent_reminders.create_index(
    [
        ("user_id", 1),
        ("event_type", 1),
        ("event_id", 1),
        ("event_date", 1),
        ("slot", 1),
    ],
    unique=True,
    name="unique_event_reminder_slot",
)


def parse_event_date(value):
    """Parse a date stored as YYYY-MM-DD."""
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        return datetime.strptime(
            value.strip()[:10], "%Y-%m-%d"
        ).date()
    except ValueError:
        return None


def get_event_details(event_type, document):
    """Return the date, title and description for an event."""

    if event_type == "deadline":
        event_date = parse_event_date(document.get("deadline"))
        title = "Job application deadline"
        description = (
            f"{document.get('jobRole', 'Job')} at "
            f"{document.get('companyName', 'Company')}"
        )

    elif event_type == "assessment":
        event_date = parse_event_date(
            document.get("assessmentDate")
        )
        title = "Upcoming assessment"
        description = (
            f"{document.get('jobRole', 'Job')} at "
            f"{document.get('companyName', 'Company')}"
        )

    elif event_type == "interview":
        event_date = parse_event_date(
            document.get("scheduledDate")
        )
        title = "Upcoming interview"
        description = (
            f"{document.get('roundName', 'Interview')} for "
            f"{document.get('jobRole', 'Job')} at "
            f"{document.get('companyName', 'Company')}"
        )

    else:
        return None, None, None

    return event_date, title, description


def get_reminder_slots(event_type):
    """Return the reminder intervals applicable to each event."""

    if event_type == "deadline":
        return {
            "7_days": (timedelta(days=7), "in 7 days"),
            "3_days": (timedelta(days=3), "in 3 days"),
            "24_hours": (timedelta(days=1), "tomorrow"),
        }

    if event_type in ("assessment", "interview"):
        return {
            "24_hours": (timedelta(days=1), "tomorrow"),
        }

    return {}


def send_event_reminder(user, event_type, document, today):
    """Send each applicable reminder once on its scheduled date."""

    event_date, title, description = get_event_details(
        event_type, document
    )

    if event_date is None or event_date <= today:
        return

    user_id = str(document.get("user_id", ""))
    event_id = str(document["_id"])

    for slot, (offset, timing_text) in get_reminder_slots(
        event_type
    ).items():

        # Send on the calendar date that matches this reminder interval.
        if event_date != today + offset:
            continue

        reminder_record = {
            "user_id": user_id,
            "event_type": event_type,
            "event_id": event_id,
            "event_date": event_date.isoformat(),
            "slot": slot,
        }

        # Claim this particular slot to prevent duplicate emails.
        try:
            sent_reminders.insert_one({
                **reminder_record,
                "status": "sending",
                "created_at": datetime.now(IST),
            })
        except DuplicateKeyError:
            # This reminder slot has already been claimed.
            continue

        try:
            event_time = ""

            if event_type == "interview":
                scheduled_time = document.get(
                    "scheduledTime", ""
                )
                if scheduled_time:
                    event_time = f"\nTime: {scheduled_time}"

            message = (
                f"Hello {user.get('username', 'there')},\n\n"
                f"This is a reminder for an event {timing_text}.\n\n"
                f"{title}\n"
                f"{description}\n"
                f"Date: {event_date.strftime('%d %B %Y')}"
                f"{event_time}\n\n"
                "Please open your Placement Tracker for more details."
            )

            send_email(
                user["email"],
                f"Reminder: {title} {timing_text}",
                message,
            )

            sent_reminders.update_one(
                reminder_record,
                {"$set": {"status": "sent"}},
            )

            print(
                f"Reminder sent: {event_type} - "
                f"{slot} - {event_id}"
            )

        except Exception as error:
            # Remove failed claims so a later check can retry.
            sent_reminders.delete_one(reminder_record)

            print(
                f"Reminder failed for {event_type} "
                f"{event_id}, slot {slot}: {error}"
            )


def check_reminders():
    """Check all users' upcoming deadlines, assessments and interviews."""

    today = datetime.now(IST).date()
    print(f"Checking reminders for {today.isoformat()}")

    for user in users.find({"email_verified": True}):
        user_id = str(user["_id"])

        notifications = user.get("notifications") or {}
        reminders = user.get("reminders") or {}

        if notifications.get("email", True) is not True:
            continue

        event_sources = [
            (
                "deadline",
                "deadlines",
                jobs_collection,
                {"deadline": {"$nin": ["", None]}},
            ),
            (
                "assessment",
                "assessments",
                applications_collection,
                {"assessmentDate": {"$nin": ["", None]}},
            ),
            (
                "interview",
                "interviews",
                interviews_collection,
                {
                    "scheduledDate": {"$nin": ["", None]},
                    "status": "Scheduled",
                },
            ),
        ]

        for event_type, preference, collection, date_filter in event_sources:
            if reminders.get(preference, True) is not True:
                continue

            query = {
            "user_id": user_id,
            **date_filter
            }

            # Extra safeguard: don't remind about a saved job
            # if an application already exists for that source job.
            if event_type == "deadline":
                applied_job_ids = db["applications"].distinct(
                    "source_job_id",
                    {"user_id": user_id}
                )
                query["_id"] = {"$nin": applied_job_ids}

            for document in collection.find(query):
                try:
                    send_event_reminder(
                        user, event_type, document, today
                    )
                except Exception as error:
                    print(
                        f"Error processing {event_type} "
                        f"{document.get('_id')}: {error}"
                    )

    print("Reminder check completed.")
