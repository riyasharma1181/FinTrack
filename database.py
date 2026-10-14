from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import make_url, URL
from dotenv import load_dotenv
import urllib.parse
import os

load_dotenv()


def resolve_database_url() -> URL:
    """
    Resolve and safely parse the database connection URL.
    
    Priority:
    1. DATABASE_URL environment variable (PostgreSQL / Supabase / Render).
    2. Legacy individual MySQL environment variables (DB_USER, DB_PASSWORD, etc.).
    
    Handles:
    - Special characters in passwords (e.g. '@', ':', '#', '%').
    - Scheme normalization ('postgres://' and 'postgresql://' -> 'postgresql+psycopg://').
    - Enforcing 'sslmode=require' for remote PostgreSQL hosts.
    - Fallback to local MySQL.
    """
    raw_url = os.getenv("DATABASE_URL", "").strip()

    if raw_url:
        # Normalize schemes for SQLAlchemy 2.0 + psycopg v3
        if raw_url.startswith("postgres://"):
            raw_url = "postgresql+psycopg://" + raw_url[len("postgres://"):]
        elif raw_url.startswith("postgresql://"):
            raw_url = "postgresql+psycopg://" + raw_url[len("postgresql://"):]
        elif raw_url.startswith("mysql://"):
            raw_url = "mysql+pymysql://" + raw_url[len("mysql://"):]

        try:
            url_obj = make_url(raw_url)
            # If make_url didn't split on an unencoded '@' inside the password:
            if not (url_obj.host and "@" in url_obj.host):
                if url_obj.drivername.startswith("postgresql") and url_obj.host not in ("localhost", "127.0.0.1"):
                    query = dict(url_obj.query)
                    if "sslmode" not in query:
                        query["sslmode"] = "require"
                        url_obj = url_obj.set(query=query)
                return url_obj
        except Exception:
            pass

        # Robust fallback parser for unencoded special characters in password
        try:
            scheme_part, rest = raw_url.split("://", 1)
            path_split = rest.rsplit("/", 1)
            if len(path_split) == 2:
                host_user_part, db_query = path_split
                db_split = db_query.split("?", 1)
                database = db_split[0]
                query = urllib.parse.parse_qs(db_split[1]) if len(db_split) > 1 else {}
            else:
                host_user_part = rest
                database = ""
                query = {}

            user_pass_part, host_port = host_user_part.rsplit("@", 1)
            if ":" in host_port:
                host, port_str = host_port.split(":", 1)
                port = int(port_str) if port_str.isdigit() else None
            else:
                host = host_port
                port = None

            if ":" in user_pass_part:
                username, password = user_pass_part.split(":", 1)
                password = urllib.parse.unquote(password)
                username = urllib.parse.unquote(username)
            else:
                username = urllib.parse.unquote(user_pass_part)
                password = None

            flat_query = {k: v[0] if len(v) == 1 else v for k, v in query.items()}
            if scheme_part.startswith("postgresql") and host not in ("localhost", "127.0.0.1"):
                if "sslmode" not in flat_query:
                    flat_query["sslmode"] = "require"

            return URL.create(
                drivername=scheme_part,
                username=username,
                password=password,
                host=host,
                port=port,
                database=database,
                query=flat_query if flat_query else None
            )
        except Exception as e:
            raise ValueError(f"Failed to safely parse DATABASE_URL: {e}")

    # Fallback to local MySQL environment variables
    db_user = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "3306"))
    db_name = os.getenv("DB_NAME", "fintrack")

    return URL.create(
        drivername="mysql+pymysql",
        username=db_user,
        password=db_password,
        host=db_host,
        port=db_port,
        database=db_name
    )


DATABASE_URL_OBJ = resolve_database_url()
DATABASE_URL = DATABASE_URL_OBJ.render_as_string(hide_password=False)

# Configure engine with connection health checks & recycling for poolers
engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "echo": os.getenv("SQL_ECHO", "false").lower() in ("true", "1")
}

engine = create_engine(DATABASE_URL_OBJ, **engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine=None):
    """
    Idempotent and non-destructive table initialization.
    Creates missing tables without altering or dropping existing data.
    """
    eng = target_engine or engine
    import models
    models.Base.metadata.create_all(bind=eng, checkfirst=True)