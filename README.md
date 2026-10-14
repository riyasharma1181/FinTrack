# FinTrack — Personal Finance Management System

FinTrack is a personal finance and budget management web application developed as a Database Management System (DBMS) Project-Based Learning (PBL) project.

The application is designed to help users manage their financial information, including income, expenses, and budgets, through a web-based interface.

## Features

- **User Authentication:** Authentication-related functionality for users.
- **Income Management:** Organize and manage income records.
- **Expense Management:** Record and manage expense information.
- **Budget Management:** Manage budgets and monitor financial allocations.
- **Financial Dashboard:** Present financial information through a user interface.
- **Database Management:** Store and access application data using a relational database.
- **Database Connectivity:** Configurable database connection support through SQLAlchemy.

> Note: The available features depend on the functionality implemented in the project code.

## Technology Stack

### Frontend
- React
- Vite
- JavaScript
- HTML
- CSS

### Backend
- Python
- FastAPI
- Uvicorn

### Database and ORM
- SQLAlchemy
- MySQL support through PyMySQL
- PostgreSQL support through Psycopg

The database connection is configurable through environment variables. The default configuration in `database.py` falls back to MySQL when `DATABASE_URL` is not provided.

### Authentication and Validation
- bcrypt
- python-jose
- Pydantic
- email-validator

### Environment Configuration
- python-dotenv

## Project Structure

```text
FinTrack/
├── src/                    # Frontend source code
├── main.py                 # Backend application entry point
├── auth.py                 # Authentication-related functionality
├── database.py             # Database connection and session management
├── models.py               # Database models
├── schemas.py              # Data schemas and validation
├── migrate_to_postgres.py  # PostgreSQL migration utility
├── requirements.txt        # Python dependencies
├── test_suite.py           # Test suite
├── package.json            # Frontend dependencies and scripts
├── package-lock.json       # Locked frontend dependency versions
├── index.html              # Frontend HTML entry point
├── vite.config.js          # Vite configuration
├── eslint.config.js        # ESLint configuration
├── .gitignore              # Git ignore rules
└── README.md               # Project documentation
```

## Prerequisites

Before running the project, install the following:

- Python 3.10 or a compatible version supported by the dependencies
- Node.js and npm
- A configured MySQL or PostgreSQL database

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/riyasharma1181/FinTrack.git
cd FinTrack
```

### 2. Set Up the Backend

Create and activate a Python virtual environment.

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

### 3. Configure the Database

The database configuration is managed in `database.py`.

The application supports database connection settings through environment variables.

For the default MySQL configuration, the following variables are available:

```text
DB_USER=root
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=fintrack
```

Alternatively, configure `DATABASE_URL` with a valid connection URL for a supported database.

Place actual credentials in your local environment or an untracked `.env` file. Never commit real passwords, database credentials, or secret keys to GitHub.

Ensure the selected database exists and is accessible before starting the application.

### 4. Start the Backend

From the project root directory, run:

```bash
uvicorn main:app --reload
```

This command assumes that `main.py` defines the FastAPI application as `app`.

If the application uses a different variable name or startup configuration, adjust the command accordingly.

### 5. Set Up the Frontend

Open a second terminal in the directory containing the frontend's `package.json`.

Install the frontend dependencies:

```bash
npm install
```

Start the Vite development server:

```bash
npm run dev
```

Open the local address displayed in the terminal to access the frontend.

> If the frontend is located in a subdirectory, navigate to that directory before running the npm commands.

## Database Design

The project uses SQLAlchemy to define and manage database models.

The database layer provides:

- Database connection configuration
- SQLAlchemy engine creation
- Database session management
- Database table initialization using model metadata

The configured database determines where application data is stored.

## Testing

The repository includes `test_suite.py`, which contains project test code.

Run the tests using the command appropriate to the test framework and configuration used in the project.

Test results should be verified before claiming that all tests pass.

## Project Objective

The objective of FinTrack is to develop a web-based personal finance management system that organizes financial information and demonstrates the use of database concepts in a practical application.

The project combines a modern frontend, a Python backend, and relational database connectivity.

## Future Scope

Possible future improvements include:

- More detailed financial reports and visualizations
- Additional budget analysis features
- Improved financial insights
- Enhanced validation and error handling
- Expanded automated testing
- Additional database and deployment options

These are potential enhancements and may not be implemented in the current version.

## Repository

GitHub: https://github.com/riyasharma1181/FinTrack

---

**Project:** FinTrack — Personal Finance Management System  
**Project Type:** DBMS Project-Based Learning (PBL)
