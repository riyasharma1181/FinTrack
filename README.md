# FinTrack – Personal Finance & Budget Management System

FinTrack is a web-based personal finance management application developed using Python and Flask. It helps users manage their income and expenses, monitor their balance, set category-wise budgets, and analyze their spending patterns through interactive visualizations.

## Features

- Add and manage expenses
- Record income
- Calculate total income and total expenses
- Automatically calculate available balance
- Identify the top spending category
- View recent transactions
- Analyze monthly spending
- Visualize spending using interactive charts
- Set category-wise budgets
- Compare budgeted amount with actual spending
- Calculate remaining budget
- Calculate budget utilization percentage
- Display warnings when spending approaches or exceeds the budget limit
- Store financial data using SQLite

## Technology Stack

- **Python**
- **Flask**
- **SQLite**
- **HTML5**
- **CSS3**
- **JavaScript**
- **Chart.js**

## Project Structure

```text
personal-expense-tracker/
│
├── src/
│   ├── app.py
│   │
│   ├── templates/
│   │   ├── index.html
│   │   ├── add.html
│   │   ├── income.html
│   │   ├── budget.html
│   │   ├── monthly.html
│   │   └── recent.html
│   │
│   └── static/
│       ├── script.js
│       ├── styles.css
│       └── images/
│
├── README.md
├── requirements.txt
└── .gitignore

Main Modules

1. Dashboard
The dashboard provides a financial overview including:

Total Income
Total Expenses
Balance
Top Spending Category
Budget Overview
Spending Analytics


2. Expense Management
Users can record expenses with:

Date
Business / merchant
Amount
Category
Description
Optional receipt image


3. Income Management
Users can record:

Date
Income source
Amount
Description

The dashboard automatically calculates total income from the stored records.

4. Budget Management
Users can set a spending limit for individual categories.

For each budget, FinTrack calculates:

Budget Amount
Actual Spending
Remaining Budget
Percentage Used

The system also provides warnings when:

Spending reaches 80% of the budget
Spending exceeds the budget


5. Spending Analytics
FinTrack provides visual analysis of spending using Chart.js, including:

Monthly spending trends
Category-wise spending distribution
Pie charts
Spending summaries
How It Works

FinTrack uses Flask as the backend and SQLite as the database.

User
  ↓
Web Interface
  ↓
Flask Backend
  ↓
SQLite Database
  ↓
Data Processing
  ↓
Dashboard & Analytics


Balance Calculation
Balance = Total Income - Total Expenses
Budget Utilization
Budget Used (%) = (Actual Spending / Budget Amount) × 100


Installation
1. Clone the Repository
git clone https://github.com/riyasharma1181/FinTrack.git
2. Open the Project
cd FinTrack
3. Open the Source Directory
cd src
4. Create a Virtual Environment
python -m venv venv

5. Activate the Virtual Environment

For Windows PowerShell:

.\venv\Scripts\Activate.ps1

If PowerShell blocks script execution, you can run the application directly using:

.\venv\Scripts\python.exe app.py
6. Install Dependencies
pip install -r ../requirements.txt
7. Run the Application
python app.py

Open the application in your browser:

http://127.0.0.1:5000



Database

FinTrack uses SQLite for local data storage.

The database is automatically initialized when the application starts.

The database contains tables for:

Expenses
Income
Budgets

The local database file is excluded from GitHub using .gitignore.

Future Improvements

Possible future improvements include:

User authentication
Export financial reports
Recurring transactions
Advanced spending trend analysis
Improved mobile responsiveness
Cloud database integration
Deployment to a production server


Author
Riya Sharma

GitHub: https://github.com/riyasharma1181


