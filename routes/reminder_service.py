from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from pymongo.errors import DuplicateKeyError

from extensions import db, users
from routes.email_service import send_email


IST = ZoneInfo("Asia/Kolkata")
REMINDER_WINDOW = timedelta(minutes=6)

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
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_event_time(value):
    """Parse an optional HH:MM time. Return None when it is missing/invalid."""
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        return datetime.strptime(value.strip()[:5], "%H:%M").time()
    except ValueError:
        return None


def get_event_details(event_type, document):
    """Return event date, title, description, optional time and time-source flag."""

    if event_type == "deadline":
        event_date = parse_event_date(document.get("deadline"))
        title = "Job application deadline"
        description = (
            f"{document.get('jobRole', 'Job')} at "
            f"{document.get('companyName', 'Company')}"
        )
        event_time = None
        time_was_specified = False

    elif event_type == "assessment":
        event_date = parse_event_date(document.get("assessmentDate"))
        title = "Upcoming assessment"
        description = (
            f"{document.get('jobRole', 'Job')} at "
            f"{document.get('companyName', 'Company')}"
        )
        # The current frontend only collects assessmentDate. If assessmentTime
        # is added later, this service will use it automatically.
        event_time = parse_event_time(document.get("assessmentTime"))
        time_was_specified = event_time is not None

    elif event_type == "interview":
        event_date = parse_event_date(document.get("scheduledDate"))
        title = "Upcoming interview"
        description = (
            f"{document.get('roundName', 'Interview')} for "
            f"{document.get('jobRole', 'Job')} at "
            f"{document.get('companyName', 'Company')}"
        )
        event_time = parse_event_time(document.get("scheduledTime"))
        time_was_specified = event_time is not None

    else:
        return None, None, None, None, False

    return event_date, title, description, event_time, time_was_specified


def get_reminder_slots(event_type):
    """Return reminder intervals for each event type."""
    if event_type == "deadline":
        return {
            "7_days": (timedelta(days=7), "in 7 days"),
            "3_days": (timedelta(days=3), "in 3 days"),
            "24_hours": (timedelta(days=1), "in 24 hours"),
        }

    if event_type in ("assessment", "interview"):
        return {
            "24_hours": (timedelta(hours=24), "in about 24 hours"),
            "12_hours": (timedelta(hours=12), "in about 12 hours"),
            "6_hours": (timedelta(hours=6), "in about 6 hours"),
            "3_hours": (timedelta(hours=3), "in about 3 hours"),
            "1_hour": (timedelta(hours=1), "in about 1 hour"),
        }

    return {}


def claim_reminder(reminder_record):
    """Claim a reminder slot atomically so duplicate emails are avoided."""
    try:
        sent_reminders.insert_one({
            **reminder_record,
            "status": "sending",
            "created_at": datetime.now(IST),
        })
        return True
    except DuplicateKeyError:
        return False


def send_event_reminder(user, event_type, document, now):
    """Send due reminders once; timed events use a short window around each slot."""
    (
        event_date,
        title,
        description,
        event_time,
        time_was_specified,
    ) = get_event_details(event_type, document)

    if event_date is None:
        return

    user_id = str(document.get("user_id", ""))
    event_id = str(document["_id"])
    event_date_key = event_date.isoformat()

    if event_type == "deadline":
        # Keep job-deadline reminders date-based as before.
        if event_date <= now.date():
            return

        for slot, (offset, timing_text) in get_reminder_slots(event_type).items():
            if event_date != now.date() + offset:
                continue

            reminder_record = {
                "user_id": user_id,
                "event_type": event_type,
                "event_id": event_id,
                "event_date": event_date_key,
                "slot": slot,
            }

            if not claim_reminder(reminder_record):
                continue

            try:
                message = (
                    f"Hello {user.get('username', 'there')},\n\n"
                    f"This is a reminder for an event {timing_text}.\n\n"
                    f"{title}\n{description}\n"
                    f"Deadline: {event_date.strftime('%d %B %Y')}\n\n"
                    "Please open your Placement Tracker for more details."
                )

                send_email(
                    user["email"],
                    f"Reminder: {title} {timing_text}",
                    message,
                )
                sent_reminders.update_one(
                    reminder_record, {"$set": {"status": "sent"}}
                )
                print(f"Reminder sent: {event_type} - {slot} - {event_id}")

            except Exception as error:
                sent_reminders.delete_one(reminder_record)
                print(
                    f"Reminder failed for {event_type} {event_id}, "
                    f"slot {slot}: {error}"
                )
        return

    # Assessments/interviews default to 09:00 IST if no valid time is saved.
    # This is only a reminder-calculation fallback, not a claim that the
    # event organizer confirmed a 9:00 AM start.
    effective_time = event_time or time(9, 0)
    event_datetime = datetime.combine(
        event_date, effective_time, tzinfo=IST
    )

    # Do not send reminders for events that have already started.
    if event_datetime <= now:
        return

    for slot, (offset, timing_text) in get_reminder_slots(event_type).items():
        reminder_due_at = event_datetime - offset

        # cron-job.org runs every 5 minutes. The small grace window tolerates
        # minor scheduler delays; the unique MongoDB index prevents duplicates.
        if not (reminder_due_at <= now < reminder_due_at + REMINDER_WINDOW):
            continue

        reminder_record = {
            "user_id": user_id,
            "event_type": event_type,
            "event_id": event_id,
            "event_date": event_date_key,
            "slot": slot,
        }

        if not claim_reminder(reminder_record):
            continue

        try:
            time_text = (
                f"Event time: {event_time.strftime('%I:%M %p').lstrip('0')} IST"
                if time_was_specified
                else (
                    "Exact event time: Not specified. "
                    "For reminder timing only, we assumed 9:00 AM IST."
                )
            )

            message = (
                f"Hello {user.get('username', 'there')},\n\n"
                f"This is a reminder that your event is {timing_text}.\n\n"
                f"{title}\n"
                f"{description}\n"
                f"Date: {event_date.strftime('%d %B %Y')}\n"
                f"{time_text}\n\n"
                "Please check your Placement Tracker and any official "
                "communication from the company for the confirmed schedule."
            )

            send_email(
                user["email"],
                f"Reminder: {title} {timing_text}",
                message,
            )
            sent_reminders.update_one(
                reminder_record, {"$set": {"status": "sent"}}
            )
            print(f"Reminder sent: {event_type} - {slot} - {event_id}")

        except Exception as error:
            # Remove failed claims so the next eligible check can retry.
            sent_reminders.delete_one(reminder_record)
            print(
                f"Reminder failed for {event_type} {event_id}, "
                f"slot {slot}: {error}"
            )


def check_reminders():
    """Check users' upcoming deadlines, assessments and scheduled interviews."""
    now = datetime.now(IST)
    today = now.date()
    print(f"Checking reminders for {now.isoformat()}")

    for user in users.find({}):
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

            query = {"user_id": user_id, **date_filter}

            # Do not remind about a saved job if an application already exists.
            if event_type == "deadline":
                applied_job_ids = db["applications"].distinct(
                    "source_job_id", {"user_id": user_id}
                )
                query["_id"] = {"$nin": applied_job_ids}

            for document in collection.find(query):
                try:
                    send_event_reminder(user, event_type, document, now)
                except Exception as error:
                    print(
                        f"Error processing {event_type} "
                        f"{document.get('_id')}: {error}"
                    )

    print(f"Reminder check completed for {today.isoformat()}")
