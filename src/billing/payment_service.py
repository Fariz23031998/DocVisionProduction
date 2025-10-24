from typing import List

from src.core.db import DatabaseConnection
from src.models.billing import PaymentCreateRequest, PaymentGetResponse


class PaymentService:
    @staticmethod
    async def create_payment(payment: PaymentCreateRequest) -> bool:
        query = """
        INSERT INTO payments (amount, provider, subscription_id)
        VALUES (?, ?, ?)
        """
        async with DatabaseConnection() as db:
            result = await db.execute_one(
                query=query,
                params=(payment.amount, payment.provider, payment.subscription_id),
                commit=True,
                raise_http=False
            )

            if result.get("rows_affected", 0) == 0:
                return False
            else:
                return True

    @staticmethod
    async def get_payments() -> List[PaymentGetResponse] | []:
        async with DatabaseConnection() as db:
            result = await db.fetch_all(
                query="SELECT * FROM payments WHERE is_cancelled = 0",
                raise_http=False
            )

            if not result:
                return []

        return [PaymentGetResponse(**dict(row)) for row in result]


