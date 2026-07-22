import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.deadline import DeadlineEntry, DeadlineStatus
from app.services.email import EmailService

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def check_and_send_reminders() -> None:
    """
    Background job execution.
    Queries the database for upcoming deadlines that require notifications,
    sends emails to their owners, and updates the reminder_sent_at field.
    
    Robustness / Concurrency / Crash Recovery:
    1. Generates a unique UUID claim token per execution.
    2. Claims matching rows atomically by setting claim_token = run_claim_token.
    3. Handles crash/stall recovery using a lease/timeout mechanism: reclaims rows
       if the lease is expired (updated_at is older than 15 minutes and reminder_sent_at is NULL).
    4. Selects only the claimed rows to process.
    5. Clears claim_token and writes reminder_sent_at on success.
    6. Clears claim_token on failure so it can be retried immediately.
    """
    db: Session = SessionLocal()
    try:
        # Use timezone-aware datetimes throughout the application logic
        now = datetime.now(timezone.utc)
        threshold_delta = timedelta(hours=settings.reminder_threshold_hours)
        max_deadline = now + threshold_delta

        # Convert to naive UTC datetimes for SQLite database compatibility.
        # SQLite stores datetimes without timezone offset strings by default,
        # so keeping offsets in query parameters causes string comparison mismatches.
        now_naive = now.replace(tzinfo=None)
        max_deadline_naive = max_deadline.replace(tzinfo=None)

        # Lease timeout check (15 minutes). If a worker crashed or stalled after claiming,
        # the lease has expired, allowing a new run to claim and retry.
        lease_duration = timedelta(minutes=15)
        lease_cutoff_naive = now_naive - lease_duration

        import uuid
        run_claim_token = uuid.uuid4().hex

        # Claim matching rows atomically.
        # We claim rows that:
        # - Are UPCOMING and not deleted.
        # - Have not received a reminder yet (reminder_sent_at is NULL).
        # - Are within the deadline window.
        # - AND either unclaimed (claim_token IS NULL) OR have an expired lease (updated_at <= lease_cutoff_naive).
        updated_count = (
            db.query(DeadlineEntry)
            .filter(
                DeadlineEntry.status == DeadlineStatus.UPCOMING,
                DeadlineEntry.is_deleted.is_(False),
                DeadlineEntry.reminder_sent_at.is_(None),
                DeadlineEntry.deadline <= max_deadline_naive,
                # Avoid sending reminders for opportunities that have already passed
                DeadlineEntry.deadline >= now_naive,
                (
                    (DeadlineEntry.claim_token.is_(None)) |
                    (DeadlineEntry.updated_at <= lease_cutoff_naive)
                )
            )
            .update(
                {
                    DeadlineEntry.claim_token: run_claim_token,
                    # Explicitly update updated_at to refresh the claim lease time
                    DeadlineEntry.updated_at: now_naive,
                },
                synchronize_session=False
            )
        )
        db.commit()

        if updated_count == 0:
            logger.debug("No pending reminders found.")
            return

        # Fetch only the entries successfully claimed by this run
        entries = (
            db.query(DeadlineEntry)
            .filter(
                DeadlineEntry.claim_token == run_claim_token,
                DeadlineEntry.is_deleted.is_(False),
            )
            .all()
        )

        logger.info("Claimed %d pending reminders to send.", len(entries))

        for entry in entries:
            try:
                user = entry.owner
                if not user or not user.email:
                    logger.warning("DeadlineEntry %d has no owner or owner email.", entry.id)
                    continue

                # Ensure deadline datetime is timezone-aware
                deadline_dt = entry.deadline
                if deadline_dt.tzinfo is None:
                    deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)

                deadline_str = deadline_dt.astimezone(timezone.utc).strftime("%d %b %Y %H:%M UTC")

                logger.info("Sending reminder email to %s for company %s", user.email, entry.company_name)
                EmailService.send_deadline_reminder(
                    to_email=user.email,
                    company_name=entry.company_name,
                    role=entry.role,
                    category=entry.category.value,
                    deadline_str=deadline_str,
                    registration_link=entry.registration_link,
                )

                # Set success status: save reminder send time, clear claim, and refresh updated_at
                now_done = datetime.now(timezone.utc).replace(tzinfo=None)
                entry.reminder_sent_at = now_done
                entry.claim_token = None
                entry.updated_at = now_done
                db.commit()

            except Exception as entry_exc:
                logger.error("Failed to send reminder for entry ID %d: %s", entry.id, entry_exc)
                # Reset claim token and update updated_at on failure so it can be retried immediately
                entry.claim_token = None
                entry.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                db.commit()

    except Exception as exc:
        logger.error("Exception in check_and_send_reminders background task: %s", exc)
    finally:
        db.close()


def start_scheduler() -> None:
    """Initialize and start the APScheduler background thread."""
    if not scheduler.running:
        interval_mins = settings.reminder_interval_minutes
        logger.info("Starting background reminder scheduler (interval: %d minutes).", interval_mins)
        scheduler.add_job(
            check_and_send_reminders,
            "interval",
            minutes=interval_mins,
            id="deadline_reminders_job",
            replace_existing=True,
        )
        scheduler.start()


def shutdown_scheduler() -> None:
    """Shut down the background scheduler thread."""
    if scheduler.running:
        logger.info("Stopping background reminder scheduler.")
        scheduler.shutdown()
