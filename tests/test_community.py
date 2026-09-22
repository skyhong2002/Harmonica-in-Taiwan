import json
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import community

TOKEN = 'apify_api_' + 'A' * 40
QUOTA = {'limitUsd': 5, 'usedUsd': 1, 'remainingUsd': 4, 'cycleStart': '2026-09-01T00:00:00Z',
         'cycleEnd': '2026-10-01T00:00:00Z', 'checkedAt': time.time(), 'accountId': 'private-account-identity'}


class CommunityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'HARMONICA_COMMUNITY_STATE': self.temp.name})
        self.env.start()
        self.verify = patch.object(community, 'verify_token', return_value=QUOTA.copy())
        self.verify_mock = self.verify.start()

    def tearDown(self):
        self.verify.stop()
        self.env.stop()
        self.temp.cleanup()

    def register(self, owner='owner', budget=1):
        return community.register(owner, {'token': TOKEN, 'name': 'Public label', 'budgetUsd': budget, 'consent': True})

    def test_empty_public_read_does_not_create_storage(self):
        self.assertEqual(community.active_tokens(), [])
        self.assertEqual(community.public_status()['activeAccounts'], 0)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_encrypted_private_storage_public_allowlist(self):
        item = self.register()
        db = Path(self.temp.name) / 'community.sqlite3'
        self.assertNotIn(TOKEN.encode(), db.read_bytes())
        self.assertEqual(db.stat().st_mode & 0o777, 0o600)
        self.assertEqual((Path(self.temp.name) / 'encryption.key').stat().st_mode & 0o777, 0o600)
        public = json.dumps(community.public_status())
        self.assertNotIn(TOKEN, public)
        self.assertNotIn('private-account-identity', public)
        self.assertNotIn('owner', item)
        self.assertEqual(community.active_tokens()[0]['token'], TOKEN)
        self.assertEqual(community.active_tokens()[0]['verifiedQuota']['accountId'], QUOTA['accountId'])

    def test_consent_and_budget_fail_closed(self):
        for bad in (None, 0, -1, 101, float('nan'), float('inf'), True):
            with self.assertRaises(community.CommunityError):
                self.register(budget=bad)
        with self.assertRaises(community.CommunityError):
            community.register('owner', {'token': TOKEN, 'name': 'x', 'budgetUsd': 1})
        self.verify_mock.assert_not_called()

    def test_owner_withdrawal_clears_secret_and_preserves_reservation(self):
        item = self.register()
        self.assertTrue(community.reserve_budget(item['id'], 'run', 0.5))
        self.assertFalse(community.revoke('someone-else', item['id']))
        self.assertTrue(community.revoke('owner', item['id']))
        self.assertEqual(community.active_tokens(), [])
        self.assertFalse(community.reserve_budget(item['id'], 'later', 0.1))
        self.assertTrue(community.settle_budget('run', 0.5))
        own = community.owner_contributions('owner')[0]
        self.assertEqual(own['spentUsd'], 0.5)
        self.assertEqual(own['status'], 'revoked')
        with community.connect() as conn:
            self.assertEqual(conn.execute('SELECT ciphertext FROM contributions').fetchone()[0], '')

    def test_atomic_budget_reservations(self):
        item = self.register()
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda i: community.reserve_budget(item['id'], str(i), 0.25), range(20)))
        self.assertEqual(sum(results), 4)
        self.assertEqual(community.owner_contributions('owner')[0]['budgetRemainingUsd'], 0)
        success_id = str(results.index(True))
        self.assertFalse(community.reserve_budget(item['id'], success_id, 0.1))
        self.assertTrue(community.settle_budget(success_id, 0.2))
        self.assertFalse(community.settle_budget(success_id, 0.2))
        self.assertAlmostEqual(community.owner_contributions('owner')[0]['budgetRemainingUsd'], 0.05)

    def test_public_capacity_excludes_stale_and_deduplicates_accounts(self):
        now = time.time()
        fresh = {**QUOTA, 'checkedAt': now,
                 'cycleStart': datetime.fromtimestamp(now - 86400, timezone.utc).isoformat(),
                 'cycleEnd': datetime.fromtimestamp(now + 86400, timezone.utc).isoformat()}
        self.verify_mock.return_value = fresh
        first = self.register()
        community.register('other', {'token': 'apify_api_' + 'B' * 40, 'name': 'Second credential', 'budgetUsd': 1, 'consent': True})
        status = community.public_status()
        self.assertEqual(status['activeAccounts'], 1)
        self.assertEqual(status['remainingUsd'], 4)
        self.assertEqual(status['budgetRemainingUsd'], 2)
        community.mark_quota(first['id'], {**fresh, 'checkedAt': now - 3601})
        status = community.public_status()
        self.assertEqual(status['staleAccounts'], 1)
        self.assertEqual(status['budgetRemainingUsd'], 1)
        own = community.owner_contributions('owner')[0]
        self.assertEqual(own['quotaState'], 'stale')
        self.assertEqual(own['remainingUsd'], 4)

    def test_session_is_opaque_and_invalid_cookie_never_selects_owner(self):
        first, cookie = community.session(None, create=True)
        again, replacement = community.session(cookie)
        self.assertEqual(first['owner'], again['owner'])
        self.assertIsNone(replacement)
        self.assertEqual(community.session('invalid'), (None, None))
        with community.connect() as conn:
            self.assertNotEqual(conn.execute('SELECT hash FROM sessions').fetchone()[0], cookie)

    def test_submissions_remain_pending_and_owner_scoped(self):
        item = community.submit('owner', {'url': 'https://example.org/concert#fragment', 'note': 'Please review', 'countryCode': 'jp'})
        self.assertEqual(item['countryCode'], 'JP')
        self.assertEqual(item['status'], 'pending')
        self.assertEqual(community.owner_submissions('other'), [])
        self.assertEqual(len(community.owner_submissions('owner')), 1)
        with self.assertRaises(community.CommunityError):
            community.submit('owner', {'url': item['url']})
        with self.assertRaises(community.CommunityError):
            community.submit('owner', {'url': 'javascript:alert(1)'})


if __name__ == '__main__':
    unittest.main()
