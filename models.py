from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    TIMESTAMP,
    DECIMAL,
    Date,
    DateTime,
    ForeignKey,
    func
)
from database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        Enum("USER", "DEVELOPER", name="user_role"),
        nullable=False,
        default="USER"
    )
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)

class Income(Base):
    __tablename__ = "income"

    income_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False
    )
    amount = Column(DECIMAL(12, 2), nullable=False)
    source = Column(String(100), nullable=False)
    income_date = Column(Date, nullable=False)
    description = Column(String(255))
    source_type = Column(String(50))
    created_at = Column(TIMESTAMP)


class Expense(Base):
    __tablename__ = "expenses"

    expense_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False
    )
    amount = Column(DECIMAL(12, 2), nullable=False)
    category = Column(String(100), nullable=False)
    merchant = Column(String(150))
    expense_date = Column(Date, nullable=False)
    description = Column(String(255))
    payment_method = Column(String(50))
    source = Column(String(50), default="MANUAL")
    created_at = Column(TIMESTAMP)


class Budget(Base):
    __tablename__ = "budgets"

    budget_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    category = Column(String(100), nullable=False)
    limit_amount = Column(DECIMAL(12, 2), nullable=False)
    period = Column(String(30), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    created_at = Column(TIMESTAMP)


class IncomeAllocation(Base):
    __tablename__ = "income_allocations"

    allocation_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)

    title = Column(String(150), nullable=False)
    category = Column(String(100), nullable=True)

    planned_amount = Column(DECIMAL(12, 2), nullable=False)
    actual_amount = Column(DECIMAL(12, 2), default=0.00)

    due_date = Column(Date, nullable=True)

    status = Column(
        Enum("PENDING", "COMPLETED", "CANCELLED", name="allocation_status"),
        default="PENDING"
    )

    description = Column(String(255), nullable=True)

    created_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(Integer, nullable=True)
    timestamp = Column(TIMESTAMP)




class SplitBill(Base):
    __tablename__ = "split_bills"

    split_bill_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    title = Column(String(150), nullable=False)
    total_amount = Column(DECIMAL(12, 2), nullable=False)
    bill_date = Column(Date, nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP)


class SplitParticipant(Base):
    __tablename__ = "split_participants"

    participant_id = Column(Integer, primary_key=True, index=True)
    split_bill_id = Column(
        Integer, ForeignKey("split_bills.split_bill_id"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    name = Column(String(100), nullable=False)
    share_amount = Column(DECIMAL(12, 2), nullable=False)
    amount_paid = Column(DECIMAL(12, 2), default=0.00)
    status = Column(
        Enum("PENDING", "PARTIAL", "PAID", name="participant_status"),
        default="PENDING"
    )


class Settlement(Base):
    __tablename__ = "settlements"

    settlement_id = Column(Integer, primary_key=True, index=True)
    split_bill_id = Column(
        Integer, ForeignKey("split_bills.split_bill_id"), nullable=False
    )
    participant_id = Column(
        Integer, ForeignKey("split_participants.participant_id"), nullable=False
    )
    amount = Column(DECIMAL(12, 2), nullable=False)
    settlement_date = Column(Date, nullable=True)
    status = Column(
        Enum("PENDING", "PAID", "CANCELLED", name="settlement_status"),
        default="PENDING"
    )
    created_at = Column(TIMESTAMP)


class Card(Base):
    __tablename__ = "cards"

    card_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False
    )
    card_name = Column(String(100), nullable=False)
    issuer = Column(String(100), nullable=False)
    card_type = Column(
        Enum("DEBIT", "CREDIT", name="card_type_enum"),
        nullable=False
    )
    network = Column(String(50), nullable=True)
    last_four_digits = Column(String(4), nullable=True)
    expiry_month = Column(Integer, nullable=True)
    expiry_year = Column(Integer, nullable=True)
    created_at = Column(
        DateTime,
        server_default=func.current_timestamp()
    )



class CardBenefit(Base):
    __tablename__ = "card_benefits"

    benefit_id = Column(Integer, primary_key=True, index=True)
    card_id = Column(
        Integer,
        ForeignKey("cards.card_id"),
        nullable=False
    )
    category = Column(String(100), nullable=False)
    benefit_type = Column(String(50), nullable=False)
    benefit_value = Column(DECIMAL(10, 2), nullable=False)
    conditions = Column(String(255), nullable=True)
    created_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp()
    )


class CardUsage(Base):
    __tablename__ = "card_usage"

    usage_id = Column(Integer, primary_key=True, index=True)
    card_id = Column(
        Integer,
        ForeignKey("cards.card_id"),
        nullable=False
    )
    expense_id = Column(
        Integer,
        ForeignKey("expenses.expense_id"),
        nullable=False
    )
    benefit_received = Column(DECIMAL(10, 2), nullable=True)
    used_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp()
    )


class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False
    )
    title = Column(String(150), nullable=False)
    message = Column(String(500), nullable=False)
    notification_type = Column(String(50), nullable=True)
    is_read = Column(Integer, default=0, nullable=False)
    created_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp()
    )