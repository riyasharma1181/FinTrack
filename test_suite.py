import unittest
import urllib.request
import urllib.parse
import json
import time

BASE_URL = "http://localhost:8000"

def make_request(method, endpoint, data=None, token=None, urlencoded=False):
    url = f"{BASE_URL}{endpoint}"
    headers = {}
    body = None

    if token:
        headers["Authorization"] = f"Bearer {token}"

    if data is not None:
        if urlencoded:
            body = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            return response.status, json.loads(res_body) if res_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"raw": err_body}
        return e.code, parsed


class TestFinTrackAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create unique test users
        cls.ts = int(time.time() * 1000)
        cls.user1_email = f"testuser1_{cls.ts}@example.com"
        cls.user2_email = f"testuser2_{cls.ts}@example.com"
        cls.password = "TestPass123!"

        # Register User 1
        st, res = make_request("POST", "/register", {
            "name": "Test User One",
            "email": cls.user1_email,
            "password": cls.password
        })
        assert st in (200, 201), f"User 1 registration failed: {res}"

        # Register User 2
        st, res = make_request("POST", "/register", {
            "name": "Test User Two",
            "email": cls.user2_email,
            "password": cls.password
        })
        assert st in (200, 201), f"User 2 registration failed: {res}"

        # Login User 1
        st, res = make_request("POST", "/login", {
            "username": cls.user1_email,
            "password": cls.password
        }, urlencoded=True)
        assert st == 200, f"User 1 login failed: {res}"
        cls.token1 = res["access_token"]

        # Login User 2
        st, res = make_request("POST", "/login", {
            "username": cls.user2_email,
            "password": cls.password
        }, urlencoded=True)
        assert st == 200, f"User 2 login failed: {res}"
        cls.token2 = res["access_token"]

        # Register and promote Developer User
        cls.dev_email = f"testdev_{cls.ts}@example.com"
        st, res = make_request("POST", "/register", {
            "name": "Test Developer",
            "email": cls.dev_email,
            "password": cls.password
        })
        assert st in (200, 201), f"Developer registration failed: {res}"

        # Update role to DEVELOPER in database
        import sys
        sys.path.insert(0, ".")
        from database import SessionLocal
        from models import User
        db = SessionLocal()
        dev_user = db.query(User).filter(User.email == cls.dev_email).first()
        if dev_user:
            dev_user.role = "DEVELOPER"
            db.commit()
        db.close()

        # Login Developer User
        st, res = make_request("POST", "/login", {
            "username": cls.dev_email,
            "password": cls.password
        }, urlencoded=True)
        assert st == 200, f"Developer login failed: {res}"
        cls.token_dev = res["access_token"]

    def test_01_user_profile(self):
        st, res = make_request("GET", "/me", token=self.token1)
        self.assertEqual(st, 200)
        self.assertEqual(res["email"], self.user1_email)

    def test_02_card_lifecycle_and_user_isolation(self):
        # User 1 creates a card
        st, card = make_request("POST", "/cards", {
            "card_name": "Axis Magnus",
            "issuer": "Axis Bank",
            "card_type": "CREDIT",
            "network": "Mastercard",
            "last_four_digits": "4321",
            "expiry_month": 11,
            "expiry_year": 2028
        }, token=self.token1)
        self.assertEqual(st, 200)
        card_id = card["card_id"]

        # User 1 adds benefit
        st, benefit = make_request("POST", f"/cards/{card_id}/benefits", {
            "category": "Dining",
            "benefit_type": "Cashback",
            "benefit_value": 5.0,
            "conditions": "Min spend ₹500"
        }, token=self.token1)
        self.assertEqual(st, 200)

        # User 2 tries to access User 1's card benefits -> Must return 404
        st, res = make_request("GET", f"/cards/{card_id}/benefits", token=self.token2)
        self.assertEqual(st, 404)

        # User 2 tries to add benefit to User 1's card -> Must return 404
        st, res = make_request("POST", f"/cards/{card_id}/benefits", {
            "category": "Travel",
            "benefit_type": "Points",
            "benefit_value": 10.0
        }, token=self.token2)
        self.assertEqual(st, 404)

        # User 1 creates an expense first
        st, exp = make_request("POST", "/expense", {
            "amount": 500.0,
            "category": "Dining",
            "merchant": "Swiggy",
            "expense_date": "2026-10-02"
        }, token=self.token1)
        self.assertEqual(st, 200)

        # User 1 records card usage linked to expense
        st, usage = make_request("POST", f"/cards/{card_id}/usage", {
            "expense_id": exp["expense_id"],
            "benefit_received": 25.0
        }, token=self.token1)
        self.assertEqual(st, 200)
        self.assertEqual(usage["card_id"], card_id)

        # User 1 fetches card usages
        st, usages = make_request("GET", f"/cards/{card_id}/usage", token=self.token1)
        self.assertEqual(st, 200)
        self.assertTrue(len(usages) >= 1)

        # Recommendations for User 1
        st, recs = make_request("GET", "/cards-recommendations", token=self.token1)
        self.assertEqual(st, 200)
        self.assertTrue(recs["has_cards"])

    def test_03_financial_reports_summary(self):
        # Add income and expense for User 1
        st, _ = make_request("POST", "/income", {
            "amount": 50000.0,
            "source": "Salary",
            "income_date": "2026-10-01",
            "source_type": "MANUAL"
        }, token=self.token1)
        self.assertEqual(st, 200)

        st, _ = make_request("POST", "/expense", {
            "amount": 1200.0,
            "category": "Dining",
            "merchant": "Barbeque Nation",
            "expense_date": "2026-10-05"
        }, token=self.token1)
        self.assertEqual(st, 200)

        # Fetch Financial Summary
        st, report = make_request("GET", "/reports/financial-summary", token=self.token1)
        self.assertEqual(st, 200)
        self.assertIn("summary", report)
        self.assertGreaterEqual(report["summary"]["total_income"], 50000.0)
        self.assertGreaterEqual(report["summary"]["total_direct_expenses"], 1200.0)
        self.assertIn("category_breakdown", report)

    def test_04_ai_assistant_query(self):
        st, res = make_request("POST", "/ai-assistant/query", {
            "query": "Where did I spend the most money?"
        }, token=self.token1)
        self.assertEqual(st, 200)
        self.assertIn("response", res)
        self.assertIn("Dining", res["response"])

        st, res = make_request("POST", "/ai-assistant/query", {
            "query": "Which card gives the best rewards?"
        }, token=self.token1)
        self.assertEqual(st, 200)
        self.assertIn("Axis Magnus", res["response"])

    def test_05_bank_sms_parse_and_confirm(self):
        sms = "Rs. 450.00 debited from A/C **1234 on 08-10-2026 at SWIGGY via UPI. Avl Bal: Rs 14,200."
        st, parsed = make_request("POST", "/sms/parse", {
            "sms_text": sms
        }, token=self.token1)
        self.assertEqual(st, 200)
        self.assertEqual(parsed["status"], "success")
        self.assertEqual(parsed["parsed_data"]["amount"], 450.0)
        self.assertEqual(parsed["parsed_data"]["transaction_type"], "EXPENSE")
        self.assertIn("Food", parsed["parsed_data"]["category"])

        # Confirm the transaction
        st, confirmed = make_request("POST", "/sms/confirm", {
            "transaction_type": parsed["parsed_data"]["transaction_type"],
            "amount": parsed["parsed_data"]["amount"],
            "category_or_source": parsed["parsed_data"]["category"],
            "transaction_date": parsed["parsed_data"]["transaction_date"],
            "merchant": parsed["parsed_data"]["merchant"],
            "payment_method": parsed["parsed_data"]["payment_method"]
        }, token=self.token1)
        self.assertEqual(st, 200)
        self.assertEqual(confirmed["type"], "EXPENSE")

        # Parsing identical SMS again should detect duplicate!
        st, re_parsed = make_request("POST", "/sms/parse", {
            "sms_text": sms
        }, token=self.token1)
        self.assertEqual(st, 200)
        self.assertTrue(re_parsed["is_duplicate"])

        # Test OTP message rejection (HTTP 422)
        otp_sms = "Your OTP for transaction of Rs. 999 is 482910. Do not share this OTP with anyone."
        st_otp, res_otp = make_request("POST", "/sms/parse", {
            "sms_text": otp_sms
        }, token=self.token1)
        self.assertEqual(st_otp, 422)

        # Test Promotional spam message rejection (HTTP 422)
        promo_sms = "Get Rs. 500 flat off on orders above Rs. 1999! Use code FESTIVE500. Offer valid till Sunday."
        st_promo, res_promo = make_request("POST", "/sms/parse", {
            "sms_text": promo_sms
        }, token=self.token1)
        self.assertEqual(st_promo, 422)

        # Test Ambiguous message rejection without debit/credit direction (HTTP 422)
        ambig_sms = "Your account balance inquiry shows Rs. 10,500 available."
        st_ambig, res_ambig = make_request("POST", "/sms/parse", {
            "sms_text": ambig_sms
        }, token=self.token1)
        self.assertEqual(st_ambig, 422)

    def test_06_budget_conflict_and_alert_calculation(self):
        # 1. Create a budget
        st, b1 = make_request("POST", "/budget", {
            "category": "Groceries",
            "limit_amount": 1000.0,
            "period": "MONTHLY",
            "start_date": "2026-10-01",
            "end_date": "2026-10-31"
        }, token=self.token1)
        self.assertEqual(st, 200)

        # 2. Duplicate budget check -> must reject with HTTP 409
        st, b_dup = make_request("POST", "/budget", {
            "category": "Groceries",
            "limit_amount": 1000.0,
            "period": "MONTHLY",
            "start_date": "2026-10-01",
            "end_date": "2026-10-31"
        }, token=self.token1)
        self.assertEqual(st, 409)

        # 3. Add expense that exceeds budget limit
        st, _ = make_request("POST", "/expense", {
            "amount": 1200.0,
            "category": "Groceries",
            "merchant": "Supermarket",
            "expense_date": "2026-10-07"
        }, token=self.token1)
        self.assertEqual(st, 200)

        # 4. Check budget summary -> remaining budget should be negative
        st, summary = make_request("GET", "/budget-summary", token=self.token1)
        self.assertEqual(st, 200)
        grocery_budget = next((b for b in summary if b["category"] == "Groceries"), None)
        self.assertIsNotNone(grocery_budget)
        self.assertLess(grocery_budget["remaining"], 0)

    def test_07_income_allocation_and_split_settlement(self):
        # 1. Create income allocation
        st, alloc = make_request("POST", "/allocation", {
            "title": "Emergency Fund",
            "planned_amount": 5000.0,
            "category": "Savings",
            "due_date": "2026-12-31"
        }, token=self.token1)
        self.assertEqual(st, 200)

        # 2. Create Split Bill with User 2
        st, bill = make_request("POST", "/split-bills", {
            "title": "Team Dinner",
            "total_amount": 2000.0,
            "bill_date": "2026-10-09",
            "description": "Weekend celebration",
            "participants": [
                {"name": "Self", "share_amount": 1000.0},
                {"name": "Partner", "share_amount": 1000.0}
            ]
        }, token=self.token1)
        self.assertEqual(st, 200)
        bill_id = bill["split_bill_id"]

        # 3. Retrieve split bills
        st, bills = make_request("GET", "/split-bills", token=self.token1)
        self.assertEqual(st, 200)
        my_bill = next((b for b in bills if b["split_bill_id"] == bill_id), None)
        self.assertIsNotNone(my_bill)
        partner_p = next(p for p in my_bill["participants"] if p["name"] == "Partner")

        # 4. Settle payment for participant
        st, settlement = make_request("POST", f"/split-bills/{bill_id}/settlements", {
            "participant_id": partner_p["participant_id"],
            "amount": 1000.0,
            "settlement_date": "2026-10-10"
        }, token=self.token1)
        self.assertEqual(st, 200)
        self.assertEqual(settlement["participant_status"], "PAID")

    def test_08_notifications_lifecycle(self):
        # 1. Fetch unread notifications for User 1 (triggered by earlier settlements, budget alerts, SMS imports)
        st, notifs = make_request("GET", "/notifications", token=self.token1)
        self.assertEqual(st, 200)
        self.assertIsInstance(notifs, list)
        self.assertGreater(len(notifs), 0)

        first_notif = notifs[0]
        self.assertIn("notification_id", first_notif)
        self.assertIn("title", first_notif)

        # 2. Check unread count
        st, count_data = make_request("GET", "/notifications/unread-count", token=self.token1)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(count_data["unread_count"], 1)

        # 3. User 2 cannot access or mark User 1's notification -> 404
        st, res = make_request(
            "PATCH",
            f"/notifications/{first_notif['notification_id']}/read",
            token=self.token2
        )
        self.assertEqual(st, 404)

        # 4. User 1 marks their notification as read
        st, read_notif = make_request(
            "PATCH",
            f"/notifications/{first_notif['notification_id']}/read",
            token=self.token1
        )
        self.assertEqual(st, 200)
        self.assertEqual(read_notif["is_read"], 1)

        # 5. Mark all as read
        st, res = make_request("POST", "/notifications/mark-all-read", token=self.token1)
        self.assertEqual(st, 200)

        # Unread count should now be 0
        st, count_data = make_request("GET", "/notifications/unread-count", token=self.token1)
        self.assertEqual(st, 200)
        self.assertEqual(count_data["unread_count"], 0)

    def test_09_income_expense_validation_and_deletion(self):
        # 1. Reject non-positive income amount
        st, res = make_request("POST", "/income", {
            "amount": -500.0,
            "source": "Bonus",
            "income_date": "2026-10-01"
        }, token=self.token1)
        self.assertEqual(st, 400)

        # 2. Reject non-positive expense amount
        st, res = make_request("POST", "/expense", {
            "amount": 0.0,
            "category": "Shopping",
            "expense_date": "2026-10-02"
        }, token=self.token1)
        self.assertEqual(st, 400)

        # 3. Create valid income and delete it
        st, inc = make_request("POST", "/income", {
            "amount": 1500.0,
            "source": "Freelance",
            "income_date": "2026-10-03"
        }, token=self.token1)
        self.assertEqual(st, 200)
        inc_id = inc["income_id"]

        # User 2 cannot delete User 1's income -> 404
        st, res = make_request("DELETE", f"/income/{inc_id}", token=self.token2)
        self.assertEqual(st, 404)

        # User 1 successfully deletes income
        st, res = make_request("DELETE", f"/income/{inc_id}", token=self.token1)
        self.assertEqual(st, 200)

        # Deleting already deleted income -> 404
        st, res = make_request("DELETE", f"/income/{inc_id}", token=self.token1)
        self.assertEqual(st, 404)

        # 4. Create valid expense and delete it
        st, exp = make_request("POST", "/expense", {
            "amount": 350.0,
            "category": "Books",
            "expense_date": "2026-10-04"
        }, token=self.token1)
        self.assertEqual(st, 200)
        exp_id = exp["expense_id"]

        # User 2 cannot delete User 1's expense -> 404
        st, res = make_request("DELETE", f"/expenses/{exp_id}", token=self.token2)
        self.assertEqual(st, 404)

        # User 1 successfully deletes expense
        st, res = make_request("DELETE", f"/expenses/{exp_id}", token=self.token1)
        self.assertEqual(st, 200)

    def test_10_developer_role_enforcement(self):
        # 1. Ordinary user (USER role) must receive 403 Forbidden on developer endpoints
        st, res = make_request("GET", "/developer/stats", token=self.token1)
        self.assertEqual(st, 403)

        st, res = make_request("GET", "/developer/audit-logs", token=self.token1)
        self.assertEqual(st, 403)

        st, res = make_request("GET", "/developer-test", token=self.token1)
        self.assertEqual(st, 403)

        # 2. Developer user (DEVELOPER role) receives 200 OK
        st, stats = make_request("GET", "/developer/stats", token=self.token_dev)
        self.assertEqual(st, 200)
        self.assertIn("total_users", stats)
        self.assertIn("total_expense_records", stats)

        st, logs = make_request("GET", "/developer/audit-logs", token=self.token_dev)
        self.assertEqual(st, 200)
        self.assertIsInstance(logs, list)

        # Verify no sensitive password/card credentials exposed in audit logs
        for log_entry in logs[:10]:
            self.assertNotIn("password", str(log_entry).lower())
            self.assertNotIn("cvv", str(log_entry).lower())
            self.assertNotIn("pin", str(log_entry).lower())

    def test_11_email_normalization_and_duplicate_prevention(self):
        import concurrent.futures
        norm_ts = int(time.time() * 1000)
        base_email = f"normuser_{norm_ts}@example.com"
        password = "SecurePassword123!"

        # 1. Registration with a new email succeeds
        st, res = make_request("POST", "/register", {
            "name": "Normal User",
            "email": base_email,
            "password": password
        })
        self.assertIn(st, (200, 201), f"New user registration failed: {res}")
        self.assertEqual(res["email"], base_email.lower())

        # 2. Registration with the exact same email and different name is rejected with 409 Conflict
        st, res = make_request("POST", "/register", {
            "name": "Different Name Same Email",
            "email": base_email,
            "password": password
        })
        self.assertEqual(st, 409, f"Duplicate email was not rejected with 409: st={st}, res={res}")
        self.assertEqual(res.get("detail"), "Email already registered")

        # 3. Registration with different casing (e.g. UPPERCASE) is rejected with 409 Conflict
        upper_email = f"NORMUSER_{norm_ts}@EXAMPLE.COM"
        st, res = make_request("POST", "/register", {
            "name": "Uppercase User",
            "email": upper_email,
            "password": password
        })
        self.assertEqual(st, 409, f"Uppercase duplicate was not rejected with 409: st={st}, res={res}")
        self.assertEqual(res.get("detail"), "Email already registered")

        # 4. Registration with surrounding whitespace is rejected with 409 Conflict
        space_email = f"   {base_email}   "
        st, res = make_request("POST", "/register", {
            "name": "Space User",
            "email": space_email,
            "password": password
        })
        self.assertEqual(st, 409, f"Whitespace duplicate was not rejected with 409: st={st}, res={res}")
        self.assertEqual(res.get("detail"), "Email already registered")

        # 5. Concurrent registration requests cannot create duplicate accounts
        concurrent_email = f"concurrent_{norm_ts}@example.com"
        def try_register(user_name):
            return make_request("POST", "/register", {
                "name": user_name,
                "email": concurrent_email,
                "password": password
            })

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(try_register, f"Worker {i}") for i in range(5)]
            results = [f.result() for f in futures]

        statuses = [r[0] for r in results]
        success_count = sum(1 for s in statuses if s in (200, 201))
        conflict_count = sum(1 for s in statuses if s == 409)
        self.assertEqual(success_count, 1, f"Expected exactly 1 success in concurrent registration, got: {statuses}")
        self.assertEqual(conflict_count, 4, f"Expected 4 conflicts in concurrent registration, got: {statuses}")

        # 6. Login succeeds with valid credentials (case-insensitive & trimmed)
        st, res = make_request("POST", "/login", {
            "username": f"  {base_email.upper()}  ",
            "password": password
        }, urlencoded=True)
        self.assertEqual(st, 200, f"Login with case/space variations failed: {res}")
        self.assertIn("access_token", res)

        # 7. Login fails with invalid password (401 Unauthorized without leaking sensitive info)
        st, res = make_request("POST", "/login", {
            "username": base_email,
            "password": "WrongPassword999!"
        }, urlencoded=True)
        self.assertEqual(st, 401)
        self.assertEqual(res.get("detail"), "Invalid email or password")

        # 8. Login fails with non-existent email (401 Unauthorized with same generic message)
        st, res = make_request("POST", "/login", {
            "username": f"nonexistent_{norm_ts}@example.com",
            "password": password
        }, urlencoded=True)
        self.assertEqual(st, 401)
        self.assertEqual(res.get("detail"), "Invalid email or password")


if __name__ == "__main__":
    unittest.main()

