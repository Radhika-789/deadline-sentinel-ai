import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.user import User, UserRole
from app.models.deadline import DeadlineEntry, DeadlineStatus, OpportunityCategory, SourceType
from app.services.scheduler import check_and_send_reminders

# Create an in-memory SQLite database configuration for isolated unit tests
test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


class TestSchedulerReminders(unittest.TestCase):
    def setUp(self):
        # Create schema tables
        Base.metadata.create_all(bind=test_engine)
        self.db = TestSessionLocal()

        # Seed a test user
        self.user = User(
            email="student@example.com",
            username="student_test",
            hashed_password="somepasswordhash",
            role=UserRole.USER,
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        
        # We need the user's ID
        self.user_id = self.user.id

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=test_engine)

    @patch("app.services.scheduler.SessionLocal")
    @patch("app.services.scheduler.EmailService.send_deadline_reminder")
    def test_reminder_sent_within_threshold(self, mock_send_email, mock_session_local):
        mock_session_local.return_value = self.db

        # Create upcoming deadline expiring in 12 hours (within 24h threshold)
        now = datetime.now(timezone.utc)
        deadline_time = now + timedelta(hours=12)

        entry = DeadlineEntry(
            company_name="Google",
            role="SWE Intern",
            deadline=deadline_time.replace(tzinfo=None), # SQLite naive UTC
            category=OpportunityCategory.INTERNSHIP,
            source_type=SourceType.TEXT,
            status=DeadlineStatus.UPCOMING,
            user_id=self.user_id,
            is_deleted=False,
            reminder_sent_at=None,
        )
        self.db.add(entry)
        self.db.commit()
        entry_id = entry.id

        # Execute check
        check_and_send_reminders()

        # Verify email was dispatched
        mock_send_email.assert_called_once()
        kwargs = mock_send_email.call_args[1]
        self.assertEqual(kwargs["to_email"], "student@example.com")
        self.assertEqual(kwargs["company_name"], "Google")
        self.assertEqual(kwargs["role"], "SWE Intern")
        self.assertEqual(kwargs["category"], "internship")

        # Verify database sent flag was populated by opening a fresh session
        verify_db = TestSessionLocal()
        try:
            db_entry = verify_db.query(DeadlineEntry).filter(DeadlineEntry.id == entry_id).first()
            self.assertIsNotNone(db_entry.reminder_sent_at)
            self.assertIsNone(db_entry.claim_token)
        finally:
            verify_db.close()

    @patch("app.services.scheduler.SessionLocal")
    @patch("app.services.scheduler.EmailService.send_deadline_reminder")
    def test_reminder_ignored_outside_threshold(self, mock_send_email, mock_session_local):
        mock_session_local.return_value = self.db

        # Create upcoming deadline expiring in 36 hours (outside 24h threshold)
        now = datetime.now(timezone.utc)
        deadline_time = now + timedelta(hours=36)

        entry = DeadlineEntry(
            company_name="Microsoft",
            role="Explorer Intern",
            deadline=deadline_time.replace(tzinfo=None),
            category=OpportunityCategory.INTERNSHIP,
            source_type=SourceType.TEXT,
            status=DeadlineStatus.UPCOMING,
            user_id=self.user_id,
            is_deleted=False,
            reminder_sent_at=None,
        )
        self.db.add(entry)
        self.db.commit()
        entry_id = entry.id

        # Execute check
        check_and_send_reminders()

        # Verify email was NOT dispatched
        mock_send_email.assert_not_called()

        # Verify database flag remains None
        verify_db = TestSessionLocal()
        try:
            db_entry = verify_db.query(DeadlineEntry).filter(DeadlineEntry.id == entry_id).first()
            self.assertIsNone(db_entry.reminder_sent_at)
        finally:
            verify_db.close()

    @patch("app.services.scheduler.SessionLocal")
    @patch("app.services.scheduler.EmailService.send_deadline_reminder")
    def test_reminder_ignored_if_already_sent(self, mock_send_email, mock_session_local):
        mock_session_local.return_value = self.db

        # Create upcoming deadline expiring in 12 hours, but reminder_sent_at is already set
        now = datetime.now(timezone.utc)
        deadline_time = now + timedelta(hours=12)

        entry = DeadlineEntry(
            company_name="Meta",
            role="PE Intern",
            deadline=deadline_time.replace(tzinfo=None),
            category=OpportunityCategory.INTERNSHIP,
            source_type=SourceType.TEXT,
            status=DeadlineStatus.UPCOMING,
            user_id=self.user_id,
            is_deleted=False,
            reminder_sent_at=now - timedelta(hours=1),
        )
        self.db.add(entry)
        self.db.commit()

        # Execute check
        check_and_send_reminders()

        # Verify email was NOT dispatched again
        mock_send_email.assert_not_called()

    @patch("app.services.scheduler.SessionLocal")
    @patch("app.services.scheduler.EmailService.send_deadline_reminder")
    def test_reminder_ignored_if_deleted_or_not_upcoming(self, mock_send_email, mock_session_local):
        mock_session_local.return_value = self.db

        # Create two opportunities: one deleted, one already applied
        now = datetime.now(timezone.utc)
        deadline_time = now + timedelta(hours=12)

        entry1 = DeadlineEntry(
            company_name="Apple",
            role="iOS Intern",
            deadline=deadline_time.replace(tzinfo=None),
            category=OpportunityCategory.INTERNSHIP,
            source_type=SourceType.TEXT,
            status=DeadlineStatus.UPCOMING,
            user_id=self.user_id,
            is_deleted=True, # Deleted
            reminder_sent_at=None,
        )
        entry2 = DeadlineEntry(
            company_name="Netflix",
            role="Backend Intern",
            deadline=deadline_time.replace(tzinfo=None),
            category=OpportunityCategory.INTERNSHIP,
            source_type=SourceType.TEXT,
            status=DeadlineStatus.APPLIED, # Not upcoming
            user_id=self.user_id,
            is_deleted=False,
            reminder_sent_at=None,
        )
        self.db.add_all([entry1, entry2])
        self.db.commit()

        # Execute check
        check_and_send_reminders()

        # Verify email was NOT dispatched
        mock_send_email.assert_not_called()

    @patch("app.services.scheduler.SessionLocal")
    @patch("app.services.scheduler.EmailService.send_deadline_reminder")
    def test_active_lease_is_ignored(self, mock_send_email, mock_session_local):
        mock_session_local.return_value = self.db

        # Create upcoming deadline within 12 hours, claimed 2 minutes ago (active lease)
        now = datetime.now(timezone.utc)
        deadline_time = now + timedelta(hours=12)

        entry = DeadlineEntry(
            company_name="Amazon",
            role="SDE Intern",
            deadline=deadline_time.replace(tzinfo=None),
            category=OpportunityCategory.INTERNSHIP,
            source_type=SourceType.TEXT,
            status=DeadlineStatus.UPCOMING,
            user_id=self.user_id,
            is_deleted=False,
            reminder_sent_at=None,
            claim_token="active_token_123",
            updated_at=(now - timedelta(minutes=2)).replace(tzinfo=None), # Active
        )
        self.db.add(entry)
        self.db.commit()
        entry_id = entry.id

        # Execute check
        check_and_send_reminders()

        # Verify email was NOT dispatched
        mock_send_email.assert_not_called()

        # Verify claim token and updated_at remain untouched
        verify_db = TestSessionLocal()
        try:
            db_entry = verify_db.query(DeadlineEntry).filter(DeadlineEntry.id == entry_id).first()
            self.assertEqual(db_entry.claim_token, "active_token_123")
            self.assertIsNone(db_entry.reminder_sent_at)
        finally:
            verify_db.close()

    @patch("app.services.scheduler.SessionLocal")
    @patch("app.services.scheduler.EmailService.send_deadline_reminder")
    def test_expired_lease_is_reclaimed_and_sent(self, mock_send_email, mock_session_local):
        mock_session_local.return_value = self.db

        # Create upcoming deadline within 12 hours, claimed 20 minutes ago (expired lease)
        now = datetime.now(timezone.utc)
        deadline_time = now + timedelta(hours=12)

        entry = DeadlineEntry(
            company_name="Tesla",
            role="Autopilot Intern",
            deadline=deadline_time.replace(tzinfo=None),
            category=OpportunityCategory.INTERNSHIP,
            source_type=SourceType.TEXT,
            status=DeadlineStatus.UPCOMING,
            user_id=self.user_id,
            is_deleted=False,
            reminder_sent_at=None,
            claim_token="expired_token_123",
            updated_at=(now - timedelta(minutes=20)).replace(tzinfo=None), # Expired (>15m)
        )
        self.db.add(entry)
        self.db.commit()
        entry_id = entry.id

        # Execute check
        check_and_send_reminders()

        # Verify email WAS dispatched (reclaimed!)
        mock_send_email.assert_called_once()

        # Verify database sent flag was populated and claim cleared
        verify_db = TestSessionLocal()
        try:
            db_entry = verify_db.query(DeadlineEntry).filter(DeadlineEntry.id == entry_id).first()
            self.assertIsNotNone(db_entry.reminder_sent_at)
            self.assertIsNone(db_entry.claim_token)
        finally:
            verify_db.close()
