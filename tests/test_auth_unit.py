import sys
from unittest.mock import MagicMock, patch

# Mock problematic modules before importing app
sys.modules["matplotlib"] = MagicMock()
sys.modules["matplotlib.pyplot"] = MagicMock()

import unittest  # noqa: E402
import ui.web.auth as auth  # noqa: E402


class TestAuthUnit(unittest.TestCase):
    def test_tier_order(self):
        self.assertEqual(auth.TIER_ORDER, ["none", "explorer", "professional", "enterprise"])

    @patch('ui.web.auth._users_table')
    def test_get_user_subscription_with_user_type(self, mock_table):
        mock_table.get_item.return_value = {
            "Item": {
                "subscriptions": [{"product": "zorora", "tier": "professional"}],
                "usage": {"queries": 5},
                "user_type": "admin"
            }
        }
        tier, usage, user_type = auth._get_user_subscription("user123")
        self.assertEqual(tier, "professional")
        self.assertEqual(usage, {"queries": 5})
        self.assertEqual(user_type, "admin")

    @patch('ui.web.auth._users_table')
    def test_get_user_subscription_default_user_type(self, mock_table):
        mock_table.get_item.return_value = {
            "Item": {
                "subscriptions": [{"product": "zorora", "tier": "explorer"}],
                "usage": {}
            }
        }
        tier, usage, user_type = auth._get_user_subscription("user123")
        self.assertEqual(tier, "explorer")
        self.assertEqual(user_type, "regular")

    def test_require_tier_decorator_logic(self):
        # We can't easily test the decorator without a Flask app context,
        # but we can test the TIER_ORDER logic it uses.
        tier = "explorer"
        min_tier = "professional"
        
        tier_idx = auth.TIER_ORDER.index(tier)
        min_idx = auth.TIER_ORDER.index(min_tier)
        
        self.assertTrue(tier_idx < min_idx)
        
        tier = "enterprise"
        tier_idx = auth.TIER_ORDER.index(tier)
        self.assertTrue(tier_idx >= min_idx)

if __name__ == '__main__':
    unittest.main()
