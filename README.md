# TripWala ✈

TripWala is an offline, standalone desktop Flight Management System for a class 12 project. It uses Python, PySide6 for the native interface, and a local MySQL database. There is no browser, web server, external API or internet connection in the app.

## Preview

![TripWala search](overview.png)

![Flight results](flights.png)

Screenshots show illustrative sample data.

## What it does

- Register and sign in as a traveller; passwords are salted and hashed.
- Search flights by origin, destination and optional departure date, book seats, see bookings and cancel future bookings.
- Sign in as an administrator to add flights, set delays, cancel flights and view all bookings.
- A local timer updates flight status every 30 seconds based on the computer's clock: scheduled, boarding, delayed, departed and arrived. Admin cancellations remain cancelled. Delay shifts the simulated departure and arrival. The simulator runs while the app is open; opening it again catches up based on the current time.
- The first launch creates sample flights for roughly the next week. These are fictional demonstration records, not live airline data. Admins can add more flights as time passes.

## Requirements

- Python 3.10 or newer, with a version supported by PySide6 and MySQL Connector/Python.
- A locally installed and running MySQL 8 server. Remember its username and password; the account needs permission to create a database and tables on first run.
- PySide6 and mysql-connector-python, listed in `requirements.txt`. Installing dependencies may require internet; running the app does not.

## Run

Open a terminal in this folder:

```bash
python -m venv .venv
```

Activate it with `source .venv/bin/activate` on macOS/Linux or `.venv\Scripts\activate` on Windows, then:

```bash
python -m pip install -r requirements.txt
python main.py
```

Enter your local MySQL host (`localhost`), port (`3306`), username and password in the connection window. No credentials are saved by the application. The app creates `flight_management` and its tables on first connection. If your MySQL account cannot create databases, ask the MySQL administrator to grant the required permissions.

First-run administrator login:

- Email: `admin@flightdesk.local`
- Password: `Admin@123`

These are demonstration credentials. The application currently has no password-change screen; use this account only for a local classroom demo. Register a separate account for the traveller interface. The demo account is created only when the users table is empty.

## Database design

- `users`: login details and role.
- `flights`: route, schedule, seat capacity, price, delay and status.
- `bookings`: passenger reservations, with `user_id` referencing `users(id)` and `flight_id` referencing `flights(id)` through foreign keys.

Bookings are inserted in a transaction that locks the flight record and checks available seats. Cancelling a booking keeps its history and releases its seats. Cancelling a flight retains reservations and shows the flight's cancelled status alongside them. No real payments, ticket issuance or live flight data are involved.

## Troubleshooting

- **Connection refused:** start the local MySQL server and check host and port.
- **Access denied:** check the MySQL username, password and database creation privileges.
- **No flights:** clear the search or add flights through the admin account; seed flights eventually move into the past.
- **Dependencies fail to install:** use a Python version supported by current PySide6 wheels, such as Python 3.12 or 3.13.
