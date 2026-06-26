from __future__ import annotations

from dataclasses import dataclass

from .store import _init_all_tables, _make_connection


@dataclass(frozen=True)
class TransactionRecord:
    id: int
    user_id: int
    type: str
    amount: int
    balance_after: int
    ref_request_id: int | None
    note: str | None
    created_at: str


class BalanceService:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        _init_all_tables(database_path)

    def topup(self, user_id: int, amount: int, note: str = "") -> None:
        conn = _make_connection(self.database_path)
        try:
            conn.execute("BEGIN")
            conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, user_id))
            new_bal = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()[0]
            conn.execute(
                "INSERT INTO transactions (user_id,type,amount,balance_after,note) VALUES (?,'topup',?,?,?)",
                (user_id, amount, new_bal, note or None),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def refund(self, user_id: int, amount: int, ref_request_id: int) -> None:
        conn = _make_connection(self.database_path)
        try:
            conn.execute("BEGIN")
            conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, user_id))
            new_bal = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()[0]
            conn.execute(
                "INSERT INTO transactions (user_id,type,amount,balance_after,ref_request_id) VALUES (?,'refund',?,?,?)",
                (user_id, amount, new_bal, ref_request_id),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def get_transactions(self, user_id: int, limit: int = 50) -> list[TransactionRecord]:
        conn = _make_connection(self.database_path)
        rows = conn.execute(
            "SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        conn.close()
        return [TransactionRecord(**dict(r)) for r in rows]
