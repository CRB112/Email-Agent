import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from app.microsoftGraph.email import getEmails, next_checkpoint


class FakeInbox:
    """Model Graph filtering, ordering and server-side pages without a mailbox."""

    def __init__(self, emails):
        self.emails = emails
        self.me = self
        self.mail_folders = self
        self.messages = self
        self.offset = 0

    def by_mail_folder_id(self, _folder):
        self.offset = 0
        return self

    def with_url(self, url):
        self.offset = int(url)
        return self

    async def get(self, request_configuration):
        query = request_configuration.query_parameters
        emails = self.emails[:]
        for condition in (query.filter or '').split(' and '):
            if not condition:
                continue
            _, operator, value = condition.split()
            boundary = datetime.fromisoformat(value.replace('Z', '+00:00'))
            emails = [email for email in emails if {
                'ge': email.received_date_time >= boundary,
                'gt': email.received_date_time > boundary,
                'le': email.received_date_time <= boundary,
            }[operator]]
        emails.sort(key=lambda email: email.received_date_time,
                    reverse=query.orderby == ['receivedDateTime desc'])
        end = self.offset + min(query.top, 7)
        return SimpleNamespace(value=emails[self.offset:end],
                               odata_next_link=str(end) if end < len(emails) else None)


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 9, 14, tzinfo=timezone.utc)
        self.until = (self.start + timedelta(days=1)).isoformat().replace('+00:00', 'Z')

    def drain(self, emails, limit):
        inbox = FakeInbox(emails)
        at, ids = None, []
        processed = []
        for _ in range(len(emails) + 2):
            batch = asyncio.run(getEmails(inbox, at, limit, oldest_first=True,
                                          received_before=self.until, checkpoint_ids=ids))
            at, ids = next_checkpoint(batch, at, ids, self.until)
            if not batch:
                break
            processed.extend(email.id for email in batch)
        self.assertEqual(len(processed), len(emails))
        self.assertEqual(set(processed), {email.id for email in emails})
        self.assertEqual(at, self.until)

    def test_capped_backlog_is_drained_without_skips(self):
        self.drain([SimpleNamespace(id=str(i), received_date_time=self.start + timedelta(seconds=i))
                    for i in range(150)], 100)

    def test_timestamp_ties_across_batches_and_pages(self):
        self.drain([SimpleNamespace(id=str(i), received_date_time=self.start)
                    for i in range(35)], 10)

    def test_messages_after_run_start_are_deferred(self):
        inbox = FakeInbox([SimpleNamespace(id='later', received_date_time=self.start + timedelta(days=2))])
        self.assertEqual(asyncio.run(getEmails(inbox, oldest_first=True,
                                              received_before=self.until)), [])



if __name__ == '__main__':
    unittest.main()
