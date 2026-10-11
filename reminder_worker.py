
from apscheduler.schedulers.blocking import BlockingScheduler

from routes.reminder_service import check_reminders


def main():
    scheduler = BlockingScheduler(
        timezone="Asia/Kolkata"
    )

    # Check reminders immediately when the worker starts.
    scheduler.add_job(
        func=check_reminders,
        trigger="date",
        id="initial_reminder_check",
    )

    # Continue checking every minute.
    scheduler.add_job(
        func=check_reminders,
        trigger="interval",
        minutes=1,
        id="reminder_checker",
        max_instances=1,
        coalesce=True,
    )

    print("Production reminder worker started!")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
