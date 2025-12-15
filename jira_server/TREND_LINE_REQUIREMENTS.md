# 📉 Value Reduction Requirement

This document defines the constraint for the linear reduction of an initial value ($V$) to zero over a period of time ($D$).

## 1. Goal

The primary goal is to ensure that the rate of reduction never falls below a specified minimum, guaranteeing a consistent and timely decay of the initial value.

## 2. Definitions

| Variable | Description | Initial Value (Example) |
| :--- | :--- | :--- |
| **$V$** | The Initial Value (starting $Y$-axis value). | $500$ |
| **$m$** | The calculated slope (daily rate of reduction). | $-1.3698$ |
| **$D$** | The actual duration (in days) used for reduction. | $D > 0$ |
| **$T_{min}$** | The maximum allowed duration (in days) for the reduction. | $365$ days |

## 3. The Constraint: Minimum Steepness

The "shallowest" acceptable slope is defined by reaching $0$ in exactly $365$ days. This means the daily reduction must be at least $1/365$ of the initial value $V$.

### A. Rate of Reduction

The required minimum rate of reduction (as a percentage of the initial value) is:
$$\text{Min Rate} = \frac{1}{T_{min}} \times 100\% \approx \mathbf{0.274\% \text{ per day}}$$

### B. Mathematical Requirement

The daily slope ($m$) used in the implementation **must be less than or equal to** the slope calculated for the $365$-day limit. This forces the slope to be either the minimum required value (exactly $365$ days) or a steeper value (fewer than $365$ days).

$$\mathbf{m \le -\frac{V}{T_{min}}}$$

#### Example Check (V = 500, T_min = 365)
The shallowest acceptable slope is:
$$m_{min} = -\frac{500}{365} \approx -1.3698$$

| Scenario | Calculated Slope ($m$) | Passes $m \le -1.3698$? | Result |
| :--- | :--- | :--- | :--- |
| **A. On Target** (365 days) | $m = -1.3698$ | True | **Valid** |
| **B. Steeper** (180 days) | $m \approx -2.777$ | True ($-2.777 < -1.3698$) | **Valid** |
| **C. Too Shallow** (400 days) | $m = -1.25$ | False ($-1.25 \not\le -1.3698$) | **INVALID** |

## 4. Requirement for Implementation

Any calculated linear reduction plan must ensure that the number of days ($D$) used to reach zero does not exceed $T_{min}$ (365 days).

$$\mathbf{D \le T_{min}}$$

## 5. Implementation Details

The constraint is enforced in `jira_automation/burndown_forecast.py` using the following algorithm:

### Algorithm Overview

1. **Fit OLS regression** to historical data: $y = a + b \cdot t$ where:
   - $y$ = story points remaining
   - $t$ = days since first observation
   - $a$ = y-intercept (initial value $V$)
   - $b$ = slope (daily burn rate)

2. **Calculate minimum acceptable slope**: $b_{min} = -\frac{a}{365}$

3. **Enforce constraint**: If calculated slope $b > b_{min}$ (too shallow), return no forecast

4. **Generate forecast**: If constraint is satisfied, calculate zero-crossing and confidence interval

### Behavior

- **Forecasts shown**: Epics with burn rate ≥ minimum required (completion ≤ 365 days)
- **No forecast shown**: Epics with burn rate < minimum required (would exceed 365 days)
- Charts display only historical data when no forecast is available

### Files Modified

- **Core logic**: `jira_automation/burndown_forecast.py` - Shared constrained forecasting module
- **COMPDIV integration**: `jira_automation/compdiv_burndown.py` - Uses shared module
- **IRIS integration**: `jira_automation/iris_burndown.py` - Uses shared module

This ensures all forecasts predict completion within 365 days of the most recent data point, preventing unrealistic long-term predictions.