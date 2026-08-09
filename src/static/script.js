document.addEventListener("DOMContentLoaded", () => {

  // ==========================================
  // SET TODAY'S DATE
  // ==========================================

  const today = new Date();

  const localDate =
    today.getFullYear() +
    "-" +
    String(today.getMonth() + 1).padStart(2, "0") +
    "-" +
    String(today.getDate()).padStart(2, "0");

  // Set default date for expense form
  let ele = document.getElementById("date");

  if (ele) {
    ele.value = localDate;
  }


  // ==========================================
  // GET ELEMENTS
  // ==========================================

  const form = document.getElementById("purchaseForm");
  const statusMessage = document.getElementById("statusMessage");
  const purchasesTable = document.getElementById("purchasesTable");
  const monthlyOverview = document.getElementById("monthlyOverview");
  const monthlySpendingChart =
    document.getElementById("monthlySpendingChart");

  const allTimeCategoriesChart =
    document.getElementById("allTimeCategoriesChart");


  // ==========================================
  // ADD EXPENSE
  // ==========================================

  form?.addEventListener("submit", async (e) => {

    e.preventDefault();

    const formData = new FormData();

    let tempDate = form.date.value;

    formData.append("date", form.date.value);

    formData.append(
      "business",
      form.business.value
    );

    formData.append(
      "amount",
      parseFloat(form.amount.value)
    );


    if (form.category.value === "Other") {

      formData.append(
        "category",
        form.customCategory.value
      );

    } else {

      formData.append(
        "category",
        form.category.value
      );

    }


    formData.append(
      "description",
      form.description.value
    );


    const photoFile = form.photo.files[0];

    if (photoFile) {

      formData.append(
        "photo",
        photoFile
      );

    }


    try {

      const response = await fetch("/add", {

        method: "POST",

        body: formData

      });


      const result = await response.json();


      if (result.success) {

        statusMessage.textContent =
          "Purchase added successfully!";

        form.reset();

        document.getElementById("date").value =
          tempDate;


        const customCategoryInput =
          document.getElementById("customCategory");


        if (customCategoryInput) {

          customCategoryInput.style.display =
            "none";

          customCategoryInput.required =
            false;

          customCategoryInput.value =
            "";

        }

      } else {

        statusMessage.textContent =
          "Error adding purchase.";

      }


    } catch (error) {

      console.error(
        "Error:",
        error
      );

      statusMessage.textContent =
        "An unexpected error occurred.";

    }

  });


  // ==========================================
  // RECENT PURCHASES TABLE
  // ==========================================

  if (purchasesTable) {

    fetch("/month-data")

      .then((response) =>
        response.json()
      )

      .then((purchases) => {

        const tbody =
          purchasesTable.querySelector("tbody");


        purchases.forEach((purchase) => {

          const row =
            document.createElement("tr");


          row.innerHTML = `

            <td>
              ${purchase.date}
            </td>

            <td>
              ${purchase.business}
            </td>

            <td>
              ${Number(purchase.amount).toFixed(2)}
            </td>

            <td>
              ${purchase.category}
            </td>

            <td>
              ${purchase.description || ""}
            </td>

            <td>

              ${
                purchase.photo

                  ? `<img
                      src="data:image/jpeg;base64,${purchase.photo}"
                      alt="Purchase Photo"
                      style="max-width: 100px; max-height: 100px;"
                    >`

                  : "No Photo"
              }

            </td>

          `;


          tbody.appendChild(row);

        });

      })

      .catch((error) => {

        console.error(
          "Error fetching purchases:",
          error
        );

      });

  }


  // ==========================================
  // MONTHLY OVERVIEW
  // ==========================================

  if (monthlyOverview) {

    fetch("/overview-data")

      .then((response) =>
        response.json()
      )

      .then((months) => {

        months.forEach((item) => {

          const div =
            document.createElement("div");

          div.className =
            "overview-item";


          const monthSpan =
            document.createElement("span");

          monthSpan.className =
            "month-name";

          monthSpan.textContent =
            getMonthName(item.month);


          const totalSpan =
            document.createElement("span");

          totalSpan.className =
            "total-amount";

          totalSpan.textContent =
            `Total: $${Number(item.total).toFixed(2)}`;


          // Pie chart container

          const chartContainer =
            document.createElement("div");

          chartContainer.className =
            "pie-chart-container";


          const canvas =
            document.createElement("canvas");

          canvas.className =
            "pie-chart";


          chartContainer.appendChild(
            canvas
          );


          div.appendChild(
            monthSpan
          );

          div.appendChild(
            totalSpan
          );

          div.appendChild(
            chartContainer
          );


          monthlyOverview.appendChild(
            div
          );


          // Monthly category data

          fetch(
            `/monthly-category-data?month=${item.month}`
          )

            .then((response) =>
              response.json()
            )

            .then((categorical_data) => {

              if (
                !Array.isArray(
                  categorical_data
                )
              ) {

                throw new Error(
                  "Expected an array but got something else"
                );

              }


              const categories =
                categorical_data.map(
                  (data) =>
                    data.category
                );


              const totals =
                categorical_data.map(
                  (data) =>
                    data.category_amount
                );


              const categoryColors = {

                Restaurants:
                  "#FF5733",

                "Furniture/Home":
                  "#33FF57",

                "Gas/Car":
                  "#3357FF",

                Clothes:
                  "#FF33A1",

                "School/Office Supplies":
                  "#FF8C33",

                Misc:
                  "#33FFF5",

                Groceries:
                  "#8C33FF"

              };


              const defaultColor =
                "grey";


              const backgroundColors =
                categories.map(
                  (category) => {

                    return (
                      categoryColors[
                        category
                      ] ||
                      defaultColor
                    );

                  }
                );


              // Create monthly pie chart

              new Chart(canvas, {

                type: "pie",

                data: {

                  labels:
                    categories,

                  datasets: [

                    {

                      data:
                        totals,

                      backgroundColor:
                        backgroundColors

                    }

                  ]

                },


                options: {

                  responsive: true,

                  maintainAspectRatio:
                    false

                }

              });

            })


            .catch((error) => {

              console.error(
                "Error fetching monthly category data:",
                error
              );

            });

        });

      })


      .catch((error) => {

        console.error(
          "Error fetching monthly overview data:",
          error
        );

      });

  }


  // ==========================================
  // MONTHLY SPENDING LINE CHART
  // ==========================================

  if (monthlySpendingChart) {

    fetch("/overview-data?sort=ASC")

      .then((response) =>
        response.json()
      )

      .then((data) => {

        const ctx =
          document
            .getElementById(
              "monthlySpendingChart"
            )
            .getContext("2d");


        new Chart(ctx, {

          type: "line",


          data: {

            labels:
              data.map(
                (item) =>
                  getMonthYear(
                    item.month
                  )
              ),


            datasets: [

              {

                label:
                  "Total Spent",

                data:
                  data.map(
                    (item) =>
                      item.total
                  ),

                borderColor:
                  "#36A2EB",

                backgroundColor:
                  "rgba(54, 162, 235, 0.2)",

                fill:
                  true

              }

            ]

          },


          options: {

            responsive:
              true,

            maintainAspectRatio:
              true,


            scales: {

              x: {

                title: {

                  display:
                    true,

                  text:
                    "Month"

                }

              },


              y: {

                title: {

                  display:
                    true,

                  text:
                    "Total Spent"

                }

              }

            }

          }

        });

      })


      .catch((error) => {

        console.error(
          "Error fetching monthly total data:",
          error
        );

      });

  }


  // ==========================================
  // ALL-TIME CATEGORY PIE CHART
  // ==========================================

  if (allTimeCategoriesChart) {

    fetch(
      "/monthly-category-data"
    )

      .then((response) =>
        response.json()
      )

      .then((categorical_data) => {

        if (
          !Array.isArray(
            categorical_data
          )
        ) {

          throw new Error(
            "Expected an array but got something else"
          );

        }


        const categories =
          categorical_data.map(
            (data) =>
              data.category
          );


        const totals =
          categorical_data.map(
            (data) =>
              data.category_amount
          );


        const categoryColors = {

          Restaurants:
            "#FF5733",

          "Furniture/Home":
            "#33FF57",

          "Gas/Car":
            "#3357FF",

          Clothes:
            "#FF33A1",

          "School/Office Supplies":
            "#FF8C33",

          Misc:
            "#33FFF5",

          Groceries:
            "#8C33FF"

        };


        const defaultColor =
          "grey";


        const backgroundColors =
          categories.map(
            (category) => {

              return (
                categoryColors[
                  category
                ] ||
                defaultColor
              );

            }
          );


        new Chart(
          allTimeCategoriesChart,
          {

            type: "pie",

            data: {

              labels:
                categories,

              datasets: [

                {

                  data:
                    totals,

                  backgroundColor:
                    backgroundColors

                }

              ]

            },


            options: {

              responsive:
                true,

              maintainAspectRatio:
                false

            }

          }

        );

      })


      .catch((error) => {

        console.error(
          "Error fetching monthly category data:",
          error
        );

      });

  }


  // ==========================================
  // FINTRACK DASHBOARD SUMMARY
  // ==========================================

  async function updateDashboardSummary() {

    try {

      // Get all expenses
      const expenseResponse =
        await fetch("/month-data");

      const expenses =
        await expenseResponse.json();


      // Get all income
      const incomeResponse =
        await fetch("/income-data");

      const incomes =
        await incomeResponse.json();


      // ==========================================
      // TOTAL EXPENSES
      // ==========================================

      let totalExpenses = 0;

      const categoryTotals = {};


      if (Array.isArray(expenses)) {

        expenses.forEach(
          (expense) => {

            const amount =
              Number(
                expense.amount
              ) || 0;


            const category =
              expense.category ||
              "Other";


            totalExpenses +=
              amount;


            if (
              !categoryTotals[
                category
              ]
            ) {

              categoryTotals[
                category
              ] = 0;

            }


            categoryTotals[
              category
            ] += amount;

          }
        );

      }


      // ==========================================
      // TOTAL INCOME
      // ==========================================

      let totalIncome = 0;


      if (Array.isArray(incomes)) {

        incomes.forEach(
          (income) => {

            const amount =
              Number(
                income.amount
              ) || 0;


            totalIncome +=
              amount;

          }
        );

      }


      // ==========================================
      // BALANCE
      // ==========================================

      const balance =
        totalIncome -
        totalExpenses;


      // ==========================================
      // TOP CATEGORY
      // ==========================================

      let topCategory =
        "--";

      let highestAmount =
        0;


      Object.entries(
        categoryTotals
      ).forEach(
        ([category, amount]) => {

          if (
            amount >
            highestAmount
          ) {

            highestAmount =
              amount;

            topCategory =
              category;

          }

        }
      );


      // ==========================================
      // UPDATE DASHBOARD
      // ==========================================

      const incomeElement =
        document.getElementById(
          "totalIncome"
        );


      const expenseElement =
        document.getElementById(
          "totalExpenses"
        );


      const balanceElement =
        document.getElementById(
          "balance"
        );


      const categoryElement =
        document.getElementById(
          "topCategory"
        );


      if (incomeElement) {

        incomeElement.textContent =
          `$${totalIncome.toFixed(2)}`;

      }


      if (expenseElement) {

        expenseElement.textContent =
          `$${totalExpenses.toFixed(2)}`;

      }


      if (balanceElement) {

        balanceElement.textContent =
          `$${balance.toFixed(2)}`;

      }


      if (categoryElement) {

        categoryElement.textContent =
          topCategory;

      }


    } catch (error) {

      console.error(
        "Error updating dashboard:",
        error
      );

    }

  }


  // Run dashboard calculation
  // when page loads

  updateDashboardSummary();


  // ==========================================
  // ADD INCOME
  // ==========================================

  const incomeForm =
    document.getElementById(
      "incomeForm"
    );


  if (incomeForm) {

    incomeForm.addEventListener(
      "submit",
      async function (event) {

        event.preventDefault();


        const formData =
          new FormData(
            incomeForm
          );


        try {

          const response =
            await fetch(
              "/income",
              {

                method:
                  "POST",

                body:
                  formData

              }
            );


          const result =
            await response.json();


          if (result.success) {

            alert(
              "Income added successfully!"
            );


            incomeForm.reset();


            // Set today's date again

            const dateInput =
              document.getElementById(
                "incomeDate"
              );


            if (dateInput) {

              dateInput.value =
                new Date()
                  .toISOString()
                  .split("T")[0];

            }


          } else {

            alert(
              "Error adding income: " +
              result.error
            );

          }


        } catch (error) {

          console.error(
            "Error:",
            error
          );


          alert(
            "Something went wrong while adding income."
          );

        }

      }
    );

  }

});


// ==========================================
// MONTH NAME FUNCTION
// ==========================================

const getMonthName =
  (dateString) => {

    const [
      year,
      month
    ] =
      dateString.split("-");


    const date =
      new Date(
        year,
        month - 1
      );


    return date.toLocaleString(
      "default",
      {
        month: "long"
      }
    );

  };


// ==========================================
// MONTH + YEAR FUNCTION
// ==========================================

const getMonthYear =
  (dateString) => {

    const [
      year
    ] =
      dateString.split("-");


    return (
      getMonthName(
        dateString
      ) +
      " " +
      year
    );

  };


// ==========================================
// CUSTOM CATEGORY
// ==========================================

function toggleCustomCategory(select) {

  const customCategoryInput =
    document.getElementById(
      "customCategory"
    );


  if (!customCategoryInput) {
    return;
  }


  if (
    select.value ===
    "Other"
  ) {

    customCategoryInput.style.display =
      "block";

    customCategoryInput.required =
      true;

  } else {

    customCategoryInput.style.display =
      "none";

    customCategoryInput.required =
      false;

    customCategoryInput.value =
      "";

  }

}
// ==========================================
// BUDGET MANAGEMENT
// ==========================================

const budgetForm = document.getElementById("budgetForm");
const budgetList = document.getElementById("budgetList");
const budgetStatus = document.getElementById("budgetStatus");


// ==========================================
// LOAD BUDGETS + CALCULATE SPENDING
// ==========================================

async function loadBudgets() {

    if (!budgetList) {
        return;
    }

    try {

        // Get saved budgets
        const budgetResponse =
            await fetch("/budget-data");

        const budgets =
            await budgetResponse.json();


        // Get all expenses
        const expenseResponse =
            await fetch("/month-data");

        const expenses =
            await expenseResponse.json();


        // Clear existing list
        budgetList.innerHTML = "";


        if (!Array.isArray(budgets) || budgets.length === 0) {

            budgetList.innerHTML =
                "<p>No budgets have been set yet.</p>";

            return;
        }


        // ==========================================
        // CALCULATE SPENDING BY CATEGORY
        // ==========================================

        const spendingByCategory = {};


        if (Array.isArray(expenses)) {

            expenses.forEach(expense => {

                const category =
                    expense.category || "Other";

                const amount =
                    Number(expense.amount) || 0;


                if (!spendingByCategory[category]) {

                    spendingByCategory[category] = 0;

                }


                spendingByCategory[category] +=
                    amount;

            });

        }


        // ==========================================
        // DISPLAY EACH BUDGET
        // ==========================================

        budgets.forEach(budget => {

            const category =
                budget.category;

            const budgetAmount =
                Number(budget.amount) || 0;

            const spent =
                spendingByCategory[category] || 0;

            const remaining =
                budgetAmount - spent;


            // Percentage used
            let percentageUsed = 0;

            if (budgetAmount > 0) {

                percentageUsed =
                    (spent / budgetAmount) * 100;

            }


            // Don't show more than 100%
            const progressPercentage =
                Math.min(
                    percentageUsed,
                    100
                );


            // Create budget card
            const div =
                document.createElement("div");

            div.className =
                "summary-card";


            // Determine status
            let statusText =
                "Budget is on track.";

            if (percentageUsed >= 100) {

                statusText =
                    "⚠️ Budget exceeded!";

            } else if (percentageUsed >= 80) {

                statusText =
                    "⚠️ You are close to your budget limit.";

            }


            div.innerHTML = `

                <h3>
                    ${category}
                </h3>

                <p>
                    <strong>Budget:</strong>
                    $${budgetAmount.toFixed(2)}
                </p>

                <p>
                    <strong>Spent:</strong>
                    $${spent.toFixed(2)}
                </p>

                <p>
                    <strong>Remaining:</strong>
                    $${remaining.toFixed(2)}
                </p>

                <p>
                    <strong>Used:</strong>
                    ${percentageUsed.toFixed(1)}%
                </p>

                <p>
                    ${statusText}
                </p>

                <div
                    style="
                        width: 100%;
                        background: #ddd;
                        border-radius: 5px;
                        height: 12px;
                        margin-top: 10px;
                    "
                >

                    <div
                        style="
                            width: ${progressPercentage}%;
                            background: #4e7aa6;
                            height: 12px;
                            border-radius: 5px;
                        "
                    >
                    </div>

                </div>

            `;


            budgetList.appendChild(div);

        });


    } catch (error) {

        console.error(
            "Error loading budgets:",
            error
        );


        budgetList.innerHTML =
            "<p>Unable to load budgets.</p>";

    }

}


// ==========================================
// SAVE / UPDATE BUDGET
// ==========================================

if (budgetForm) {

    budgetForm.addEventListener(
        "submit",
        async function(event) {

            event.preventDefault();


            const formData =
                new FormData(budgetForm);


            try {

                const response =
                    await fetch(
                        "/budget",
                        {
                            method: "POST",
                            body: formData
                        }
                    );


                const result =
                    await response.json();


                if (result.success) {

                    budgetStatus.textContent =
                        "Budget saved successfully!";

                    budgetStatus.style.color =
                        "green";


                    budgetForm.reset();


                    // Refresh budget information
                    loadBudgets();


                } else {

                    budgetStatus.textContent =
                        "Error saving budget: " +
                        result.error;

                    budgetStatus.style.color =
                        "red";

                }


            } catch (error) {

                console.error(
                    "Error saving budget:",
                    error
                );


                budgetStatus.textContent =
                    "Something went wrong while saving the budget.";

                budgetStatus.style.color =
                    "red";

            }

        }
    );

}


// ==========================================
// LOAD BUDGETS WHEN PAGE OPENS
// ==========================================

loadBudgets();
// ==========================================
// DASHBOARD BUDGET OVERVIEW
// ==========================================

async function loadDashboardBudgets() {

    const dashboardBudgets =
        document.getElementById("dashboardBudgets");

    if (!dashboardBudgets) {
        return;
    }

    try {

        // Get budgets
        const budgetResponse =
            await fetch("/budget-data");

        const budgets =
            await budgetResponse.json();


        // Get expenses
        const expenseResponse =
            await fetch("/month-data");

        const expenses =
            await expenseResponse.json();


        dashboardBudgets.innerHTML = "";


        if (
            !Array.isArray(budgets) ||
            budgets.length === 0
        ) {

            dashboardBudgets.innerHTML =
                "<p>No budgets have been set yet.</p>";

            return;
        }


        // Calculate spending by category

        const spendingByCategory = {};


        if (Array.isArray(expenses)) {

            expenses.forEach(expense => {

                const category =
                    expense.category || "Other";

                const amount =
                    Number(expense.amount) || 0;


                if (!spendingByCategory[category]) {

                    spendingByCategory[category] = 0;

                }


                spendingByCategory[category] +=
                    amount;

            });

        }


        // Display each budget

        budgets.forEach(budget => {

            const category =
                budget.category;

            const budgetAmount =
                Number(budget.amount) || 0;

            const spent =
                spendingByCategory[category] || 0;

            const remaining =
                budgetAmount - spent;


            let percentageUsed = 0;

            if (budgetAmount > 0) {

                percentageUsed =
                    (spent / budgetAmount) * 100;

            }


            const progressPercentage =
                Math.min(
                    Math.max(percentageUsed, 0),
                    100
                );


            // Status

            let status =
                "Budget is on track.";

            if (percentageUsed >= 100) {

                status =
                    "⚠️ Budget exceeded!";

            }
            else if (percentageUsed >= 80) {

                status =
                    "⚠️ You are close to your budget limit.";

            }


            // Create dashboard card

            const card =
                document.createElement("div");

            card.className =
                "summary-card";


            card.innerHTML = `

                <h3>
                    ${category}
                </h3>

                <p>
                    <strong>Budget:</strong>
                    $${budgetAmount.toFixed(2)}
                </p>

                <p>
                    <strong>Spent:</strong>
                    $${spent.toFixed(2)}
                </p>

                <p>
                    <strong>Remaining:</strong>
                    $${remaining.toFixed(2)}
                </p>

                <p>
                    <strong>Used:</strong>
                    ${percentageUsed.toFixed(1)}%
                </p>

                <p>
                    ${status}
                </p>

                <div
                    style="
                        width: 100%;
                        background: #ddd;
                        border-radius: 5px;
                        height: 12px;
                        margin-top: 10px;
                    "
                >

                    <div
                        style="
                            width: ${progressPercentage}%;
                            background: #4e7aa6;
                            height: 12px;
                            border-radius: 5px;
                        "
                    >
                    </div>

                </div>

            `;


            dashboardBudgets.appendChild(card);

        });


    } catch (error) {

        console.error(
            "Error loading dashboard budgets:",
            error
        );

        dashboardBudgets.innerHTML =
            "<p>Unable to load budget information.</p>";

    }

}


// Load dashboard budgets when page opens

document.addEventListener("DOMContentLoaded", () => {
    loadDashboardBudgets();
});