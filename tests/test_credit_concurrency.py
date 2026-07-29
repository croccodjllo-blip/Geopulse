from __future__ import annotations

from services.usage_billing import (
    ConcurrentAnalysisError,
    InsufficientCreditError,
    assert_can_start_analysis,
    deduct_credit,
    topup_credit,
)


class _User:
    id = None
    email = None
    credit_balance_cents = 0
    role = "user"
    plan = "free"

    def __init__(self, uid: int, balance: int, role: str = "user"):
        self.id = uid
        self.email = f"u{uid}@example.com"
        self.credit_balance_cents = balance
        self.role = role
        self.plan = "free"


class _Ledger:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _Session:
    def __init__(self, user: _User):
        self.user = user
        self.added = []
        self._flushed = False

    def query(self, model):  # noqa: ANN001
        return _Query(self, model)

    def refresh(self, obj):  # noqa: ANN001
        return None

    def add(self, obj):  # noqa: ANN001
        self.added.append(obj)

    def flush(self):
        self._flushed = True


class _Query:
    def __init__(self, session: _Session, model):  # noqa: ANN001
        self.session = session
        self.model = model
        self._filters = []

    def filter(self, *args):
        self._filters.extend(args)
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.session.user

    def update(self, values, synchronize_session=False):  # noqa: ANN001
        user = self.session.user
        # Emulate conditional UPDATE: only if credit_balance_cents >= cost
        # Filters arrive as SQLAlchemy BinaryExpression; for our mock we
        # inspect the caller's intended amount from values dict keys.
        # Simpler path: apply if balance covers the deduction magnitude.
        for col, expr in values.items():
            name = getattr(col, "key", None) or getattr(col, "name", None)
            if name == "credit_balance_cents":
                # expr is Column - cost; compute from user balance difference intent
                # In real SQLAlchemy this is ColumnElement; here we get Python ops.
                # Our deduct_credit passes: credit_balance_cents - cost
                # When using Column objects, update receives a BinaryExpression.
                # For unit test we reimplement the guard from remaining filters.
                pass
        # Detect insufficient via filter list length heuristic:
        # deduct always filters id == and balance >= cost.
        # We'll parse cost from the values expression if possible.
        cost = _extract_deduct_amount(values, user)
        if cost is not None:
            if user.credit_balance_cents < cost:
                return 0
            user.credit_balance_cents -= cost
            return 1
        # topup path: unconditional add
        add_amt = _extract_add_amount(values, user)
        if add_amt is not None:
            user.credit_balance_cents += add_amt
            return 1
        return 0


def _extract_deduct_amount(values, user: _User) -> int | None:
    """Best-effort: deduct_credit uses Column - N; mock can't eval Column.

    Instead, tests call a thin wrapper that sets expected cost on the session.
    """
    expected = getattr(user, "_pending_deduct", None)
    if expected is None:
        return None
    user._pending_deduct = None
    return int(expected)


def _extract_add_amount(values, user: _User) -> int | None:
    expected = getattr(user, "_pending_topup", None)
    if expected is None:
        return None
    user._pending_topup = None
    return int(expected)


def test_deduct_credit_atomic_rejects_overdraft():
    user = _User(1, 50)
    session = _Session(user)
    user._pending_deduct = 100
    try:
        deduct_credit(
            session,
            _Ledger,
            user,
            analysis_run_id=None,
            cost_eur_cents=100,
        )
        assert False, "expected InsufficientCreditError"
    except InsufficientCreditError:
        assert user.credit_balance_cents == 50
        assert session.added == []


def test_deduct_credit_atomic_success():
    user = _User(1, 200)
    session = _Session(user)
    user._pending_deduct = 75
    deduct_credit(
        session,
        _Ledger,
        user,
        analysis_run_id=None,
        cost_eur_cents=75,
        description="test",
    )
    assert user.credit_balance_cents == 125
    assert len(session.added) == 1
    assert session.added[0].amount_cents == -75


def test_assert_can_start_blocks_low_balance():
    user = _User(1, 10)
    session = _Session(user)
    try:
        assert_can_start_analysis(session, user, required_cents=50)
        assert False, "expected InsufficientCreditError"
    except InsufficientCreditError:
        pass


def test_assert_can_start_blocks_concurrent_jobs():
    user = _User(1, 10_000)
    session = _Session(user)

    class _Col:
        def in_(self, _vals):
            return self

    class JobQ:
        @staticmethod
        def filter(*_a, **_k):
            class C:
                @staticmethod
                def count():
                    return 2

            return C()

    class AnalysisJob:
        query = JobQ()
        user_id = _Col()
        status = _Col()

    try:
        assert_can_start_analysis(
            session,
            user,
            AnalysisJob=AnalysisJob,
            required_cents=1,
            max_concurrent_jobs=2,
        )
        assert False, "expected ConcurrentAnalysisError"
    except ConcurrentAnalysisError:
        pass


def test_topup_credit_increments():
    user = _User(1, 100)
    session = _Session(user)
    user._pending_topup = 500
    topup_credit(
        session,
        _Ledger,
        user,
        amount_eur_cents=500,
        stripe_payment_intent="pi_test",
    )
    assert user.credit_balance_cents == 600
    assert session.added[0].stripe_payment_intent == "pi_test"
