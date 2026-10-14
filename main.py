from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import date, datetime
from decimal import Decimal
import os
import re
from typing import Optional, List, Dict, Any
from auth import (
    SECRET_KEY,
    ALGORITHM,
    hash_password,
    verify_password,
    create_access_token
)
from database import get_db
from models import (
    User, Income, Expense, Budget, IncomeAllocation, AuditLog,
    SplitBill, SplitParticipant, Settlement, Card, CardBenefit,
    CardUsage, Notification
)
from schemas import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    IncomeCreate,
    ExpenseCreate,
    BudgetCreate,
    IncomeAllocationCreate,
    SplitBillCreate,
    SettlementCreate,
    CardCreate,
    CardBenefitCreate,
    CardUsageCreate,
    AIAssistantRequest,
    SMSParseRequest,
    SMSConfirmRequest,
    NotificationResponse
)


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/login"
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials"
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("user_id")

        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(
        User.user_id == user_id
    ).first()

    if user is None:
        raise credentials_exception

    return user


def require_developer(
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "DEVELOPER":
        raise HTTPException(
            status_code=403,
            detail="Developer access required"
        )

    return current_user


def create_system_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: str = "SYSTEM"
):
    try:
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            is_read=0
        )
        db.add(notif)
        db.commit()
        return notif
    except Exception:
        db.rollback()
        return None


app = FastAPI(title="FinTrack API")
default_dev_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

env_origins = []
raw_allowed_origins = os.getenv("ALLOWED_ORIGINS") or os.getenv("FRONTEND_URL", "")
if raw_allowed_origins:
    env_origins = [origin.strip().rstrip("/") for origin in raw_allowed_origins.split(",") if origin.strip()]

allowed_origins = list(dict.fromkeys(default_dev_origins + env_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https:\/\/.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_db_init():
    """
    Safe and idempotent database initialization on application startup.
    Ensures missing tables exist without modifying or dropping existing data.
    """
    try:
        from database import init_db, engine
        init_db()
        dialect_name = engine.dialect.name
        masked_host = engine.url.host or "local"
        print(f"[FinTrack Startup] Database tables verified on {dialect_name} ({masked_host})")
    except Exception as e:
        import traceback
        print(f"[FinTrack Startup ERROR] Database initialization encountered an error: {e}")
        traceback.print_exc()


@app.get("/")
def root():
    return {
        "message": "FinTrack API is running"
    }


@app.get("/db-test")
def db_test():
    try:
        from database import engine

        with engine.connect() as conn:
            dialect_name = engine.dialect.name
            driver_name = engine.dialect.driver
            db_name = engine.url.database or "default"
            return {
                "message": f"{dialect_name.upper()} database connected successfully",
                "dialect": dialect_name,
                "driver": driver_name,
                "database": db_name,
                "status": "connected"
            }

    except Exception as e:
        return {
            "message": "Database connection failed",
            "error": str(e),
            "status": "error"
        }


@app.post("/register", response_model=UserResponse)
def register(
    user_data: RegisterRequest,
    db: Session = Depends(get_db)
):
    normalized_email = str(user_data.email).strip().lower()

    existing_user = db.query(User).filter(
        func.lower(func.trim(User.email)) == normalized_email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    clean_name = user_data.name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=400,
            detail="Name cannot be empty"
        )

    new_user = User(
        name=clean_name,
        email=normalized_email,
        password_hash=hash_password(user_data.password),
        role="USER"
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    return new_user


@app.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    normalized_email = form_data.username.strip().lower() if form_data.username else ""

    user = db.query(User).filter(
        func.lower(func.trim(User.email)) == normalized_email
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not verify_password(
        form_data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    token = create_access_token({
        "user_id": user.user_id,
        "role": user.role
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@app.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user)
):
    return current_user


@app.get("/developer-test")
def developer_test(
    current_user: User = Depends(require_developer)
):
    return {
        "message": "Developer access granted",
        "user": current_user.name,
        "role": current_user.role
    }


@app.post("/income")
def add_income(
    income_data: IncomeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if income_data.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Income amount must be greater than zero"
        )

    income = Income(
        user_id=current_user.user_id,
        amount=income_data.amount,
        source=income_data.source,
        income_date=income_data.income_date,
        description=income_data.description,
        source_type=income_data.source_type
    )

    db.add(income)
    db.commit()
    db.refresh(income)

    audit = AuditLog(
        user_id=current_user.user_id,
        action="CREATED",
        entity_type="INCOME",
        entity_id=income.income_id
    )

    db.add(audit)
    db.commit()

    return {
        "message": "Income added successfully",
        "income_id": income.income_id,
        "amount": income.amount
    }


@app.get("/income")
def get_income(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Income).filter(
        Income.user_id == current_user.user_id
    ).order_by(
        Income.income_date.desc()
    ).all()


@app.delete("/income/{income_id}")
def delete_income(
    income_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    income = db.query(Income).filter(
        Income.income_id == income_id,
        Income.user_id == current_user.user_id
    ).first()

    if not income:
        raise HTTPException(status_code=404, detail="Income record not found")

    db.delete(income)
    db.commit()

    audit = AuditLog(
        user_id=current_user.user_id,
        action="DELETED",
        entity_type="INCOME",
        entity_id=income_id
    )
    db.add(audit)
    db.commit()

    return {
        "message": "Income record deleted successfully",
        "income_id": income_id
    }


@app.post("/expense")
def add_expense(
    expense_data: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if expense_data.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Expense amount must be greater than zero"
        )

    expense = Expense(
        user_id=current_user.user_id,
        amount=expense_data.amount,
        category=expense_data.category,
        merchant=expense_data.merchant,
        expense_date=expense_data.expense_date,
        description=expense_data.description,
        payment_method=expense_data.payment_method,
        source=expense_data.source
    )

    db.add(expense)
    db.commit()
    db.refresh(expense)

    audit = AuditLog(
        user_id=current_user.user_id,
        action="CREATED",
        entity_type="EXPENSE",
        entity_id=expense.expense_id
    )

    db.add(audit)
    db.commit()

    # Trigger real-time budget notification if near or over budget
    try:
        active_budgets = db.query(Budget).filter(
            Budget.user_id == current_user.user_id,
            Budget.category == expense.category,
            Budget.start_date <= expense.expense_date,
            Budget.end_date >= expense.expense_date
        ).all()

        for b in active_budgets:
            total_cat_spent = db.query(
                func.coalesce(func.sum(Expense.amount), 0)
            ).filter(
                Expense.user_id == current_user.user_id,
                Expense.category == b.category,
                Expense.expense_date >= b.start_date,
                Expense.expense_date <= b.end_date
            ).scalar()

            total_cat_spent = float(total_cat_spent or 0)
            b_limit = float(b.limit_amount or 0)
            if b_limit > 0:
                util = (total_cat_spent / b_limit) * 100
                if total_cat_spent > b_limit:
                    create_system_notification(
                        db,
                        current_user.user_id,
                        f"Over Budget Alert: {b.category}",
                        f"You have spent ₹{total_cat_spent:,.2f}, exceeding your {b.category} budget limit of ₹{b_limit:,.2f}.",
                        "BUDGET"
                    )
                elif util >= 80:
                    create_system_notification(
                        db,
                        current_user.user_id,
                        f"Budget Warning: {b.category}",
                        f"You have reached {util:.1f}% of your {b.category} budget (₹{total_cat_spent:,.2f} / ₹{b_limit:,.2f}).",
                        "BUDGET"
                    )
    except Exception:
        pass

    return {
        "message": "Expense added successfully",
        "expense_id": expense.expense_id,
        "amount": expense.amount
    }


@app.get("/expenses")
def get_expenses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Expense).filter(
        Expense.user_id == current_user.user_id
    ).order_by(
        Expense.expense_date.desc()
    ).all()


@app.delete("/expenses/{expense_id}")
def delete_expense(
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    expense = db.query(Expense).filter(
        Expense.expense_id == expense_id,
        Expense.user_id == current_user.user_id
    ).first()

    if not expense:
        raise HTTPException(status_code=404, detail="Expense record not found")

    # Clean up linked card usage if any
    db.query(CardUsage).filter(CardUsage.expense_id == expense_id).delete()

    db.delete(expense)
    db.commit()

    audit = AuditLog(
        user_id=current_user.user_id,
        action="DELETED",
        entity_type="EXPENSE",
        entity_id=expense_id
    )
    db.add(audit)
    db.commit()

    return {
        "message": "Expense record deleted successfully",
        "expense_id": expense_id
    }


@app.get("/dashboard")
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    total_income = db.query(Income).filter(
        Income.user_id == current_user.user_id
    ).with_entities(
        func.coalesce(func.sum(Income.amount), 0)
    ).scalar()

    total_expenses = db.query(Expense).filter(
        Expense.user_id == current_user.user_id
    ).with_entities(
        func.coalesce(func.sum(Expense.amount), 0)
    ).scalar()

    balance = total_income - total_expenses

    transaction_count = (
        db.query(Income).filter(Income.user_id == current_user.user_id).count()
        +
        db.query(Expense).filter(Expense.user_id == current_user.user_id).count()
    )

    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": balance,
        "transaction_count": transaction_count
    }


@app.get("/dashboard-filtered")
def get_filtered_dashboard(
    start_date: date,
    end_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    total_income = db.query(
        func.coalesce(func.sum(Income.amount), 0)
    ).filter(
        Income.user_id == current_user.user_id,
        Income.income_date >= start_date,
        Income.income_date <= end_date
    ).scalar()

    
    regular_expenses = db.query(
        func.coalesce(func.sum(Expense.amount), 0)
    ).filter(
        Expense.user_id == current_user.user_id,
        Expense.expense_date >= start_date,
        Expense.expense_date <= end_date
    ).scalar()

    split_expenses = db.query(
        func.coalesce(func.sum(SplitParticipant.share_amount), 0)
    ).join(
        SplitBill,
        SplitParticipant.split_bill_id == SplitBill.split_bill_id
    ).filter(
        SplitParticipant.user_id == current_user.user_id,
        SplitBill.bill_date >= start_date,
        SplitBill.bill_date <= end_date
    ).scalar()

    total_expenses = float(regular_expenses or 0) + float(split_expenses or 0)


    balance = float(total_income or 0) - total_expenses

    income_count = db.query(Income).filter(
        Income.user_id == current_user.user_id,
        Income.income_date >= start_date,
        Income.income_date <= end_date
    ).count()

    expense_count = db.query(Expense).filter(
        Expense.user_id == current_user.user_id,
        Expense.expense_date >= start_date,
        Expense.expense_date <= end_date
    ).count()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": balance,
        "transaction_count": income_count + expense_count
    }

@app.get("/monthly-analytics")
def get_monthly_analytics(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=400,
            detail="Month must be between 1 and 12"
        )

    if year < 1:
        raise HTTPException(
            status_code=400,
            detail="Year must be greater than 0"
        )

    start_date = date(year, month, 1)

    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    total_income = db.query(
        func.coalesce(func.sum(Income.amount), 0)
    ).filter(
        Income.user_id == current_user.user_id,
        Income.income_date >= start_date,
        Income.income_date < end_date
    ).scalar()

    regular_expenses = db.query(
        func.coalesce(func.sum(Expense.amount), 0)
    ).filter(
        Expense.user_id == current_user.user_id,
        Expense.expense_date >= start_date,
        Expense.expense_date < end_date
    ).scalar()

    split_expenses = db.query(
        func.coalesce(func.sum(SplitParticipant.share_amount), 0)
    ).join(
        SplitBill,
        SplitParticipant.split_bill_id == SplitBill.split_bill_id
    ).filter(
        SplitParticipant.user_id == current_user.user_id,
        SplitBill.bill_date >= start_date,
        SplitBill.bill_date < end_date
    ).scalar()

    income = float(total_income or 0)
    regular = float(regular_expenses or 0)
    split = float(split_expenses or 0)

    total_expenses = regular + split
    balance = income - total_expenses

    savings_rate = (
        (balance / income) * 100
        if income > 0
        else None
    )

    return {
        "year": year,
        "month": month,
        "total_income": round(income, 2),
        "regular_expenses": round(regular, 2),
        "split_bill_expenses": round(split, 2),
        "total_expenses": round(total_expenses, 2),
        "balance": round(balance, 2),
        "savings_rate_percent": (
            round(savings_rate, 2)
            if savings_rate is not None
            else None
        )
    }


@app.get("/monthly-comparison")
def get_monthly_comparison(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=400,
            detail="Month must be between 1 and 12"
        )

    if year < 1:
        raise HTTPException(
            status_code=400,
            detail="Year must be greater than 0"
        )

    current_start = date(year, month, 1)

    if month == 12:
        next_start = date(year + 1, 1, 1)
    else:
        next_start = date(year, month + 1, 1)

    previous_start = date(year, month - 1, 1) if month > 1 else date(year - 1, 12, 1)

    # Avoid constructing year 0 when comparing January of year 1.
    if year == 1 and month == 1:
        raise HTTPException(
            status_code=400,
            detail="Previous-month comparison is unavailable for January of year 1"
        )

    def get_totals(start_date, end_date):
        income = db.query(
            func.coalesce(func.sum(Income.amount), 0)
        ).filter(
            Income.user_id == current_user.user_id,
            Income.income_date >= start_date,
            Income.income_date < end_date
        ).scalar()

        regular_expenses = db.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).filter(
            Expense.user_id == current_user.user_id,
            Expense.expense_date >= start_date,
            Expense.expense_date < end_date
        ).scalar()

        split_expenses = db.query(
            func.coalesce(func.sum(SplitParticipant.share_amount), 0)
        ).join(
            SplitBill,
            SplitParticipant.split_bill_id == SplitBill.split_bill_id
        ).filter(
            SplitParticipant.user_id == current_user.user_id,
            SplitBill.bill_date >= start_date,
            SplitBill.bill_date < end_date
        ).scalar()

        total_income = float(income or 0)
        total_expenses = (
            float(regular_expenses or 0)
            + float(split_expenses or 0)
        )

        return {
            "income": round(total_income, 2),
            "expenses": round(total_expenses, 2),
            "balance": round(total_income - total_expenses, 2)
        }

    current = get_totals(current_start, next_start)
    previous = get_totals(previous_start, current_start)

    def calculate_change(current_value, previous_value):
        difference = round(current_value - previous_value, 2)

        percentage = (
            round((difference / abs(previous_value)) * 100, 2)
            if previous_value != 0
            else None
        )

        return {
            "difference": difference,
            "percentage_change": percentage
        }

    return {
        "current_month": {
            "year": year,
            "month": month,
            **current
        },
        "previous_month": {
            "year": previous_start.year,
            "month": previous_start.month,
            **previous
        },
        "comparison": {
            "income": calculate_change(
                current["income"], previous["income"]
            ),
            "expenses": calculate_change(
                current["expenses"], previous["expenses"]
            ),
            "balance": calculate_change(
                current["balance"], previous["balance"]
            )
        }
    }


@app.get("/monthly-category-analysis")
def get_monthly_category_analysis(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=400,
            detail="Month must be between 1 and 12"
        )

    if year < 1:
        raise HTTPException(
            status_code=400,
            detail="Year must be greater than 0"
        )

    start_date = date(year, month, 1)

    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    category_totals = {}

    # Regular expenses grouped by category
    regular_summary = db.query(
        Expense.category,
        func.sum(Expense.amount).label("total_amount")
    ).filter(
        Expense.user_id == current_user.user_id,
        Expense.expense_date >= start_date,
        Expense.expense_date < end_date
    ).group_by(
        Expense.category
    ).all()

    for category, amount in regular_summary:
        category_name = category or "Uncategorized"
        category_totals[category_name] = (
            category_totals.get(category_name, 0)
            + float(amount or 0)
        )

    # Linked split-bill shares for this user
    split_total = db.query(
        func.coalesce(
            func.sum(SplitParticipant.share_amount), 0
        )
    ).join(
        SplitBill,
        SplitParticipant.split_bill_id == SplitBill.split_bill_id
    ).filter(
        SplitParticipant.user_id == current_user.user_id,
        SplitBill.bill_date >= start_date,
        SplitBill.bill_date < end_date
    ).scalar()

    if float(split_total or 0) > 0:
        category_totals["Split Bills"] = (
            category_totals.get("Split Bills", 0)
            + float(split_total)
        )

    total_expenses = sum(category_totals.values())

    categories = [
        {
            "category": category,
            "amount": round(amount, 2),
            "percentage": round(
                (amount / total_expenses) * 100, 2
            ) if total_expenses > 0 else 0
        }
        for category, amount in sorted(
            category_totals.items(),
            key=lambda item: item[1],
            reverse=True
        )
    ]

    return {
        "year": year,
        "month": month,
        "total_expenses": round(total_expenses, 2),
        "category_count": len(categories),
        "categories": categories
    }


@app.post("/budget")
def add_budget(
    budget_data: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if budget_data.limit_amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Budget limit amount must be greater than zero"
        )

    if budget_data.start_date > budget_data.end_date:
        raise HTTPException(
            status_code=400,
            detail="Budget start date cannot be after end date"
        )

    # Prevent duplicate budgets for the same user,
    # category, and date range.
    existing_budget = db.query(Budget).filter(
        Budget.user_id == current_user.user_id,
        Budget.category == budget_data.category,
        Budget.start_date == budget_data.start_date,
        Budget.end_date == budget_data.end_date
    ).first()

    if existing_budget:
        raise HTTPException(
            status_code=409,
            detail=(
                "A budget already exists for this category "
                "and date range."
            )
        )

    budget = Budget(
        user_id=current_user.user_id,
        category=budget_data.category,
        limit_amount=budget_data.limit_amount,
        period=budget_data.period,
        start_date=budget_data.start_date,
        end_date=budget_data.end_date
    )

    db.add(budget)
    db.commit()
    db.refresh(budget)

    audit = AuditLog(
        user_id=current_user.user_id,
        action="CREATED",
        entity_type="BUDGET",
        entity_id=budget.budget_id
    )

    db.add(audit)
    db.commit()

    return {
        "message": "Budget added successfully",
        "budget_id": budget.budget_id,
        "category": budget.category,
        "limit_amount": budget.limit_amount,
        "period": budget.period
    }

@app.get("/budgets")
def get_budgets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    budgets = db.query(Budget).filter(
        Budget.user_id == current_user.user_id
    ).order_by(
        Budget.start_date.desc()
    ).all()

    return budgets

@app.post("/allocation")
def add_income_allocation(
    allocation_data: IncomeAllocationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    allocation = IncomeAllocation(
        user_id=current_user.user_id,
        title=allocation_data.title,
        category=allocation_data.category,
        planned_amount=allocation_data.planned_amount,
        due_date=allocation_data.due_date,
        description=allocation_data.description
    )

    db.add(allocation)
    db.commit()
    db.refresh(allocation)

    audit = AuditLog(
        user_id=current_user.user_id,
        action="CREATED",
        entity_type="INCOME_ALLOCATION",
        entity_id=allocation.allocation_id
    )

    db.add(audit)
    db.commit()

    return {
        "message": "Income allocation added successfully",
        "allocation_id": allocation.allocation_id,
        "title": allocation.title,
        "category": allocation.category,
        "planned_amount": allocation.planned_amount,
        "actual_amount": allocation.actual_amount,
        "due_date": allocation.due_date,
        "status": allocation.status
    }   
@app.get("/allocations")
def get_income_allocations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    allocations = (
        db.query(IncomeAllocation)
        .filter(IncomeAllocation.user_id == current_user.user_id)
        .order_by(IncomeAllocation.due_date.asc())
        .all()
    )

    return allocations

@app.patch("/allocations/{allocation_id}")
def update_income_allocation(
    allocation_id: int,
    actual_amount: Decimal,
    status: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    allocation = db.query(IncomeAllocation).filter(
        IncomeAllocation.allocation_id == allocation_id,
        IncomeAllocation.user_id == current_user.user_id
    ).first()

    if allocation is None:
        raise HTTPException(
            status_code=404,
            detail="Allocation not found"
        )

    if actual_amount < 0:
        raise HTTPException(
            status_code=400,
            detail="Actual amount cannot be negative"
        )

    if status not in ["PENDING", "COMPLETED", "CANCELLED"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid allocation status"
        )

    allocation.actual_amount = actual_amount
    allocation.status = status

    if status == "COMPLETED":
        allocation.completed_at = datetime.now()

    db.commit()
    db.refresh(allocation)

    return {
        "message": "Allocation updated successfully",
        "allocation_id": allocation.allocation_id,
        "actual_amount": allocation.actual_amount,
        "status": allocation.status
    }


@app.post("/split-bills")
def create_split_bill(
    data: SplitBillCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not data.participants:
        raise HTTPException(
            status_code=400,
            detail="At least one participant is required"
        )

    if data.total_amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Bill total must be greater than zero"
        )

    if any(p.share_amount <= 0 for p in data.participants):
        raise HTTPException(
            status_code=400,
            detail="Each participant share must be greater than zero"
        )

    total_shares = sum(
        (p.share_amount for p in data.participants),
        Decimal("0.00")
    )

    if total_shares != data.total_amount:
        raise HTTPException(
            status_code=400,
            detail="Participant shares must add up to the bill total"
        )

    bill = SplitBill(
        user_id=current_user.user_id,
        title=data.title,
        total_amount=data.total_amount,
        bill_date=data.bill_date,
        description=data.description
    )

    db.add(bill)
    db.flush()

    participants = []

    for person in data.participants:
        participant = SplitParticipant(
            split_bill_id=bill.split_bill_id,
            user_id=person.user_id,
            name=person.name,
            share_amount=person.share_amount,
            amount_paid=Decimal("0.00"),
            status="PENDING"
        )
        db.add(participant)
        participants.append(participant)

    db.commit()
    db.refresh(bill)

    return {
        "message": "Split bill created successfully",
        "split_bill_id": bill.split_bill_id,
        "title": bill.title,
        "total_amount": str(bill.total_amount),
        "participants": [
            {
                "participant_id": p.participant_id,
                "name": p.name,
                "share_amount": str(p.share_amount),
                "amount_paid": str(p.amount_paid),
                "status": p.status
            }
            for p in participants
        ]
    }



@app.get("/split-bills")
def get_split_bills(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    bills = (
        db.query(SplitBill)
        .filter(SplitBill.user_id == current_user.user_id)
        .order_by(SplitBill.bill_date.desc())
        .all()
    )

    result = []

    for bill in bills:
        participants = (
            db.query(SplitParticipant)
            .filter(SplitParticipant.split_bill_id == bill.split_bill_id)
            .all()
        )

        result.append({
            "split_bill_id": bill.split_bill_id,
            "title": bill.title,
            "total_amount": str(bill.total_amount),
            "bill_date": str(bill.bill_date),
            "description": bill.description,
            "participants": [
                {
                    "participant_id": p.participant_id,
                    "name": p.name,
                    "share_amount": str(p.share_amount),
                    "amount_paid": str(p.amount_paid),
                    "status": p.status
                }
                for p in participants
            ]
        })

    return result



@app.post("/split-bills/{split_bill_id}/settlements")
def create_settlement(
    split_bill_id: int,
    data: SettlementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    bill = (
        db.query(SplitBill)
        .filter(
            SplitBill.split_bill_id == split_bill_id,
            SplitBill.user_id == current_user.user_id
        )
        .first()
    )

    if bill is None:
        raise HTTPException(status_code=404, detail="Split bill not found")

    participant = (
        db.query(SplitParticipant)
        .filter(
            SplitParticipant.participant_id == data.participant_id,
            SplitParticipant.split_bill_id == split_bill_id
        )
        .first()
    )

    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")

    if data.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Settlement amount must be greater than zero"
        )

    outstanding = (
        Decimal(str(participant.share_amount))
        - Decimal(str(participant.amount_paid or 0))
    )

    if data.amount > outstanding:
        raise HTTPException(
            status_code=400,
            detail="Settlement exceeds the participant's outstanding balance"
        )

    try:
        settlement = Settlement(
            split_bill_id=split_bill_id,
            participant_id=participant.participant_id,
            amount=data.amount,
            settlement_date=data.settlement_date,
            status="PAID"
        )

        participant.amount_paid = (
            Decimal(str(participant.amount_paid or 0)) + data.amount
        )

        if participant.amount_paid >= participant.share_amount:
            participant.status = "PAID"
        elif participant.amount_paid > 0:
            participant.status = "PARTIAL"
        else:
            participant.status = "PENDING"

        db.add(settlement)
        db.commit()
        db.refresh(settlement)

        create_system_notification(
            db,
            current_user.user_id,
            "Split Bill Settlement Recorded",
            f"Settlement of ₹{data.amount} recorded for {participant.name} on '{bill.title}'. Status: {participant.status}.",
            "SETTLEMENT"
        )

        return {
            "message": "Settlement recorded successfully",
            "settlement_id": settlement.settlement_id,
            "participant_id": participant.participant_id,
            "amount_paid": str(participant.amount_paid),
            "outstanding_amount": str(
                Decimal(str(participant.share_amount))
                - Decimal(str(participant.amount_paid))
            ),
            "participant_status": participant.status,
            "settlement_status": settlement.status
        }

    except Exception:
        db.rollback()
        raise



@app.get("/budget-summary")
def get_budget_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    budgets = db.query(Budget).filter(
        Budget.user_id == current_user.user_id
    ).all()

    result = []

    for budget in budgets:
        total_spent = db.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).filter(
            Expense.user_id == current_user.user_id,
            Expense.category == budget.category,
            Expense.expense_date >= budget.start_date,
            Expense.expense_date <= budget.end_date
        ).scalar()

        # Include the user's linked split-bill shares
        # when the budget category is "Split Bills".
        if budget.category == "Split Bills":
            split_spent = db.query(
                func.coalesce(
                    func.sum(SplitParticipant.share_amount), 0
                )
            ).join(
                SplitBill,
                SplitParticipant.split_bill_id == SplitBill.split_bill_id
            ).filter(
                SplitParticipant.user_id == current_user.user_id,
                SplitBill.bill_date >= budget.start_date,
                SplitBill.bill_date <= budget.end_date
            ).scalar()

            total_spent = (
                float(total_spent or 0)
                + float(split_spent or 0)
            )

        total_spent = float(total_spent or 0)
        budget_limit = float(budget.limit_amount or 0)

        remaining = budget_limit - total_spent

        utilization = (
            (total_spent / budget_limit) * 100
            if budget_limit > 0
            else 0
        )

        result.append({
            "budget_id": budget.budget_id,
            "category": budget.category,
            "budget_limit": round(budget_limit, 2),
            "spent": round(total_spent, 2),
            "remaining": round(remaining, 2),
            "utilization_percentage": round(utilization, 2),
            "period": budget.period,
            "start_date": budget.start_date,
            "end_date": budget.end_date
        })

    return result




@app.get("/budget-alerts")
def get_budget_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    budgets = db.query(Budget).filter(
        Budget.user_id == current_user.user_id
    ).all()

    alerts = []

    for budget in budgets:
        total_spent = db.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).filter(
            Expense.user_id == current_user.user_id,
            Expense.category == budget.category,
            Expense.expense_date >= budget.start_date,
            Expense.expense_date <= budget.end_date
        ).scalar()

        spent = float(total_spent or 0)

        # Include linked split-bill shares in the Split Bills budget.
        if budget.category == "Split Bills":
            split_spent = db.query(
                func.coalesce(
                    func.sum(SplitParticipant.share_amount), 0
                )
            ).join(
                SplitBill,
                SplitParticipant.split_bill_id == SplitBill.split_bill_id
            ).filter(
                SplitParticipant.user_id == current_user.user_id,
                SplitBill.bill_date >= budget.start_date,
                SplitBill.bill_date <= budget.end_date
            ).scalar()

            spent += float(split_spent or 0)

        budget_limit = float(budget.limit_amount or 0)

        utilization = (
            (spent / budget_limit) * 100
            if budget_limit > 0
            else 0
        )

        if budget_limit > 0 and spent > budget_limit:
            status = "OVER_BUDGET"
            message = "You have exceeded your budget."
        elif budget_limit > 0 and utilization >= 90:
            status = "NEAR_LIMIT"
            message = "You have used at least 90% of your budget."
        else:
            status = "WITHIN_BUDGET"
            message = "Your spending is within the budget limit."

        alerts.append({
            "budget_id": budget.budget_id,
            "category": budget.category,
            "budget_limit": round(budget_limit, 2),
            "spent": round(spent, 2),
            "remaining": round(budget_limit - spent, 2),
            "utilization_percentage": round(utilization, 2),
            "status": status,
            "message": message
        })

    return alerts


@app.get("/users/lookup")
def lookup_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    users = (
        db.query(User.user_id, User.name)
        .filter(User.role == "USER")
        .order_by(User.name.asc())
        .all()
    )

    return [
        {
            "user_id": user_id,
            "name": name
        }
        for user_id, name in users
    ]


@app.get("/expense-summary")
def get_expense_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    regular_summary = db.query(
        Expense.category,
        func.sum(Expense.amount).label("total_amount")
    ).filter(
        Expense.user_id == current_user.user_id
    ).group_by(
        Expense.category
    ).all()

    totals = {}

    for category, total_amount in regular_summary:
        totals[category] = totals.get(category, Decimal("0.00")) + Decimal(
            str(total_amount or 0)
        )

    split_summary = db.query(
        func.sum(SplitParticipant.share_amount).label("total_amount")
    ).join(
        SplitBill,
        SplitParticipant.split_bill_id == SplitBill.split_bill_id
    ).filter(
        SplitParticipant.user_id == current_user.user_id
    ).scalar()

    if split_summary:
        totals["Split Bills"] = totals.get(
            "Split Bills", Decimal("0.00")
        ) + Decimal(str(split_summary))

    return [
        {
            "category": category,
            "total_amount": float(total_amount)
        }
        for category, total_amount in sorted(
            totals.items(),
            key=lambda item: item[1],
            reverse=True
        )
    ]



@app.get("/transactions")
def get_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    incomes = db.query(Income).filter(
        Income.user_id == current_user.user_id
    ).all()

    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.user_id
    ).all()

    transactions = []

    for income in incomes:
        transactions.append({
            "type": "INCOME",
            "id": income.income_id,
            "amount": income.amount,
            "category": income.source,
            "date": income.income_date,
            "description": income.description,
            "source": income.source_type
        })

    for expense in expenses:
        transactions.append({
            "type": "EXPENSE",
            "id": expense.expense_id,
            "amount": expense.amount,
            "category": expense.category,
            "date": expense.expense_date,
            "description": expense.description,
            "source": expense.source
        })

    transactions.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    return transactions


@app.get("/developer/stats")
def developer_stats(
    current_user: User = Depends(require_developer),
    db: Session = Depends(get_db)
):
    total_users = db.query(User).count()

    total_income = db.query(Income).count()

    total_expenses = db.query(Expense).count()

    total_budgets = db.query(Budget).count()

    return {
        "total_users": total_users,
        "total_income_records": total_income,
        "total_expense_records": total_expenses,
        "total_budgets": total_budgets
    }


@app.get("/developer/audit-logs")
def get_audit_logs(
    current_user: User = Depends(require_developer),
    db: Session = Depends(get_db)
):
    logs = db.query(AuditLog).order_by(
        AuditLog.timestamp.desc()
    ).all()

    return logs



@app.post("/cards")
def add_card(
    card_data: CardCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Validate card metadata
    if card_data.last_four_digits is not None:
        if (
            len(card_data.last_four_digits) != 4
            or not card_data.last_four_digits.isdigit()
        ):
            raise HTTPException(
                status_code=400,
                detail="Last four digits must contain exactly 4 numbers"
            )

    if card_data.expiry_month is not None:
        if not 1 <= card_data.expiry_month <= 12:
            raise HTTPException(
                status_code=400,
                detail="Expiry month must be between 1 and 12"
            )

    if card_data.expiry_year is not None:
        if card_data.expiry_year < 2000:
            raise HTTPException(
                status_code=400,
                detail="Expiry year is invalid"
            )

    card = Card(
        user_id=current_user.user_id,
        card_name=card_data.card_name,
        issuer=card_data.issuer,
        card_type=card_data.card_type,
        network=card_data.network,
        last_four_digits=card_data.last_four_digits,
        expiry_month=card_data.expiry_month,
        expiry_year=card_data.expiry_year
    )

    db.add(card)
    db.commit()
    db.refresh(card)

    return {
        "message": "Card added successfully",
        "card_id": card.card_id,
        "card_name": card.card_name,
        "issuer": card.issuer,
        "card_type": card.card_type,
        "network": card.network,
        "last_four_digits": card.last_four_digits,
        "expiry_month": card.expiry_month,
        "expiry_year": card.expiry_year
    }


@app.get("/cards")
def get_cards(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cards = db.query(Card).filter(
        Card.user_id == current_user.user_id
    ).order_by(
        Card.card_id.desc()
    ).all()

    return [
        {
            "card_id": card.card_id,
            "card_name": card.card_name,
            "issuer": card.issuer,
            "card_type": card.card_type,
            "network": card.network,
            "last_four_digits": card.last_four_digits,
            "expiry_month": card.expiry_month,
            "expiry_year": card.expiry_year,
            "created_at": card.created_at
        }
        for card in cards
    ]



@app.post("/cards/{card_id}/benefits")
def add_card_benefit(
    card_id: int,
    benefit_data: CardBenefitCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(
        Card.card_id == card_id,
        Card.user_id == current_user.user_id
    ).first()

    if not card:
        raise HTTPException(
            status_code=404,
            detail="Card not found"
        )

    benefit = CardBenefit(
        card_id=card_id,
        category=benefit_data.category,
        benefit_type=benefit_data.benefit_type,
        benefit_value=benefit_data.benefit_value,
        conditions=benefit_data.conditions
    )

    db.add(benefit)
    db.commit()
    db.refresh(benefit)

    return {
        "message": "Card benefit added successfully",
        "benefit_id": benefit.benefit_id,
        "card_id": benefit.card_id,
        "category": benefit.category,
        "benefit_type": benefit.benefit_type,
        "benefit_value": float(benefit.benefit_value),
        "conditions": benefit.conditions
    }


@app.get("/cards/{card_id}/benefits")
def get_card_benefits(
    card_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(
        Card.card_id == card_id,
        Card.user_id == current_user.user_id
    ).first()

    if not card:
        raise HTTPException(
            status_code=404,
            detail="Card not found"
        )

    benefits = db.query(CardBenefit).filter(
        CardBenefit.card_id == card_id
    ).order_by(
        CardBenefit.benefit_id.desc()
    ).all()

    return [
        {
            "benefit_id": benefit.benefit_id,
            "card_id": benefit.card_id,
            "category": benefit.category,
            "benefit_type": benefit.benefit_type,
            "benefit_value": float(benefit.benefit_value),
            "conditions": benefit.conditions
        }
        for benefit in benefits
    ]


@app.delete("/cards/{card_id}")
def delete_card(
    card_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(
        Card.card_id == card_id,
        Card.user_id == current_user.user_id
    ).first()

    if not card:
        raise HTTPException(
            status_code=404,
            detail="Card not found"
        )

    # Clean up card usage and card benefits for this card
    db.query(CardUsage).filter(CardUsage.card_id == card_id).delete()
    db.query(CardBenefit).filter(CardBenefit.card_id == card_id).delete()
    db.delete(card)

    audit = AuditLog(
        user_id=current_user.user_id,
        action="DELETE_CARD",
        entity_type="CARD",
        entity_id=card_id
    )
    db.add(audit)
    db.commit()

    return {"message": "Card deleted successfully"}


@app.post("/cards/{card_id}/usage")
def add_card_usage(
    card_id: int,
    usage_data: CardUsageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(
        Card.card_id == card_id,
        Card.user_id == current_user.user_id
    ).first()

    if not card:
        raise HTTPException(
            status_code=404,
            detail="Card not found"
        )

    expense = db.query(Expense).filter(
        Expense.expense_id == usage_data.expense_id,
        Expense.user_id == current_user.user_id
    ).first()
    if not expense:
        raise HTTPException(
            status_code=404,
            detail="Expense not found or does not belong to user"
        )

    if usage_data.benefit_received is not None and usage_data.benefit_received < 0:
        raise HTTPException(
            status_code=400,
            detail="Benefit received cannot be negative"
        )

    usage = CardUsage(
        card_id=card_id,
        expense_id=usage_data.expense_id,
        benefit_received=usage_data.benefit_received
    )
    db.add(usage)
    db.commit()
    db.refresh(usage)

    audit = AuditLog(
        user_id=current_user.user_id,
        action="CREATE_CARD_USAGE",
        entity_type="CARD_USAGE",
        entity_id=usage.usage_id
    )
    db.add(audit)
    db.commit()

    return {
        "message": "Card usage recorded successfully",
        "usage_id": usage.usage_id,
        "card_id": usage.card_id,
        "expense_id": usage.expense_id,
        "benefit_received": float(usage.benefit_received) if usage.benefit_received is not None else None,
        "used_at": usage.used_at
    }


@app.get("/cards/{card_id}/usage")
def get_card_usage_for_card(
    card_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(
        Card.card_id == card_id,
        Card.user_id == current_user.user_id
    ).first()

    if not card:
        raise HTTPException(
            status_code=404,
            detail="Card not found"
        )

    usages = db.query(CardUsage).filter(
        CardUsage.card_id == card_id
    ).order_by(CardUsage.used_at.desc()).all()

    result = []
    for u in usages:
        expense_info = None
        if u.expense_id:
            exp = db.query(Expense).filter(Expense.expense_id == u.expense_id).first()
            if exp:
                expense_info = {
                    "expense_id": exp.expense_id,
                    "amount": float(exp.amount),
                    "category": exp.category,
                    "merchant": exp.merchant,
                    "expense_date": str(exp.expense_date)
                }
        result.append({
            "usage_id": u.usage_id,
            "card_id": u.card_id,
            "card_name": card.card_name,
            "expense_id": u.expense_id,
            "expense": expense_info,
            "benefit_received": float(u.benefit_received) if u.benefit_received is not None else None,
            "used_at": u.used_at
        })

    return result


@app.get("/cards-usage")
def get_all_card_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    usages = (
        db.query(CardUsage, Card)
        .join(Card, Card.card_id == CardUsage.card_id)
        .filter(Card.user_id == current_user.user_id)
        .order_by(CardUsage.used_at.desc())
        .all()
    )

    result = []
    for u, c in usages:
        expense_info = None
        if u.expense_id:
            exp = db.query(Expense).filter(Expense.expense_id == u.expense_id).first()
            if exp:
                expense_info = {
                    "expense_id": exp.expense_id,
                    "amount": float(exp.amount),
                    "category": exp.category,
                    "merchant": exp.merchant,
                    "expense_date": str(exp.expense_date)
                }
        result.append({
            "usage_id": u.usage_id,
            "card_id": u.card_id,
            "card_name": c.card_name,
            "issuer": c.issuer,
            "last_four_digits": c.last_four_digits,
            "expense_id": u.expense_id,
            "expense": expense_info,
            "benefit_received": float(u.benefit_received) if u.benefit_received is not None else None,
            "used_at": u.used_at
        })

    return result


@app.get("/cards-recommendations")
def get_card_recommendations(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Retrieve user's cards
    user_cards = db.query(Card).filter(Card.user_id == current_user.user_id).all()
    if not user_cards:
        return {
            "has_cards": False,
            "message": "No cards registered. Please add credit/debit cards and benefits to view recommendations.",
            "recommendations": []
        }

    card_ids = [c.card_id for c in user_cards]
    card_map = {c.card_id: c for c in user_cards}

    # Retrieve all benefits for user's cards
    benefits = db.query(CardBenefit).filter(CardBenefit.card_id.in_(card_ids)).all()
    if not benefits:
        return {
            "has_cards": True,
            "message": "You have cards registered, but no benefits configured yet. Add benefits to receive tailored card recommendations.",
            "recommendations": []
        }

    # Historical expenses to correlate with spending habits
    expenses = db.query(
        Expense.category,
        func.sum(Expense.amount).label("total_spent"),
        func.count(Expense.expense_id).label("txn_count")
    ).filter(
        Expense.user_id == current_user.user_id
    ).group_by(
        Expense.category
    ).all()

    spending_by_category = {
        e.category.strip().lower(): {
            "category_name": e.category,
            "total_spent": float(e.total_spent),
            "txn_count": int(e.txn_count)
        }
        for e in expenses
    }

    if category and category.strip():
        target_categories = [category.strip()]
    else:
        # Combine categories from registered benefits and past expenses
        benefit_cats = {b.category.strip() for b in benefits}
        expense_cats = {e.category.strip() for e in expenses}
        target_categories = sorted(list(benefit_cats | expense_cats))

    recommendations = []
    for cat in target_categories:
        cat_lower = cat.strip().lower()
        matching_benefits = [
            b for b in benefits
            if b.category.strip().lower() == cat_lower or b.category.strip().lower() in ("all", "all spending", "general")
        ]

        if not matching_benefits:
            if category:
                recommendations.append({
                    "category": cat,
                    "has_benefit": False,
                    "explanation": f"No specific registered card benefits found for '{cat}'. Check your card terms or register a benefit.",
                    "best_card": None,
                    "matching_cards": []
                })
            continue

        matching_benefits.sort(key=lambda b: float(b.benefit_value), reverse=True)
        top_benefit = matching_benefits[0]
        best_card = card_map.get(top_benefit.card_id)

        matching_cards_list = []
        for b in matching_benefits:
            c = card_map.get(b.card_id)
            if c:
                matching_cards_list.append({
                    "card_id": c.card_id,
                    "card_name": c.card_name,
                    "issuer": c.issuer,
                    "card_type": c.card_type,
                    "last_four_digits": c.last_four_digits,
                    "benefit_id": b.benefit_id,
                    "benefit_type": b.benefit_type,
                    "benefit_value": float(b.benefit_value),
                    "conditions": b.conditions
                })

        spent_info = spending_by_category.get(cat_lower, {"total_spent": 0.0, "txn_count": 0})

        explanation = (
            f"Recommended '{best_card.card_name}' ({best_card.issuer}) offering {float(top_benefit.benefit_value)} "
            f"{top_benefit.benefit_type} on '{top_benefit.category}'. "
            f"Conditions: {top_benefit.conditions or 'None specified'}. "
            f"(Note: Recommendations depend strictly on your registered card benefit data; verify bank terms)."
        )

        recommendations.append({
            "category": cat,
            "has_benefit": True,
            "best_card": {
                "card_id": best_card.card_id,
                "card_name": best_card.card_name,
                "issuer": best_card.issuer,
                "card_type": best_card.card_type,
                "last_four_digits": best_card.last_four_digits,
                "benefit_id": top_benefit.benefit_id,
                "benefit_type": top_benefit.benefit_type,
                "benefit_value": float(top_benefit.benefit_value),
                "conditions": top_benefit.conditions
            },
            "historical_spending": spent_info["total_spent"],
            "transaction_count": spent_info["txn_count"],
            "explanation": explanation,
            "matching_cards": matching_cards_list
        })

    recommendations.sort(key=lambda r: r.get("historical_spending", 0.0), reverse=True)

    return {
        "has_cards": True,
        "message": "Recommendations generated based on your registered card benefits and recorded spending.",
        "recommendations": recommendations
    }


# ==========================================
# PHASE 4: FINANCIAL REPORTS ENDPOINTS
# ==========================================

@app.get("/reports/financial-summary")
def get_financial_report_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Direct Income
    income_query = db.query(Income).filter(Income.user_id == current_user.user_id)
    if start_date:
        income_query = income_query.filter(Income.income_date >= start_date)
    if end_date:
        income_query = income_query.filter(Income.income_date <= end_date)
    incomes = income_query.all()
    total_income = sum(Decimal(str(i.amount)) for i in incomes)

    # 2. Direct Expenses
    expense_query = db.query(Expense).filter(Expense.user_id == current_user.user_id)
    if start_date:
        expense_query = expense_query.filter(Expense.expense_date >= start_date)
    if end_date:
        expense_query = expense_query.filter(Expense.expense_date <= end_date)
    expenses = expense_query.all()
    total_expenses = sum(Decimal(str(e.amount)) for e in expenses)

    # Category breakdown for direct expenses
    category_totals = {}
    for e in expenses:
        cat = e.category.strip()
        amt = Decimal(str(e.amount))
        category_totals[cat] = category_totals.get(cat, Decimal("0.00")) + amt

    category_breakdown = [
        {
            "category": cat,
            "amount": float(amt),
            "percentage": float(round((amt / total_expenses * 100), 2)) if total_expenses > 0 else 0.0
        }
        for cat, amt in sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    ]

    # 3. Split Bills: Personal assigned shares (user as participant)
    # This prevents counting other participants' shares
    user_shares_query = (
        db.query(SplitParticipant, SplitBill)
        .join(SplitBill, SplitBill.split_bill_id == SplitParticipant.split_bill_id)
        .filter(SplitParticipant.user_id == current_user.user_id)
    )
    if start_date:
        user_shares_query = user_shares_query.filter(SplitBill.bill_date >= start_date)
    if end_date:
        user_shares_query = user_shares_query.filter(SplitBill.bill_date <= end_date)
    user_shares = user_shares_query.all()

    total_split_shares = sum(Decimal(str(p.share_amount)) for p, _ in user_shares)
    total_split_paid = sum(Decimal(str(p.amount_paid or 0)) for p, _ in user_shares)
    total_split_outstanding = total_split_shares - total_split_paid

    # 4. Split Bills created by user (bills where user is creditor)
    created_bills_query = db.query(SplitBill).filter(SplitBill.user_id == current_user.user_id)
    if start_date:
        created_bills_query = created_bills_query.filter(SplitBill.bill_date >= start_date)
    if end_date:
        created_bills_query = created_bills_query.filter(SplitBill.bill_date <= end_date)
    created_bills = created_bills_query.all()
    total_bills_created_amount = sum(Decimal(str(b.total_amount)) for b in created_bills)

    # 5. Income Allocations (Planned vs Actual)
    allocations_query = db.query(IncomeAllocation).filter(IncomeAllocation.user_id == current_user.user_id)
    allocations = allocations_query.all()
    total_planned_allocations = sum(Decimal(str(a.planned_amount)) for a in allocations)
    total_completed_allocations = sum(Decimal(str(a.actual_amount or 0)) for a in allocations if a.status == "COMPLETED")
    pending_allocations_count = sum(1 for a in allocations if a.status == "PENDING")

    # 6. Card benefits received
    user_cards = db.query(Card).filter(Card.user_id == current_user.user_id).all()
    user_card_ids = [c.card_id for c in user_cards]
    total_benefits_received = Decimal("0.00")
    if user_card_ids:
        usages = db.query(CardUsage).filter(CardUsage.card_id.in_(user_card_ids)).all()
        total_benefits_received = sum(Decimal(str(u.benefit_received or 0)) for u in usages)

    # 7. Budgets vs Actuals
    budgets = db.query(Budget).filter(Budget.user_id == current_user.user_id).all()
    budget_comparison = []
    for b in budgets:
        # Sum expenses in this budget category and period
        exp_in_cat = sum(
            Decimal(str(e.amount))
            for e in expenses
            if e.category.strip().lower() == b.category.strip().lower()
            and (b.start_date <= e.expense_date <= b.end_date)
        )
        limit = Decimal(str(b.limit_amount))
        pct = float(round((exp_in_cat / limit * 100), 1)) if limit > 0 else 0.0
        budget_comparison.append({
            "category": b.category,
            "limit_amount": float(limit),
            "spent_amount": float(exp_in_cat),
            "remaining": float(limit - exp_in_cat),
            "percentage_used": pct,
            "period": b.period,
            "is_over_budget": exp_in_cat > limit
        })

    # Net Cash Flow & Savings Rate
    net_savings = total_income - total_expenses
    savings_rate = float(round((net_savings / total_income * 100), 2)) if total_income > 0 else 0.0

    return {
        "user_name": current_user.name,
        "filter": {
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None
        },
        "summary": {
            "total_income": float(total_income),
            "total_direct_expenses": float(total_expenses),
            "net_savings": float(net_savings),
            "savings_rate_percent": savings_rate,
            "split_bill_personal_share": float(total_split_shares),
            "split_bill_share_paid": float(total_split_paid),
            "split_bill_share_outstanding": float(total_split_outstanding),
            "total_bills_created_amount": float(total_bills_created_amount),
            "total_planned_allocations": float(total_planned_allocations),
            "total_completed_allocations": float(total_completed_allocations),
            "pending_allocations_count": pending_allocations_count,
            "total_card_benefits_received": float(total_benefits_received)
        },
        "category_breakdown": category_breakdown,
        "budget_performance": budget_comparison
    }


# ==========================================
# PHASE 5: AI FINANCE ASSISTANT ENDPOINT
# ==========================================

@app.post("/ai-assistant/query")
def ai_assistant_query(
    request: AIAssistantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = request.query.strip().lower()

    # Collect authorized user metrics safely
    incomes = db.query(Income).filter(Income.user_id == current_user.user_id).all()
    expenses = db.query(Expense).filter(Expense.user_id == current_user.user_id).all()
    budgets = db.query(Budget).filter(Budget.user_id == current_user.user_id).all()
    cards = db.query(Card).filter(Card.user_id == current_user.user_id).all()
    card_ids = [c.card_id for c in cards]
    benefits = db.query(CardBenefit).filter(CardBenefit.card_id.in_(card_ids)).all() if card_ids else []

    total_income = sum(float(i.amount) for i in incomes)
    total_expenses = sum(float(e.amount) for e in expenses)
    net_balance = total_income - total_expenses
    savings_rate = (net_balance / total_income * 100) if total_income > 0 else 0.0

    # Category totals
    cat_totals = {}
    for e in expenses:
        cat = e.category.strip()
        cat_totals[cat] = cat_totals.get(cat, 0.0) + float(e.amount)
    sorted_cats = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)

    # Budget warnings
    over_budget_items = []
    for b in budgets:
        spent = sum(float(e.amount) for e in expenses if e.category.strip().lower() == b.category.strip().lower() and b.start_date <= e.expense_date <= b.end_date)
        limit = float(b.limit_amount)
        if spent > limit:
            over_budget_items.append((b.category, spent, limit, spent - limit))

    # Pattern recognition for response generation
    disclaimer = "\n\n*Disclaimer: This response is generated automatically from your authorized personal finance data and is for informational guidance only. Not financial or legal advice.*"

    if any(k in query for k in ["spend", "expense", "cost", "where", "category"]):
        if not sorted_cats:
            answer = f"You currently have no recorded expenses. Your total recorded income is ₹{total_income:,.2f}."
        else:
            top_3 = sorted_cats[:3]
            top_str = "\n".join([f"- **{cat}**: ₹{amt:,.2f} ({(amt/total_expenses*100):.1f}% of total expenses)" for cat, amt in top_3])
            answer = (
                f"### Spending Analysis\n\n"
                f"Your total recorded expenditure is **₹{total_expenses:,.2f}** across {len(expenses)} transactions.\n\n"
                f"**Your Top Expense Categories:**\n{top_str}\n\n"
                f"💡 **Recommendation:** Focus on optimizing spending in **{sorted_cats[0][0]}** as it represents your single largest cash outflow."
            )

    elif any(k in query for k in ["budget", "limit", "alert", "health", "over"]):
        if not budgets:
            answer = "You haven't set up any category budgets yet. Creating budgets for your recurring categories like Dining or Shopping helps protect your savings rate."
        elif over_budget_items:
            warnings_str = "\n".join([f"- ⚠️ **{cat}**: Spent ₹{spent:,.2f} against limit ₹{limit:,.2f} (Exceeded by ₹{diff:,.2f})" for cat, spent, limit, diff in over_budget_items])
            answer = (
                f"### ⚠️ Budget Health Alert\n\n"
                f"You have **{len(over_budget_items)} category budget(s)** currently exceeding their configured limits:\n\n"
                f"{warnings_str}\n\n"
                f"💡 **Action Required:** Pause discretionary expenses in these categories until the next budget cycle begins."
            )
        else:
            answer = (
                f"### ✅ All Budgets On Track\n\n"
                f"Great job! None of your **{len(budgets)} active category budgets** are currently exceeding their limits.\n"
                f"Your total budgeted allowance is healthy and remaining balances are intact."
            )

    elif any(k in query for k in ["card", "benefit", "reward", "cashback", "points"]):
        if not cards:
            answer = "You have not registered any cards yet. Go to the Cards section to register your credit/debit cards and enter their rewards/cashback terms to receive tailored card recommendations."
        elif not benefits:
            answer = f"You have {len(cards)} card(s) saved, but no reward benefits registered yet. Add benefit rules (e.g. 5% cashback on dining) to receive optimal card usage recommendations."
        else:
            best_benefits = sorted(benefits, key=lambda b: float(b.benefit_value), reverse=True)[:3]
            card_map = {c.card_id: c.card_name for c in cards}
            rec_str = "\n".join([f"- **{b.category}**: Use **{card_map.get(b.card_id, 'Card')}** for **{float(b.benefit_value)} {b.benefit_type}** ({b.conditions or 'Standard'})" for b in best_benefits])
            answer = (
                f"### 💳 Top Card Recommendations\n\n"
                f"Here are your highest-value registered card benefits:\n\n{rec_str}\n\n"
                f"💡 Make sure to choose the matching card at checkout to maximize cashbacks and rewards."
            )

    elif any(k in query for k in ["save", "saving", "rate", "invest", "50/30/20"]):
        answer = (
            f"### 📈 Savings Rate & Strategy\n\n"
            f"- **Total Income:** ₹{total_income:,.2f}\n"
            f"- **Total Expenses:** ₹{total_expenses:,.2f}\n"
            f"- **Net Savings:** ₹{net_balance:,.2f}\n"
            f"- **Current Savings Rate:** **{savings_rate:.1f}%**\n\n"
            f"💡 **Benchmark:** Financial experts recommend targeting at least a **20% savings rate** (under the 50/30/20 rule). "
            + ("You are beating this target! Consider allocating surplus funds into targeted goals." if savings_rate >= 20 else "Consider trimming non-essential subscriptions and high-cost categories to increase your monthly savings rate to 20%.")
        )

    else:
        # Comprehensive overview
        answer = (
            f"### 📊 Financial Snapshot for {current_user.name}\n\n"
            f"- **Net Balance:** ₹{net_balance:,.2f} (Income: ₹{total_income:,.2f} | Expenses: ₹{total_expenses:,.2f})\n"
            f"- **Savings Rate:** {savings_rate:.1f}%\n"
            f"- **Active Budgets:** {len(budgets)} ({len(over_budget_items)} exceeding limit)\n"
            f"- **Registered Cards:** {len(cards)}\n\n"
            f"You can ask me specific questions like:\n"
            f"- *'Where am I spending the most?'*\n"
            f"- *'How is my budget health?'*\n"
            f"- *'Which card gives the best rewards?'*\n"
            f"- *'How can I improve my savings rate?'*"
        )

    return {
        "query": request.query,
        "response": answer + disclaimer
    }


# ==========================================
# PHASE 6: ANDROID BANK SMS TRANSACTION DETECTION
# ==========================================

@app.post("/sms/parse")
def parse_bank_sms(
    request: SMSParseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    text = request.sms_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="SMS content cannot be empty")

    text_lower = text.lower()

    # 0. Check for OTP / security verification messages
    otp_indicators = ["otp", "one time password", "verification code", "security code"]
    if any(k in text_lower for k in otp_indicators) and any(k in text_lower for k in ["do not share", "valid for", "is your otp", "secret", "never share"]):
        raise HTTPException(
            status_code=422,
            detail="Message identified as an OTP or security verification request. Only completed transaction alerts can be imported."
        )

    # 0b. Check for promotional / marketing offers
    promo_indicators = ["use code", "coupon code", "promo code", "flat off", "cashback up to", "win up to", "hurry", "offer valid till", "apply code", "claim your prize"]
    confirmed_tx_indicators = ["debited", "credited", "spent", "charged", "withdrawn", "deposited", "paid to", "sent to", "received from"]
    if any(k in text_lower for k in promo_indicators) and not any(k in text_lower for k in confirmed_tx_indicators):
        raise HTTPException(
            status_code=422,
            detail="Message appears to be a promotional offer or marketing campaign, not a completed transaction alert."
        )

    # 1. Determine direction (DEBIT/EXPENSE vs CREDIT/INCOME)
    debit_keywords = ["debited", "spent", "paid", "sent", "withdrawn", "purchase", "transferred to", "txn", "dr", "charged"]
    credit_keywords = ["credited", "received", "deposited", "added to", "refund", "salary", "cr"]

    has_debit = any(k in text_lower for k in debit_keywords)
    has_credit = any(k in text_lower for k in credit_keywords)

    if not has_debit and not has_credit:
        raise HTTPException(
            status_code=422,
            detail="Could not identify transaction direction (Debit or Credit). Please provide an authentic bank transaction SMS alert."
        )

    is_credit = has_credit and not any(k in text_lower for k in ["debited", "paid to", "sent to", "charged"])
    txn_type = "INCOME" if is_credit else "EXPENSE"

    # 2. Extract Amount
    # Matches: Rs. 500, Rs 500.00, INR 1,200.50, ₹ 250
    amount_match = re.search(r'(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d{1,2})?)', text, re.IGNORECASE)
    if not amount_match:
        # Fallback: look for numbers followed by INR/Rs
        amount_match = re.search(r'([\d,]+(?:\.\d{1,2})?)\s*(?:rs|inr|₹)', text, re.IGNORECASE)

    extracted_amount = None
    if amount_match:
        amt_str = amount_match.group(1).replace(",", "")
        try:
            extracted_amount = float(Decimal(amt_str))
        except Exception:
            extracted_amount = None

    if not extracted_amount:
        raise HTTPException(
            status_code=422,
            detail="Could not detect a valid transaction amount from the SMS message. Please verify the format."
        )

    # 3. Extract Merchant / Beneficiary
    merchant = None
    merchant_patterns = [
        r'(?:at|to|info|towards|for|vpa)\s+([A-Za-z0-9\s\.\-_&]{2,30}?)(?:\s+(?:on|using|via|ref|txn|avl|avbl|bal|a/c|\.|\,))',
        r'paid\s+to\s+([A-Za-z0-9\s\.\-_&]{2,30})',
        r'sent\s+to\s+([A-Za-z0-9\s\.\-_&]{2,30})'
    ]
    for pattern in merchant_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            # Clean up common false positive words
            if candidate.lower() not in ["your", "a/c", "account", "bank", "the"]:
                merchant = candidate
                break

    if not merchant:
        merchant = "UPI / Bank Transfer" if "upi" in text_lower else "Bank Transaction"

    # 4. Extract Date
    txn_date = date.today()
    date_match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', text)
    if date_match:
        try:
            d, m, y = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
            if y < 100:
                y += 2000
            txn_date = date(y, m, d)
        except Exception:
            txn_date = date.today()

    # 5. Extract Payment Method
    payment_method = "UPI"
    if "card" in text_lower or "ending" in text_lower:
        payment_method = "CARD"
    elif "netbanking" in text_lower or "imps" in text_lower or "neft" in text_lower:
        payment_method = "NETBANKING"
    elif "atm" in text_lower:
        payment_method = "ATM"

    # 6. Suggest Category
    suggested_category = "General"
    m_lower = merchant.lower()
    if any(k in m_lower or k in text_lower for k in ["swiggy", "zomato", "mcdonald", "starbucks", "kfc", "restaurant", "food", "cafe", "dine"]):
        suggested_category = "Food & Dining"
    elif any(k in m_lower or k in text_lower for k in ["uber", "ola", "metro", "petrol", "fuel", "indianoil", "hpcl", "bpcl", "rail", "irctc"]):
        suggested_category = "Transportation"
    elif any(k in m_lower or k in text_lower for k in ["amazon", "flipkart", "myntra", "zara", "store", "mart", "supermarket", "retail"]):
        suggested_category = "Shopping"
    elif any(k in m_lower or k in text_lower for k in ["netflix", "spotify", "prime", "hotstar", "cinema", "movie", "bookmyshow"]):
        suggested_category = "Entertainment"
    elif any(k in m_lower or k in text_lower for k in ["electricity", "bescom", "water", "wifi", "airtel", "jio", "broadband", "bill"]):
        suggested_category = "Utilities"
    elif any(k in m_lower or k in text_lower for k in ["hospital", "pharmacy", "apollo", "medplus", "doctor", "health"]):
        suggested_category = "Healthcare"
    elif is_credit and any(k in text_lower for k in ["salary", "payroll"]):
        suggested_category = "Salary"

    # 7. Idempotency & Duplicate Check
    # Check if a transaction with the identical amount and date already exists for this user
    is_duplicate = False
    duplicate_info = None

    if txn_type == "EXPENSE":
        existing = db.query(Expense).filter(
            Expense.user_id == current_user.user_id,
            Expense.amount == extracted_amount,
            Expense.expense_date == txn_date
        ).first()
        if existing:
            is_duplicate = True
            duplicate_info = f"Existing expense found: ₹{existing.amount} for '{existing.merchant or existing.category}' on {existing.expense_date}"
    else:
        existing = db.query(Income).filter(
            Income.user_id == current_user.user_id,
            Income.amount == extracted_amount,
            Income.income_date == txn_date
        ).first()
        if existing:
            is_duplicate = True
            duplicate_info = f"Existing income found: ₹{existing.amount} from '{existing.source}' on {existing.income_date}"

    return {
        "status": "success",
        "parsed_data": {
            "transaction_type": txn_type,
            "amount": extracted_amount,
            "merchant": merchant,
            "category": suggested_category,
            "transaction_date": str(txn_date),
            "payment_method": payment_method,
            "description": f"SMS: {text[:60]}..."
        },
        "is_duplicate": is_duplicate,
        "duplicate_warning": duplicate_info,
        "confidence": 0.95 if amount_match and merchant else 0.80
    }


@app.post("/sms/confirm")
def confirm_bank_sms_transaction(
    request: SMSConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")

    if request.transaction_type == "EXPENSE":
        new_expense = Expense(
            user_id=current_user.user_id,
            amount=request.amount,
            category=request.category_or_source,
            merchant=request.merchant,
            expense_date=request.transaction_date,
            description=request.description or "Imported via Bank SMS",
            payment_method=request.payment_method or "SMS",
            source="SMS"
        )
        db.add(new_expense)
        db.commit()
        db.refresh(new_expense)

        audit = AuditLog(
            user_id=current_user.user_id,
            action="CREATE_EXPENSE_FROM_SMS",
            entity_type="EXPENSE",
            entity_id=new_expense.expense_id
        )
        db.add(audit)
        db.commit()

        create_system_notification(
            db,
            current_user.user_id,
            "Bank Expense Imported",
            f"Successfully imported expense of ₹{new_expense.amount} for {new_expense.merchant or new_expense.category}.",
            "SMS"
        )

        return {
            "message": "Expense transaction successfully recorded from SMS",
            "transaction_id": new_expense.expense_id,
            "type": "EXPENSE",
            "amount": float(new_expense.amount),
            "category": new_expense.category,
            "merchant": new_expense.merchant,
            "date": str(new_expense.expense_date)
        }
    else:
        new_income = Income(
            user_id=current_user.user_id,
            amount=request.amount,
            source=request.category_or_source,
            income_date=request.transaction_date,
            description=request.description or "Imported via Bank SMS",
            source_type="SMS"
        )
        db.add(new_income)
        db.commit()
        db.refresh(new_income)

        audit = AuditLog(
            user_id=current_user.user_id,
            action="CREATE_INCOME_FROM_SMS",
            entity_type="INCOME",
            entity_id=new_income.income_id
        )
        db.add(audit)
        db.commit()

        create_system_notification(
            db,
            current_user.user_id,
            "Bank Income Imported",
            f"Successfully imported income of ₹{new_income.amount} from {new_income.source}.",
            "SMS"
        )

        return {
            "message": "Income transaction successfully recorded from SMS",
            "transaction_id": new_income.income_id,
            "type": "INCOME",
            "amount": float(new_income.amount),
            "source": new_income.source,
            "date": str(new_income.income_date)
        }


# ============================================================================
# NOTIFICATIONS API (MODULE I)
# ============================================================================

@app.get("/notifications", response_model=List[NotificationResponse])
def get_user_notifications(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Notification).filter(
        Notification.user_id == current_user.user_id
    ).order_by(
        Notification.created_at.desc(),
        Notification.notification_id.desc()
    ).limit(limit).all()


@app.get("/notifications/unread-count")
def get_unread_notification_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    count = db.query(Notification).filter(
        Notification.user_id == current_user.user_id,
        Notification.is_read == 0
    ).count()
    return {"unread_count": count}


@app.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    notif = db.query(Notification).filter(
        Notification.notification_id == notification_id,
        Notification.user_id == current_user.user_id
    ).first()

    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = 1
    db.commit()
    db.refresh(notif)
    return notif


@app.post("/notifications/mark-all-read")
def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    unread = db.query(Notification).filter(
        Notification.user_id == current_user.user_id,
        Notification.is_read == 0
    ).all()

    for n in unread:
        n.is_read = 1

    db.commit()
    return {
        "message": "All notifications marked as read",
        "marked_count": len(unread)
    }


