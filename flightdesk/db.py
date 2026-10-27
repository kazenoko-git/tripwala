"""MySQL persistence. All user-supplied values are parameterized."""
import hashlib
import hmac
import os
import random
from datetime import datetime, timedelta

import mysql.connector
from .geo import AIRPORT_COORDINATES, great_circle_distance

DATABASE = 'flight_management'
AIRPORTS = [('DEL', 'New Delhi'), ('BOM', 'Mumbai'), ('BLR', 'Bengaluru'), ('HYD', 'Hyderabad'), ('MAA', 'Chennai'), ('CCU', 'Kolkata'), ('GOI', 'Goa'), ('COK', 'Kochi')]


CITY_ALIASES = {'bangalore':'Bengaluru', 'bombay':'Mumbai', 'calcutta':'Kolkata', 'madras':'Chennai', 'cochin':'Kochi', 'trivandrum':'Thiruvananthapuram'}
INDIAN_AIRPORTS = {'DEL','BOM','BLR','HYD','MAA','CCU','GOI','COK','AMD','PNQ','JAI','IXC','TRV','GAU'}


def normalize_city(value):
    value=value.strip()
    return CITY_ALIASES.get(value.casefold(),value)


def airline_for_route(origin, destination, number):
    endpoints={origin,destination}
    if endpoints <= INDIAN_AIRPORTS: return ('6E','IndiGo') if number % 2 else ('AI','Air India')
    if 'DXB' in endpoints: return 'EK','Emirates'
    if 'DOH' in endpoints: return 'QR','Qatar Airways'
    if 'SIN' in endpoints: return 'SQ','Singapore Airlines'
    if 'LHR' in endpoints: return 'BA','British Airways'
    if endpoints == {'JFK','LAX'}: return 'AA','American Airlines'
    if endpoints == {'SFO','NRT'}: return 'NH','All Nippon Airways'
    return 'AI','Air India'


def hash_password(password, salt=None):
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 240000).hex()
    return f'{salt}${digest}'


def verify_password(password, stored):
    try:
        salt, _ = stored.split('$', 1)
        return hmac.compare_digest(hash_password(password, salt), stored)
    except (ValueError, TypeError):
        return False


class Database:
    def __init__(self, host, port, user, password):
        self.config = dict(host=host, port=int(port), user=user, password=password, connection_timeout=5)
        self.connection = None
        self._last_schedule_check = None
        self._last_delay_check = None

    def connect(self):
        self.connection = mysql.connector.connect(**self.config)
        self.connection.autocommit = True
        cursor = self.connection.cursor()
        cursor.execute(f'CREATE DATABASE IF NOT EXISTS {DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        cursor.execute(f'USE {DATABASE}')
        for statement in SCHEMA:
            cursor.execute(statement)
        # Existing installations gain simulator metadata without losing bookings.
        cursor.execute("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='flights'", (DATABASE,))
        columns = {row[0] for row in cursor.fetchall()}
        if 'delay_checked' not in columns:
            cursor.execute('ALTER TABLE flights ADD COLUMN delay_checked BOOLEAN NOT NULL DEFAULT FALSE')
        if 'delay_locked' not in columns:
            cursor.execute('ALTER TABLE flights ADD COLUMN delay_locked BOOLEAN NOT NULL DEFAULT FALSE')
        cursor.execute("CREATE TABLE IF NOT EXISTS simulator_days (flight_date DATE PRIMARY KEY) ENGINE=InnoDB")
        cursor.execute("CREATE TABLE IF NOT EXISTS simulator_network_days (flight_date DATE PRIMARY KEY) ENGINE=InnoDB")
        cursor.execute("CREATE TABLE IF NOT EXISTS simulator_domestic_v2_days (flight_date DATE PRIMARY KEY) ENGINE=InnoDB")
        self.connection.commit()
        cursor.close()
        self.seed()
        self.relabel_network_flights()

    def cursor(self, dictionary=True):
        self.connection.ping(reconnect=True, attempts=1, delay=0)
        self.connection.database = DATABASE
        return self.connection.cursor(dictionary=dictionary)

    def query(self, sql, params=()):
        cur = self.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()

    def execute(self, sql, params=()):
        cur = self.cursor()
        try:
            cur.execute(sql, params)
            self.connection.commit()
            return cur.lastrowid
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cur.close()

    def seed(self):
        if not self.query('SELECT id FROM users LIMIT 1'):
            self.execute('INSERT INTO users (name,email,password_hash,role) VALUES (%s,%s,%s,%s)', ('Administrator', 'admin@flightdesk.local', hash_password('Admin@123'), 'admin'))
        if not self.query('SELECT id FROM flights LIMIT 1'):
            now = datetime.now().replace(second=0, microsecond=0)
            rng = random.Random(42)
            airlines = [('AI', 'Air India'), ('6E', 'IndiGo'), ('IX', 'Air India Express'), ('SG', 'SpiceJet')]
            rows = []
            for day in range(7):
                for i in range(24):
                    origin = AIRPORTS[i % len(AIRPORTS)]
                    dest = AIRPORTS[(i + 1 + (i // len(AIRPORTS))) % len(AIRPORTS)]
                    code, airline = airlines[i % len(airlines)]
                    departure = (now + timedelta(days=day)).replace(hour=5 + (i * 2 % 18), minute=(i % 4) * 15)
                    if departure <= now:
                        departure += timedelta(days=1)
                    arrival = departure + timedelta(minutes=rng.randrange(75, 181, 15))
                    rows.append((f'{code} {100 + day * 24 + i}', airline, origin[0], origin[1], dest[0], dest[1], departure, arrival, rng.randrange(3200, 9800, 100), 120))
            cur = self.cursor()
            try:
                cur.executemany('INSERT INTO flights (flight_number,airline,origin_code,origin_city,destination_code,destination_city,departure,arrival,price,total_seats) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', rows)
                self.connection.commit()
            finally:
                cur.close()

    def register(self, name, email, password):
        return self.execute('INSERT INTO users (name,email,password_hash,role) VALUES (%s,%s,%s,%s)', (name, email.lower(), hash_password(password), 'customer'))

    def login(self, email, password):
        rows = self.query('SELECT * FROM users WHERE email=%s', (email.strip().lower(),))
        return rows[0] if rows and verify_password(password, rows[0]['password_hash']) else None

    def flights(self, origin='', destination='', date=None):
        sql = """SELECT f.*, f.total_seats - COALESCE(SUM(CASE WHEN b.status='Confirmed' THEN b.seats ELSE 0 END),0) AS available
                 FROM flights f LEFT JOIN bookings b ON b.flight_id=f.id
                 WHERE f.departure > NOW() AND f.status NOT IN ('Cancelled','Departed','Arrived')"""
        params = []
        origin=normalize_city(origin); destination=normalize_city(destination)
        if origin:
            sql += ' AND (f.origin_city LIKE %s OR f.origin_code LIKE %s)'
            params += [f'%{origin}%', f'%{origin}%']
        if destination:
            sql += ' AND (f.destination_city LIKE %s OR f.destination_code LIKE %s)'
            params += [f'%{destination}%', f'%{destination}%']
        if date:
            sql += ' AND DATE(f.departure)=%s'
            params.append(date)
        sql += ' GROUP BY f.id ORDER BY f.departure LIMIT 200'
        return self.query(sql, tuple(params))

    def book(self, user_id, flight_id, seats, passengers=None, contact_email=None, contact_phone=None, expected_price=None):
        cur = self.cursor()
        try:
            self.connection.start_transaction()
            cur.execute('SELECT * FROM flights WHERE id=%s FOR UPDATE', (flight_id,))
            flight = cur.fetchone()
            if not flight or flight['status'] in ('Cancelled','Departed','Arrived') or flight['departure'] <= datetime.now():
                raise ValueError('This flight is no longer available for booking.')
            if expected_price is not None and flight['price'] != expected_price:
                raise ValueError('The fare has changed. Return to the flight list and review it again.')
            cur.execute("SELECT COALESCE(SUM(seats),0) AS booked FROM bookings WHERE flight_id=%s AND status='Confirmed'", (flight_id,))
            available = flight['total_seats'] - cur.fetchone()['booked']
            if seats < 1 or seats > available:
                raise ValueError(f'Only {available} seat(s) available.')
            cur.execute('INSERT INTO bookings (user_id,flight_id,seats,total_price,status) VALUES (%s,%s,%s,%s,%s)', (user_id, flight_id, seats, flight['price'] * seats, 'Confirmed'))
            booking_id = cur.lastrowid
            if passengers is not None:
                if len(passengers) != seats or any(not name.strip() for name in passengers):
                    raise ValueError('Enter the name of every traveller.')
                cur.executemany('INSERT INTO booking_passengers (booking_id, full_name) VALUES (%s,%s)', [(booking_id, name.strip()) for name in passengers])
                cur.execute('INSERT INTO booking_contacts (booking_id, email, phone) VALUES (%s,%s,%s)', (booking_id, contact_email, contact_phone))
            self.connection.commit()
            return booking_id
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cur.close()

    def bookings(self, user_id=None):
        sql = """SELECT b.*, u.name, u.email, f.flight_number, f.airline, f.origin_code, f.destination_code, f.departure, f.status AS flight_status
                 FROM bookings b JOIN users u ON b.user_id=u.id JOIN flights f ON b.flight_id=f.id"""
        args = ()
        if user_id is not None:
            sql += ' WHERE b.user_id=%s'
            args = (user_id,)
        return self.query(sql + ' ORDER BY b.created_at DESC', args)

    def cancel_booking(self, booking_id, user_id):
        self.execute("UPDATE bookings b JOIN flights f ON f.id=b.flight_id SET b.status='Cancelled' WHERE b.id=%s AND b.user_id=%s AND b.status='Confirmed' AND f.departure > NOW()", (booking_id, user_id))

    def generate_flights(self, now=None):
        """Keep seven calendar days of fictional schedules; each date is generated once."""
        now = now or datetime.now()
        airlines = [('AI', 'Air India'), ('6E', 'IndiGo'), ('IX', 'Air India Express'), ('SG', 'SpiceJet')]
        for offset in range(7):
            date = (now + timedelta(days=offset)).date()
            rng = random.Random(date.toordinal())
            cur = self.cursor()
            try:
                self.connection.start_transaction()
                cur.execute('INSERT IGNORE INTO simulator_days (flight_date) VALUES (%s)', (date,))
                if cur.rowcount:
                    rows = []
                    for i in range(24):
                        origin = AIRPORTS[i % len(AIRPORTS)]
                        destination = AIRPORTS[(i + 1 + i // len(AIRPORTS)) % len(AIRPORTS)]
                        prefix, airline = airlines[i % len(airlines)]
                        departure = datetime.combine(date, datetime.min.time()) + timedelta(hours=5 + (i * 2 % 18), minutes=(i % 4) * 15)
                        # Do not insert flights that have already departed today.
                        if departure <= now: continue
                        arrival = departure + timedelta(minutes=rng.randrange(75, 181, 15))
                        rows.append((f'{prefix} {500+i}', airline, origin[0], origin[1], destination[0], destination[1], departure, arrival, rng.randrange(3200, 9800, 100), 120))
                    if rows:
                        cur.executemany('INSERT INTO flights (flight_number,airline,origin_code,origin_city,destination_code,destination_city,departure,arrival,price,total_seats) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', rows)
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise
            finally:
                cur.close()

    def relabel_network_flights(self):
        """Update older generated labels in place; flight and booking IDs are preserved."""
        rows=self.query("SELECT id, flight_number, origin_code, destination_code FROM flights WHERE airline=%s AND flight_number LIKE %s",('TripWala Simulated','TW %'))
        for row in rows:
            suffix=row['flight_number'][3:]
            if not suffix.isdigit() or not 1000 <= int(suffix) < 1078: continue
            prefix,name=airline_for_route(row['origin_code'],row['destination_code'],int(suffix)-1000)
            self.execute("UPDATE flights SET airline=%s, flight_number=%s WHERE id=%s AND airline=%s",(name,f'{prefix} {suffix}',row['id'],'TripWala Simulated'))

    def generate_bengaluru_chennai(self, now=None):
        """Add a common domestic route once per day on existing and new installs."""
        now=now or datetime.now()
        for offset in range(7):
            date=(now+timedelta(days=offset)).date(); cur=self.cursor()
            try:
                self.connection.start_transaction(); cur.execute('INSERT IGNORE INTO simulator_domestic_v2_days (flight_date) VALUES (%s)',(date,))
                if cur.rowcount:
                    rows=[]
                    for direction,(origin,ocity,dest,dcity) in enumerate([('BLR','Bengaluru','MAA','Chennai'),('MAA','Chennai','BLR','Bengaluru')]):
                        for i,hour in enumerate((6,10,14,19)):
                            depart=datetime.combine(date,datetime.min.time())+timedelta(hours=hour,minutes=direction*30)
                            if depart<=now: continue
                            prefix,name=airline_for_route(origin,dest,i+direction)
                            rows.append((f'{prefix} {800+direction*10+i}',name,origin,ocity,dest,dcity,depart,depart+timedelta(minutes=70),3200+i*500,180))
                    if rows: cur.executemany('INSERT INTO flights (flight_number,airline,origin_code,origin_city,destination_code,destination_city,departure,arrival,price,total_seats) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',rows)
                self.connection.commit()
            except Exception:
                self.connection.rollback(); raise
            finally: cur.close()

    def generate_network_flights(self, now=None):
        """Add a repeatable network of fictional routes without changing existing flights."""
        now=now or datetime.now()
        routes=[
            ('DEL','New Delhi','DXB','Dubai'),('BOM','Mumbai','LHR','London'),('DEL','New Delhi','LHR','London'),
            ('BOM','Mumbai','SIN','Singapore'),('DEL','New Delhi','SIN','Singapore'),('BLR','Bengaluru','SIN','Singapore'),
            ('DEL','New Delhi','JFK','New York'),('BOM','Mumbai','JFK','New York'),('DEL','New Delhi','SFO','San Francisco'),
            ('DEL','New Delhi','CDG','Paris'),('BOM','Mumbai','FRA','Frankfurt'),('DEL','New Delhi','FRA','Frankfurt'),
            ('BOM','Mumbai','DXB','Dubai'),('HYD','Hyderabad','DXB','Dubai'),('COK','Kochi','DXB','Dubai'),
            ('DEL','New Delhi','DOH','Doha'),('BOM','Mumbai','DOH','Doha'),('DEL','New Delhi','BKK','Bangkok'),
            ('CCU','Kolkata','BKK','Bangkok'),('DEL','New Delhi','KTM','Kathmandu'),('MAA','Chennai','CMB','Colombo'),
            ('BLR','Bengaluru','KUL','Kuala Lumpur'),('DEL','New Delhi','SYD','Sydney'),('DEL','New Delhi','NRT','Tokyo'),
            ('LHR','London','JFK','New York'),('JFK','New York','LAX','Los Angeles'),('SFO','San Francisco','NRT','Tokyo'),
            ('SIN','Singapore','SYD','Sydney'),('DXB','Dubai','CDG','Paris'),('FRA','Frankfurt','LHR','London'),
            ('BOM','Mumbai','GOI','Goa'),('DEL','New Delhi','AMD','Ahmedabad'),('BLR','Bengaluru','PNQ','Pune'),
            ('DEL','New Delhi','JAI','Jaipur'),('DEL','New Delhi','IXC','Chandigarh'),('BOM','Mumbai','TRV','Thiruvananthapuram'),
            ('BLR','Bengaluru','CCU','Kolkata'),('HYD','Hyderabad','MAA','Chennai'),('DEL','New Delhi','GAU','Guwahati'),
        ]
        for offset in range(7):
            date=(now+timedelta(days=offset)).date(); cur=self.cursor()
            try:
                self.connection.start_transaction(); cur.execute('INSERT IGNORE INTO simulator_network_days (flight_date) VALUES (%s)',(date,))
                if cur.rowcount:
                    rows=[]
                    for i,(a,ac,b,bc) in enumerate(routes):
                        if a not in AIRPORT_COORDINATES or b not in AIRPORT_COORDINATES: continue
                        distance=great_circle_distance(AIRPORT_COORDINATES[a],AIRPORT_COORDINATES[b])
                        duration=max(60,round((distance/800*60+35)/5)*5)
                        for direction in (0,1):
                            origin,ocity,dest,dcity=(a,ac,b,bc) if not direction else (b,bc,a,ac)
                            # Fictional schedules use the computer's local time throughout.
                            minute=(i*37 + direction*719) % (24*60)
                            departure=datetime.combine(date,datetime.min.time())+timedelta(minutes=minute)
                            arrival=departure+timedelta(minutes=duration)
                            if arrival<=now: continue
                            price=max(2500,min(140000,round((distance*7+1500)/100)*100))
                            prefix, airline=airline_for_route(origin,dest,i*2+direction)
                            rows.append((f'{prefix} {1000+i*2+direction}',airline,origin,ocity,dest,dcity,departure,arrival,price,180))
                    if rows: cur.executemany('INSERT INTO flights (flight_number,airline,origin_code,origin_city,destination_code,destination_city,departure,arrival,price,total_seats) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',rows)
                self.connection.commit()
            except Exception:
                self.connection.rollback(); raise
            finally:
                cur.close()

    def simulate_delays(self, rng=None):
        """Once within two hours of departure, give each untouched flight one delay roll."""
        rng = rng or random.SystemRandom()
        rows = self.query("""SELECT id FROM flights WHERE delay_checked=FALSE AND delay_locked=FALSE
            AND status IN ('Scheduled','Boarding') AND delay_minutes=0
            AND departure > NOW() AND departure <= DATE_ADD(NOW(), INTERVAL 2 HOUR)""")
        for flight in rows:
            minutes = rng.choice((15, 30, 45, 60)) if rng.random() < 0.12 else 0
            # Conditional update ensures an admin override wins a race with the simulator.
            self.execute("""UPDATE flights SET delay_checked=TRUE, delay_minutes=%s
                WHERE id=%s AND delay_checked=FALSE AND delay_locked=FALSE AND delay_minutes=0
                AND status IN ('Scheduled','Boarding') AND departure > NOW()""", (minutes, flight['id']))

    def simulate(self):
        """Refresh flight states frequently; replenish schedules and roll delays periodically."""
        now = datetime.now()
        if self._last_schedule_check is None or now - self._last_schedule_check >= timedelta(minutes=1):
            self.generate_flights(now)
            self.generate_network_flights(now)
            self.generate_bengaluru_chennai(now)
            self._last_schedule_check = now
        if self._last_delay_check is None or now - self._last_delay_check >= timedelta(seconds=30):
            self.simulate_delays()
            self._last_delay_check = now
        self.execute("""UPDATE flights SET status=CASE
            WHEN status='Cancelled' THEN 'Cancelled'
            WHEN NOW() >= DATE_ADD(arrival, INTERVAL delay_minutes MINUTE) THEN 'Arrived'
            WHEN NOW() >= DATE_ADD(departure, INTERVAL delay_minutes MINUTE) THEN 'Departed'
            WHEN delay_minutes > 0 THEN 'Delayed'
            WHEN NOW() >= DATE_SUB(departure, INTERVAL 30 MINUTE) THEN 'Boarding'
            ELSE 'Scheduled' END""")


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100) NOT NULL, email VARCHAR(190) NOT NULL UNIQUE, password_hash VARCHAR(150) NOT NULL, role ENUM('admin','customer') NOT NULL DEFAULT 'customer', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS flights (id INT AUTO_INCREMENT PRIMARY KEY, flight_number VARCHAR(20) NOT NULL, airline VARCHAR(80) NOT NULL, origin_code CHAR(3) NOT NULL, origin_city VARCHAR(80) NOT NULL, destination_code CHAR(3) NOT NULL, destination_city VARCHAR(80) NOT NULL, departure DATETIME NOT NULL, arrival DATETIME NOT NULL, price DECIMAL(10,2) NOT NULL, total_seats INT NOT NULL, status ENUM('Scheduled','Boarding','Delayed','Departed','Arrived','Cancelled') NOT NULL DEFAULT 'Scheduled', delay_minutes INT NOT NULL DEFAULT 0, INDEX (departure)) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS bookings (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, flight_id INT NOT NULL, seats INT NOT NULL, total_price DECIMAL(10,2) NOT NULL, status ENUM('Confirmed','Cancelled') NOT NULL DEFAULT 'Confirmed', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY (flight_id) REFERENCES flights(id), INDEX (flight_id,status)) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS booking_passengers (id INT AUTO_INCREMENT PRIMARY KEY, booking_id INT NOT NULL, full_name VARCHAR(100) NOT NULL, FOREIGN KEY (booking_id) REFERENCES bookings(id)) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS booking_contacts (booking_id INT PRIMARY KEY, email VARCHAR(190) NOT NULL, phone VARCHAR(25) NOT NULL, FOREIGN KEY (booking_id) REFERENCES bookings(id)) ENGINE=InnoDB"""
]
