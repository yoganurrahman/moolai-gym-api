# Moolai Gym API - Test Scenarios

This folder contains real-world scenario tests that simulate typical gym operations.

## Available Scenarios

### 1. New Member Journey (`scenario_new_member.py`)
Simulates the complete journey of a new member:
- Member registration
- Purchasing membership package
- First check-in
- Booking a class
- Booking PT session

### 2. Daily Operations (`scenario_daily_ops.py`)
Simulates typical daily gym operations:
- Staff opening shift
- Processing multiple check-ins
- Handling POS transactions
- Processing walk-in membership sales
- End of day report

### 3. Admin Tasks (`scenario_admin.py`)
Simulates admin management tasks:
- Creating new staff account
- Setting up new class schedules
- Configuring promo campaigns
- Generating reports

## Running Scenarios

```bash
# Run all scenarios
python run_scenarios.py

# Run specific scenario
python scenario_new_member.py
python scenario_daily_ops.py
python scenario_admin.py
```

## Prerequisites

1. API server must be running at `http://localhost:8181`
2. Database should be seeded with initial data:
   - At least one admin user (admin@moolaigym.com)
   - At least one membership package
   - At least one product

## Test Data

Scenarios will create their own test data (users, transactions, etc.)
and will not affect existing production data if properly isolated.
