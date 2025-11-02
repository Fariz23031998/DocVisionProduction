from typing import List
import logging

from src.core.db import DatabaseConnection
from src.models.billing import PaymentCreateRequest, PaymentGetResponse

logger = logging.getLogger("DocVision")


class PaymentService:
    @staticmethod
    async def create_payment(payment: PaymentCreateRequest) -> bool:
        query = """
        INSERT INTO payments (amount, provider, user_id)
        VALUES (?, ?, ?)
        """
        async with DatabaseConnection() as db:
            result = await db.execute_one(
                query=query,
                params=(payment.amount, payment.provider, payment.user_id),
                commit=True,
                raise_http=False
            )

            if result.get("rows_affected", 0) == 0:
                return False
            else:
                return True

    @staticmethod
    async def get_payments(user_id: str) -> List[PaymentGetResponse]:
        async with DatabaseConnection() as db:
            result = await db.fetch_all(
                query="SELECT * FROM payments WHERE user_id = ?",
                params=(user_id, ),
                raise_http=False
            )

            if not result:
                return []
        logger.info(f"{result}")
        return [PaymentGetResponse(**dict(row)) for row in result]


