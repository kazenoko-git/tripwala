"""Native Qt interface for FlightDesk."""
from datetime import datetime
from pathlib import Path
import json
import re

from PySide6.QtCore import Qt, QTimer, QDate, QDateTime
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient, QPixmap, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QFrame, QMessageBox, QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QFormLayout, QSpinBox, QDoubleSpinBox, QDateTimeEdit, QComboBox, QAbstractItemView, QInputDialog, QScrollArea, QDateEdit, QCheckBox)
from mysql.connector import Error
from .db import Database

STYLE = """
QWidget { background: #f2f5fa; color: #17243c; font-family: "Helvetica Neue", "Arial"; font-size: 13px; }
QMainWindow { background: #f4f2ec; }
QFrame#sidebar { background: #102443; border: none; }
QFrame#sidebar QLabel { background: transparent; color: #f5f1e8; }
QFrame#sidebar QPushButton { background: transparent; color: #abbeb6; border: none; text-align: left; padding: 15px 16px; border-radius: 9px; font-weight: 600; }
QFrame#sidebar QPushButton:hover, QFrame#sidebar QPushButton:checked { background: #234d7b; color: #fffdf2; }
QLabel#title { font-size: 31px; font-weight: 700; color: #20302d; }
QLabel#subtitle, QLabel#muted { color: #798981; font-size: 13px; }
QLabel#hero { font-size: 42px; font-weight: 700; color: #fff9e9; background: transparent; }
QLineEdit, QSpinBox, QDoubleSpinBox, QDateTimeEdit, QComboBox { background: #fffefa; border: 1px solid #d8e1d9; border-radius: 9px; padding: 12px; min-height: 20px; selection-background-color: #416c5b; }
QLineEdit:focus, QSpinBox:focus, QDateTimeEdit:focus { border: 1px solid #527c6a; }
QPushButton { background: #1264d5; color: #fffdf3; border: none; border-radius: 9px; padding: 13px 19px; font-weight: 700; }
QPushButton:hover { background: #0c50af; }
QPushButton#secondary { background: #e4ebe2; color: #355b49; }
QPushButton#secondary:hover { background: #d5e2d4; }
QPushButton#danger { background: #f7e9e3; color: #a04b38; }
QTableWidget { background: #fffefa; border: 1px solid #e0e6dd; border-radius: 14px; gridline-color: #edf0eb; alternate-background-color: #f8faf5; selection-background-color: #dcebe0; selection-color: #20302d; }
QHeaderView::section { background: #edf2eb; color: #73867b; border: none; border-bottom: 1px solid #e0e8dd; padding: 14px 7px; font-weight: 700; }
QTableWidget::item { padding: 8px; border-bottom: 1px solid #edf0eb; }
QDialog { background: #f4f2ec; }
"""


class SkyPanel(QFrame):
    """A painted, scalable landscape that keeps the interface fully offline."""
    def __init__(self, compact=False):
        super().__init__(); self.compact=compact
        self.setMinimumHeight(255 if compact else 480)
    def paintEvent(self, event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w=self.width(); h=self.height()
        path=QPainterPath(); path.addRoundedRect(0,0,w,h,18 if self.compact else 0,18 if self.compact else 0)
        p.setClipPath(path)
        grad=QLinearGradient(0,0,w,h); grad.setColorAt(0,QColor('#416c5b')); grad.setColorAt(1,QColor('#afc5a9'))
        p.fillRect(self.rect(),grad)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#e9d9aa')); p.drawEllipse(int(w*.70),int(h*.11),int(h*.25),int(h*.25))
        for color, points in [('#86a88e',[(0,.76),(.20,.44),(.36,.72),(.57,.37),(.83,.72),(1,.52),(1,1),(0,1)]),('#618b74',[(0,.87),(.24,.65),(.43,.83),(.68,.57),(1,.84),(1,1),(0,1)]),('#345e4d',[(0,.93),(.27,.82),(.50,.96),(.79,.73),(1,.88),(1,1),(0,1)])]:
            mountain=QPainterPath(); mountain.moveTo(points[0][0]*w,points[0][1]*h)
            for x,y in points[1:]: mountain.lineTo(x*w,y*h)
            mountain.closeSubpath(); p.fillPath(mountain,QColor(color))
        pen=QPen(QColor(255,255,245,130),1.5,Qt.PenStyle.DashLine); p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        route=QPainterPath(); route.moveTo(w*.50,h*.29); route.cubicTo(w*.64,h*.02,w*.79,h*.48,w*.93,h*.20); p.drawPath(route)
        p.setPen(QColor('#fff9e9')); p.setFont(QFont('Arial',18)); p.drawText(int(w*.90),int(h*.20),'✈')
        p.end()



class TravelArtwork(QFrame):
    """Small vector illustrations painted locally; no image downloads needed."""
    def __init__(self, scene, parent=None):
        super().__init__(parent); self.scene=scene
        if scene != 'login': self.setFixedHeight(116)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w=self.width(); h=self.height()
        if self.scene=='login':
            p.fillRect(self.rect(),QColor('#102f60'))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#173d75')); p.drawEllipse(int(w*.49),int(h*.05),int(w*.78),int(w*.78))
            p.setBrush(QColor('#204b85')); p.drawEllipse(int(w*.70),int(h*.18),int(w*.40),int(w*.40))
            pen=QPen(QColor(185,211,247,130),2,Qt.PenStyle.DashLine); p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            route=QPainterPath(); route.moveTo(w*.54,h*.18); route.cubicTo(w*.83,h*.05,w*.50,h*.42,w*.91,h*.35); p.drawPath(route)
            p.setPen(QColor('#ff9b4a')); p.setFont(QFont('Arial',25)); p.drawText(int(w*.86),int(h*.35),'✈')
            p.setPen(QColor(195,216,245,150)); p.setFont(QFont('Arial',10)); p.drawText(int(w*.67),int(h*.16),'DEL'); p.drawText(int(w*.84),int(h*.40),'BOM')
        else:
            colors={'BOM':('#b9def5','#eaf6ff','#5e96c6'), 'HYD':('#dcdcf7','#f4efff','#8b84bd'), 'COK':('#c8e9e5','#f2faf2','#60a99d')}
            sky,light,land=colors[self.scene]; p.fillRect(self.rect(),QColor(sky)); p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(light)); p.drawEllipse(int(w*.72),-24,85,85)
            p.setBrush(QColor(255,255,255,115)); p.drawEllipse(int(w*.12),22,45,12); p.drawEllipse(int(w*.18),15,53,19); p.drawEllipse(int(w*.61),20,56,12)
            p.setBrush(QColor(land))
            if self.scene=='BOM':
                for x,height,width in [(0,35,25),(.11,50,26),(.24,41,30),(.37,65,24),(.49,42,28),(.62,55,28),(.76,39,28),(.89,62,30)]:
                    p.drawRect(int(w*x),h-height,width,height)
            elif self.scene=='HYD':
                p.drawRect(0,h-23,w,23); p.drawRect(int(w*.38),h-59,int(w*.24),42)
                for x in (.37,.58): p.drawRect(int(w*x),h-77,8,55); p.drawEllipse(int(w*x)-3,h-83,14,10)
                p.drawEllipse(int(w*.44),h-73,int(w*.12),30)
            else:
                p.drawRect(0,h-24,w,24)
                pen=QPen(QColor(land),5); p.setPen(pen); p.drawLine(int(w*.74),h-20,int(w*.79),h-78)
                p.setPen(Qt.PenStyle.NoPen)
                for x,y in [(.69,.30),(.74,.24),(.79,.20),(.84,.24),(.88,.29)]: p.drawEllipse(int(w*x),int(h*y),int(w*.12),10)
            p.setPen(QColor('#284b70')); p.setFont(QFont('Arial',16,QFont.Weight.Bold)); p.drawText(16,26,self.scene+'   →')
        p.end()


def paint_mark(p, x, y, size):
    """A curved route ending in a north-east arrow."""
    p.save(); p.translate(x,y); p.scale(size/40,size/40)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#ff8a3d')); p.drawRoundedRect(0,0,40,40,12,12)
    pen=QPen(QColor('white'),3.2); pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin); p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
    route=QPainterPath(); route.moveTo(9,26); route.cubicTo(14,30,19,30,21,24); route.cubicTo(23,18,24,15,30,12); p.drawPath(route)
    p.drawLine(23,12,30,12); p.drawLine(30,12,30,19); p.restore()


class Brand(QWidget):
    def __init__(self):
        super().__init__(); self.setFixedSize(190,42); self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); paint_mark(p,0,3,36)
        p.setPen(QColor('#ffffff')); f=QFont('Arial',19); f.setBold(True); p.setFont(f); p.drawText(47,29,'TripWala'); p.end()


def brand_icon():
    pixmap=QPixmap(128,128); pixmap.fill(Qt.GlobalColor.transparent); painter=QPainter(pixmap); painter.setRenderHint(QPainter.RenderHint.Antialiasing); paint_mark(painter,4,4,120); painter.end(); return QIcon(pixmap)


def label(text, object_name=None):
    widget = QLabel(text)
    if object_name: widget.setObjectName(object_name)
    return widget


def button(text, callback, kind=None):
    widget = QPushButton(text)
    if kind: widget.setObjectName(kind)
    widget.clicked.connect(callback)
    return widget


def field(placeholder, secret=False):
    w = QLineEdit(); w.setPlaceholderText(placeholder)
    if secret: w.setEchoMode(QLineEdit.EchoMode.Password)
    return w


def table(headers):
    t = QTableWidget(0, len(headers)); t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.verticalHeader().setVisible(False); t.setAlternatingRowColors(True)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setShowGrid(False); t.verticalHeader().setDefaultSectionSize(52)
    return t


def fill(t, rows):
    t.setRowCount(len(rows))
    for i, (identifier, values) in enumerate(rows):
        for j, value in enumerate(values):
            item = QTableWidgetItem(str(value)); item.setData(Qt.ItemDataRole.UserRole, identifier)
            t.setItem(i, j, item)


def selected_id(t):
    row = t.currentRow()
    return t.item(row, 0).data(Qt.ItemDataRole.UserRole) if row >= 0 and t.item(row, 0) else None


def money(x): return '₹{:,.0f}'.format(x)
def dt(x): return x.strftime('%d %b %Y, %I:%M %p')


class SetupDialog(QDialog):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Connect to MySQL'); self.setMinimumWidth(440)
        layout = QVBoxLayout(self); layout.setSpacing(12)
        layout.addWidget(label('Welcome to TripWala', 'title'))
        layout.addWidget(label('Connect to your local MySQL server to get started.', 'subtitle'))
        self.host = field('Host'); self.host.setText('localhost')
        self.port = field('Port'); self.port.setText('3306')
        self.user = field('MySQL username'); self.user.setText('root')
        self.password = field('MySQL password', True)
        form = QFormLayout(); form.addRow('Host', self.host); form.addRow('Port', self.port); form.addRow('Username', self.user); form.addRow('Password', self.password)
        layout.addLayout(form); layout.addWidget(button('Connect & open TripWala', self.connect_db))
        layout.addWidget(label('The database and demo flights are created on first launch.', 'muted'))
        self.db = None

    def connect_db(self):
        try:
            db = Database(self.host.text().strip(), self.port.text(), self.user.text().strip(), self.password.text()); db.connect(); db.simulate()
            self.db = db; self.accept()
        except (Error, ValueError) as e: QMessageBox.critical(self, 'Connection failed', f'Could not connect or set up MySQL.\n\n{e}\n\nCheck that MySQL is running and this account can create databases.')


class Auth(QWidget):
    def __init__(self, db, on_login):
        super().__init__(); self.db = db; self.on_login = on_login; self.registering = False
        outer = QHBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        left = TravelArtwork('login'); left_layout = QVBoxLayout(left); left_layout.setContentsMargins(65,58,65,58)
        left_layout.addWidget(Brand()); left_layout.addStretch()
        kicker=label('YOUR FLIGHT BOOKING COMPANION'); kicker.setStyleSheet('color:#97bce8; font-size:11px; font-weight:800; background:transparent;'); left_layout.addWidget(kicker)
        headline=label('Your next trip\nstarts here.'); headline.setStyleSheet('font-size:48px; font-weight:800; color:white; background:transparent;'); left_layout.addWidget(headline)
        caption=label('Search flights, plan your journey and keep\neverything in one place.'); caption.setStyleSheet('color:#c8daf0; font-size:16px; background:transparent;'); left_layout.addWidget(caption); left_layout.addSpacing(35)
        for text in ('✈   Explore flights across India', '✓   Keep track of your bookings', '◷   Stay updated on flight status'):
            feature=label(text); feature.setStyleSheet('color:#e7effa; font-size:14px; padding:9px 0; background:transparent;'); left_layout.addWidget(feature)
        left_layout.addStretch(); foot=label('MADE FOR EVERY JOURNEY'); foot.setStyleSheet('color:#8dafd7; font-size:10px; font-weight:700; background:transparent;'); left_layout.addWidget(foot); outer.addWidget(left,5)
        right = QWidget(); right_layout = QVBoxLayout(right); right_layout.setContentsMargins(75,50,75,50); right_layout.addStretch()
        eyebrow=label('WELCOME TO TRIPWALA', 'subtitle'); eyebrow.setStyleSheet('color:#5d83b5; font-size:10px; font-weight:800;'); right_layout.addWidget(eyebrow)
        self.heading = label('Welcome back', 'title'); right_layout.addWidget(self.heading)
        self.intro = label('Sign in to manage your journeys.', 'subtitle'); right_layout.addWidget(self.intro); right_layout.addSpacing(24)
        self.name = field('Full name'); self.name.hide(); self.email = field('Email address'); self.password = field('Password', True)
        for w in (self.name, self.email, self.password): right_layout.addWidget(w)
        self.submit = button('Sign in', self.submit_auth); right_layout.addWidget(self.submit)
        self.switch = button('New here? Create an account', self.toggle, 'secondary'); right_layout.addWidget(self.switch)
        right_layout.addStretch(); right_layout.addWidget(label('Offline desktop project • Powered by MySQL', 'muted')); outer.addWidget(right, 4)
        self.password.returnPressed.connect(self.submit_auth)

    def toggle(self):
        self.registering = not self.registering; self.name.setVisible(self.registering)
        self.heading.setText('Create your account' if self.registering else 'Welcome back')
        self.intro.setText('Your next adventure is waiting.' if self.registering else 'Sign in to manage your journeys.')
        self.submit.setText('Create account' if self.registering else 'Sign in')
        self.switch.setText('Already have an account? Sign in' if self.registering else 'New here? Create an account')

    def submit_auth(self):
        email = self.email.text().strip().lower(); password = self.password.text()
        try:
            if self.registering:
                name = self.name.text().strip()
                if not name or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(password) < 8:
                    raise ValueError('Enter your name, a valid email and a password of at least 8 characters.')
                self.db.register(name, email, password); QMessageBox.information(self, 'Account created', 'You can now sign in.'); self.toggle(); return
            user = self.db.login(email, password)
            if not user: raise ValueError('Incorrect email or password.')
            self.password.clear(); self.on_login(user)
        except (Error, ValueError) as e: QMessageBox.warning(self, 'Could not continue', str(e))


class FlightDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent); self.setWindowTitle('Add flight'); self.setMinimumWidth(430)
        layout = QVBoxLayout(self); layout.addWidget(label('Add a flight', 'title')); form = QFormLayout(); self.fields = {}
        for key, title in [('number','Flight number'),('airline','Airline'),('oc','Origin code (3 letters)'),('ocity','Origin city'),('dc','Destination code (3 letters)'),('dcity','Destination city')]:
            self.fields[key] = field(title); form.addRow(title, self.fields[key])
        self.departure = QDateTimeEdit(QDateTime.currentDateTime().addDays(1)); self.arrival = QDateTimeEdit(QDateTime.currentDateTime().addDays(1).addSecs(7200))
        for w in (self.departure, self.arrival): w.setCalendarPopup(True); w.setDisplayFormat('dd MMM yyyy HH:mm')
        self.price = QDoubleSpinBox(); self.price.setRange(1, 1000000); self.price.setValue(5000); self.price.setPrefix('₹ ')
        self.seats = QSpinBox(); self.seats.setRange(1, 1000); self.seats.setValue(120)
        for title, w in [('Departure',self.departure),('Arrival',self.arrival),('Price per seat',self.price),('Seats',self.seats)]: form.addRow(title,w)
        layout.addLayout(form); layout.addWidget(button('Save flight', self.validate))

    def validate(self):
        vals = {k:v.text().strip() for k,v in self.fields.items()}
        if any(not x for x in vals.values()) or not re.fullmatch('[A-Za-z]{3}', vals['oc']) or not re.fullmatch('[A-Za-z]{3}', vals['dc']):
            QMessageBox.warning(self, 'Check the details', 'Complete every field and use three-letter airport codes.'); return
        if vals['oc'].upper() == vals['dc'].upper() or self.departure.dateTime() <= QDateTime.currentDateTime() or self.arrival.dateTime() <= self.departure.dateTime():
            QMessageBox.warning(self, 'Check the details', 'Choose different airports, a future departure and a later arrival.'); return
        self.values = (vals['number'].upper(), vals['airline'], vals['oc'].upper(), vals['ocity'], vals['dc'].upper(), vals['dcity'], self.departure.dateTime().toPython(), self.arrival.dateTime().toPython(), self.price.value(), self.seats.value()); self.accept()


class BookingPage(QWidget):
    """Traveller details and explicit fare review before a simulated reservation."""
    def __init__(self, dashboard):
        super().__init__(); self.dashboard=dashboard; self.flight=None; self.names=[]
        outer=QVBoxLayout(self); outer.setContentsMargins(42,25,42,25); outer.setSpacing(12)
        top=QHBoxLayout(); top.addWidget(button('← Back to flights',lambda:dashboard.navigate(1),'secondary')); top.addStretch(); top.addWidget(label('FLIGHT  →  TRAVELLERS  →  REVIEW','subtitle')); outer.addLayout(top)
        outer.addWidget(label('Complete your booking','title')); outer.addWidget(label('Enter traveller details, then review before confirming.','subtitle'))
        content=QHBoxLayout(); content.setSpacing(18); outer.addLayout(content,1)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame); body=QWidget(); self.form=QVBoxLayout(body); self.form.setContentsMargins(2,2,2,2); self.form.setSpacing(12)
        section=label('Traveller details'); section.setStyleSheet('font-size:18px; font-weight:800;'); self.form.addWidget(section)
        self.form.addWidget(label('Passenger count','subtitle')); self.count=QSpinBox(); self.count.setRange(1,9); self.count.valueChanged.connect(self.update_passengers); self.form.addWidget(self.count)
        self.passenger_container=QWidget(); self.passenger_layout=QVBoxLayout(self.passenger_container); self.passenger_layout.setContentsMargins(0,0,0,0); self.form.addWidget(self.passenger_container)
        self.form.addWidget(label('Contact details','title')); self.email=field('Email for this booking'); self.phone=field('Mobile number'); self.form.addWidget(self.email); self.form.addWidget(self.phone)
        self.form.addWidget(label('Simulation only • No payment will be collected.','subtitle')); self.form.addStretch(); scroll.setWidget(body); content.addWidget(scroll,3)
        right=QFrame(); right.setObjectName('bookingSummary'); right.setStyleSheet('QFrame#bookingSummary { background:white; border:1px solid #dfe7f1; border-radius:15px; }'); summary=QVBoxLayout(right); summary.setContentsMargins(22,22,22,22)
        title=label('Your flight'); title.setStyleSheet('font-size:19px; font-weight:800; background:transparent;'); summary.addWidget(title)
        self.route=label(''); self.route.setWordWrap(True); self.route.setStyleSheet('background:transparent; font-size:21px; font-weight:800; color:#153869;'); summary.addWidget(self.route)
        self.details=label(''); self.details.setWordWrap(True); self.details.setStyleSheet('background:transparent; color:#708198; line-height:1.5;'); summary.addWidget(self.details); summary.addSpacing(16)
        self.fare=label(''); self.fare.setWordWrap(True); self.fare.setStyleSheet('background:transparent; color:#213c61; font-size:16px; font-weight:700;'); summary.addWidget(self.fare); summary.addStretch()
        self.review=button('Review booking  →', self.review_booking); summary.addWidget(self.review); content.addWidget(right,2)
        self.update_passengers()

    def open_flight(self,flight):
        self.flight=flight; self.count.setValue(1); self.update_passengers(); self.names[0].setText(self.dashboard.user['name']); self.email.setText(self.dashboard.user['email']); self.phone.clear()
        self.route.setText(f"{flight['origin_code']}  →  {flight['destination_code']}")
        self.details.setText(f"{flight['airline']}  ·  {flight['flight_number']}\n{dt(flight['departure'])}  →  {dt(flight['arrival'])}\nStatus: {flight['status']}")
        self.update_fare()

    def update_passengers(self):
        existing=[w.text() for w in self.names]
        while self.passenger_layout.count():
            item=self.passenger_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.names=[]
        for i in range(self.count.value()):
            name=field(f'Traveller {i+1} · full name'); name.setMaxLength(100)
            if i < len(existing): name.setText(existing[i])
            self.names.append(name); self.passenger_layout.addWidget(name)
        self.update_fare()

    def update_fare(self):
        if self.flight:
            n=self.count.value(); self.fare.setText(f"{money(self.flight['price'])} × {n} traveller{'s' if n!=1 else ''}\n\nTotal  {money(self.flight['price']*n)}")

    def review_booking(self):
        names=[w.text().strip() for w in self.names]; email=self.email.text().strip(); phone=self.phone.text().strip()
        if any(not name for name in names) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or not re.fullmatch(r'[+0-9 ()-]{7,25}',phone):
            QMessageBox.warning(self,'Check traveller details','Enter every traveller’s name, a valid email and a phone number.'); return
        f=self.flight; n=len(names)
        text=f"{f['origin_code']} → {f['destination_code']}  ·  {f['flight_number']}\n{dt(f['departure'])}\n\nTravellers: {', '.join(names)}\nContact: {email}  ·  {phone}\n\nTotal: {money(f['price']*n)}\n\nThis is a simulated booking; no payment is collected. Confirm?"
        if QMessageBox.question(self,'Review your booking',text) != QMessageBox.StandardButton.Yes: return
        try:
            bid=self.dashboard.db.book(self.dashboard.user['id'],f['id'],n,names,email,phone,f['price'])
            QMessageBox.information(self,'Booking confirmed',f'Booking FD-{bid:05} is confirmed. Find it under My trips.')
            self.dashboard._flight_snapshot=None; self.dashboard._booking_snapshot=None; self.dashboard.navigate(2)
        except (Error, ValueError) as exc: QMessageBox.warning(self,'Could not book flight',str(exc))


class Dashboard(QWidget):
    def __init__(self, db, user, logout):
        super().__init__(); self.db=db; self.user=user; self.logout=logout; self.admin=user['role']=='admin'
        self._flight_snapshot=None; self._booking_snapshot=None
        self.stack=QStackedWidget(); self.nav_buttons=[]
        pages = [('Home', self.overview_page()), ('Flights', self.flights_page()), ('My trips' if not self.admin else 'Bookings', self.bookings_page())]
        if self.admin:
            root=QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
            sidebar=QFrame(); sidebar.setObjectName('sidebar'); sidebar.setFixedWidth(230); nav=QVBoxLayout(sidebar); nav.setContentsMargins(18,30,18,25)
            brand=Brand(); nav.addWidget(brand); nav.addSpacing(10); nav.addWidget(label('ADMIN CONSOLE')); nav.addSpacing(30)
            for index, (name,page) in enumerate(pages):
                b=button('  '+name, lambda checked=False, i=index:self.navigate(i)); b.setCheckable(True); nav.addWidget(b); self.nav_buttons.append(b); self.stack.addWidget(page)
            nav.addStretch(); nav.addWidget(label(user['name'])); nav.addWidget(button('  Sign out', logout)); root.addWidget(sidebar); root.addWidget(self.stack,1)
        else:
            root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
            top=QFrame(); top.setObjectName('topNav'); top.setFixedHeight(76); top.setStyleSheet('QFrame#topNav { background:#102f60; } QFrame#topNav QLabel { background:transparent; color:white; } QFrame#topNav QPushButton { background:transparent; color:#cbddf4; border-radius:0; padding:16px 18px; } QFrame#topNav QPushButton:checked { color:white; border-bottom:3px solid #ff8a38; }')
            nav=QHBoxLayout(top); nav.setContentsMargins(46,0,46,0); nav.setSpacing(5)
            brand=Brand(); nav.addWidget(brand); nav.addSpacing(42)
            for index,(name,page) in enumerate(pages):
                b=button(name,lambda checked=False,i=index:self.navigate(i)); b.setCheckable(True); nav.addWidget(b); self.nav_buttons.append(b); self.stack.addWidget(page)
            nav.addStretch(); profile=label('●   '+user['name']); nav.addWidget(profile); nav.addWidget(button('Sign out',logout)); root.addWidget(top); root.addWidget(self.stack,1)
        self.booking_page=BookingPage(self) if not self.admin else None
        if self.booking_page: self.stack.addWidget(self.booking_page)
        self.navigate(0)

    def page(self, title, subtitle):
        w=QWidget(); layout=QVBoxLayout(w); layout.setContentsMargins(42,36,42,32); layout.setSpacing(15)
        layout.addWidget(label(title,'title')); layout.addWidget(label(subtitle,'subtitle')); layout.addSpacing(8); return w,layout

    def overview_page(self):
        if not self.admin: return self.customer_home()
        w,l=self.page('Your journey starts here.' if not self.admin else 'A view from the tower.', 'Welcome back, '+self.user['name'].split()[0]+'. Make yourself at home.')
        hero=SkyPanel(compact=True); h=QVBoxLayout(hero); h.setContentsMargins(34,28,34,28)
        a=label('YOUR NEXT ADVENTURE  /  01' if not self.admin else 'FLIGHT OPERATIONS  /  01'); a.setStyleSheet('color:#e0eadb; font-size:10px; font-weight:700; background:transparent;'); h.addWidget(a); h.addStretch()
        b=label('Go somewhere\nthat moves you.' if not self.admin else 'Good journeys\nstart here.','hero'); b.setStyleSheet('font-family: Georgia; font-size: 38px; font-weight:700; color:#fff9ec; background:transparent;'); h.addWidget(b)
        c=label('A new favourite place is just a flight away.' if not self.admin else 'A little clarity for every journey.'); c.setStyleSheet('color:#eff4e9; background:transparent; font-size:13px;'); h.addWidget(c); l.addWidget(hero)
        row=QHBoxLayout(); row.setSpacing(14)
        info=QFrame(); info.setStyleSheet('background:#fffefa; border:1px solid #e1e8df; border-radius:14px;'); il=QVBoxLayout(info); il.setContentsMargins(22,18,22,18)
        tag=label('YOUR TRIPWALA', 'subtitle'); tag.setStyleSheet('color:#91a296; font-size:10px; font-weight:700; background:transparent; border:0;'); il.addWidget(tag)
        self.stats=label(''); self.stats.setWordWrap(True); self.stats.setStyleSheet('font-size:16px; font-weight:700; color:#294639; background:transparent; border:0;'); il.addWidget(self.stats); row.addWidget(info,3)
        action=QFrame(); action.setObjectName('actionCard'); action.setStyleSheet('QFrame#actionCard { background:#e2eadb; border-radius:14px; }'); al=QVBoxLayout(action); al.setContentsMargins(20,16,20,16)
        al.addWidget(label('READY WHEN YOU ARE', 'subtitle')); al.addWidget(button('Manage flights  →' if self.admin else 'Explore flights  →', lambda:self.navigate(1))); row.addWidget(action,2); l.addLayout(row)
        note=label('A considered way to get from here to there.'); note.setStyleSheet('color:#96a49a; font-family:Georgia; font-size:15px;'); l.addWidget(note); l.addStretch(); return w

    def customer_home(self):
        w=QWidget(); w.setStyleSheet('background:#eef3fa;'); l=QVBoxLayout(w); l.setContentsMargins(55,35,55,30); l.setSpacing(16)
        welcome=QHBoxLayout(); a=QVBoxLayout(); a.addWidget(label('Let’s find your next flight.', 'title')); a.addWidget(label('Good to see you, '+self.user['name'].split()[0]+'. Where are you headed?', 'subtitle')); welcome.addLayout(a); welcome.addStretch(); v=label('FLIGHTS  /  ONE WAY'); v.setStyleSheet('color:#6584aa; font-weight:800; font-size:11px;'); welcome.addWidget(v); l.addLayout(welcome)
        form=QFrame(); form.setObjectName('bookingForm'); form.setStyleSheet('QFrame#bookingForm { background:white; border:1px solid #dbe4ef; border-radius:18px; }'); fl=QVBoxLayout(form); fl.setContentsMargins(25,22,25,23); fl.setSpacing(15)
        tabs=QHBoxLayout(); trip=label('●  One way'); trip.setStyleSheet('color:#1563d4; font-weight:800; font-size:14px; background:transparent;'); tabs.addWidget(trip); tabs.addStretch(); note=label('Domestic flights  •  Economy'); note.setStyleSheet('color:#7f8fa4; background:transparent;'); tabs.addWidget(note); fl.addLayout(tabs)
        fields=QHBoxLayout(); fields.setSpacing(0); self.home_origin=field('City or airport code'); self.home_destination=field('City or airport code'); self.home_date=QDateEdit(QDate.currentDate()); self.home_date.setCalendarPopup(True); self.home_date.setDisplayFormat('dd MMM yyyy'); self.home_date_enabled=QCheckBox('Choose date')
        for title,widget in [('FROM',self.home_origin),('TO',self.home_destination),('DEPARTURE',self.home_date)]:
            box=QFrame(); box.setObjectName('bookingField'); box.setStyleSheet('QFrame#bookingField { background:#f8faff; border:1px solid #e0e8f3; } QLineEdit, QDateEdit { background:transparent; border:0; padding:5px 0; color:#1c3153; font-size:16px; font-weight:700; }'); v=QVBoxLayout(box); v.setContentsMargins(18,15,18,15); t=label(title); t.setStyleSheet('color:#8c9bad; font-size:10px; font-weight:800; background:transparent;'); v.addWidget(t); v.addWidget(widget); fields.addWidget(box,2 if title!='DEPARTURE' else 1)
        fl.addLayout(fields); bottom=QHBoxLayout(); bottom.addWidget(self.home_date_enabled); detail=label('Leave unchecked to see all dates'); detail.setStyleSheet('background:transparent; color:#8b99ab;'); bottom.addWidget(detail); bottom.addStretch(); search=button('SEARCH FLIGHTS  →',self.home_search); search.setStyleSheet('background:#ff8733; color:white; border-radius:9px; padding:15px 34px; font-weight:800; font-size:14px;'); bottom.addWidget(search); fl.addLayout(bottom); l.addWidget(form)
        header=QHBoxLayout(); heading=label('Discover popular routes'); heading.setStyleSheet('font-size:21px; font-weight:800; color:#1a3152;'); header.addWidget(heading); header.addStretch(); header.addWidget(button('See all flights  →',lambda:self.navigate(1),'secondary')); l.addLayout(header)
        routes=QHBoxLayout(); routes.setSpacing(14)
        for origin,dest,caption,subtitle,color in [('DEL','BOM','New Delhi to Mumbai','The city that never slows down','#d7e9fa'),('BLR','HYD','Bengaluru to Hyderabad','Food, culture and city lights','#e3e1f6'),('GOI','COK','Goa to Kochi','Your coastal escape awaits','#e1f2ec')]:
            card=QFrame(); card.setObjectName('popular'); card.setStyleSheet('QFrame#popular { background:white; border:1px solid #dce5f0; border-radius:14px; }'); c=QVBoxLayout(card); c.setContentsMargins(0,0,0,12); c.setSpacing(5)
            art=TravelArtwork(dest); c.addWidget(art)
            text=label(caption); text.setStyleSheet('background:transparent; color:#1b3151; font-size:15px; font-weight:800; padding:4px 14px;'); c.addWidget(text)
            description=label(subtitle); description.setStyleSheet('background:transparent; color:#8796aa; padding:0 14px;'); c.addWidget(description)
            go=button('View flights  →',lambda checked=False,o=origin,d=dest:self.route_search(o,d),'secondary'); go.setStyleSheet('background:transparent; color:#1765cf; text-align:left; padding:8px 14px;'); c.addWidget(go); routes.addWidget(card)
        l.addLayout(routes); self.stats=label(''); self.stats.setStyleSheet('color:#8191a6; font-size:12px;'); l.addWidget(self.stats); l.addStretch(); return w

    def home_search(self):
        self.date_filter.setChecked(self.home_date_enabled.isChecked()); self.search_date.setDate(self.home_date.date()); self.route_search(self.home_origin.text().strip(),self.home_destination.text().strip())

    def route_search(self,origin,destination):
        self.origin.setText(origin); self.destination.setText(destination); self.navigate(1)

    def flights_page(self):
        w,l=self.page('Manage flights' if self.admin else 'Choose your flight', 'Create and update schedules.' if self.admin else 'Compare fares and pick the flight that works for you.')
        filters=QHBoxLayout(); self.origin=field('From · city or airport'); self.destination=field('To · city or airport'); filters.addWidget(self.origin); filters.addWidget(self.destination)
        self.date_filter=QCheckBox('Date'); self.date_filter.setToolTip('Filter by departure date'); filters.addWidget(self.date_filter)
        self.search_date=QDateEdit(QDate.currentDate()); self.search_date.setCalendarPopup(True); self.search_date.setDisplayFormat('dd MMM yyyy'); filters.addWidget(self.search_date)
        filters.addWidget(button('Search flights',self.refresh_flights)); filters.addWidget(button('Clear',self.clear_search,'secondary')); l.addLayout(filters)
        self.flight_hint=label('','subtitle'); l.addWidget(self.flight_hint)
        if self.admin:
            self.flight_table=table(['FLIGHT','ROUTE','DEPARTURE','ARRIVAL','STATUS','SEATS','PRICE']); l.addWidget(self.flight_table,1)
            actions=QHBoxLayout(); actions.addStretch(); actions.addWidget(button('Add flight', self.add_flight)); actions.addWidget(button('Set delay', self.delay_flight,'secondary')); actions.addWidget(button('Cancel flight', self.cancel_flight,'danger')); l.addLayout(actions)
        else:
            scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame); scroll.setStyleSheet('QScrollArea { background:transparent; border:0; }')
            content=QWidget(); content.setStyleSheet('background:transparent;'); self.results_layout=QVBoxLayout(content); self.results_layout.setContentsMargins(0,0,8,0); self.results_layout.setSpacing(10); self.results_layout.addStretch(); scroll.setWidget(content); l.addWidget(scroll,1)
        return w

    def flight_card(self,r):
        card=QFrame(); card.setObjectName('flightCard'); card.setStyleSheet('QFrame#flightCard { background:white; border:1px solid #e0e7f1; border-radius:13px; } QLabel { background:transparent; }'); layout=QHBoxLayout(card); layout.setContentsMargins(20,16,20,16); layout.setSpacing(16)
        airline=QVBoxLayout(); name=label(r['airline']); name.setStyleSheet('font-size:15px; font-weight:800; color:#1a2e49;'); airline.addWidget(name); airline.addWidget(label(r['flight_number'],'subtitle')); layout.addLayout(airline,2)
        dep=QVBoxLayout(); t=label(r['departure'].strftime('%H:%M')); t.setStyleSheet('font-size:22px; font-weight:800; color:#17243c;'); dep.addWidget(t); dep.addWidget(label(r['origin_code']+'  ·  '+r['departure'].strftime('%d %b'),'subtitle')); layout.addLayout(dep,1)
        duration=r['arrival']-r['departure']; mins=int(duration.total_seconds()//60); mid=QVBoxLayout(); mid.addWidget(label(f'{mins//60}h {mins%60:02}m','subtitle')); mid.addWidget(label('──────  ✈  ──────','subtitle')); mid.addWidget(label('Non-stop','subtitle')); layout.addLayout(mid,2)
        arr=QVBoxLayout(); t=label(r['arrival'].strftime('%H:%M')); t.setStyleSheet('font-size:22px; font-weight:800; color:#17243c;'); arr.addWidget(t); arr.addWidget(label(r['destination_code']+'  ·  '+r['arrival'].strftime('%d %b'),'subtitle')); layout.addLayout(arr,1)
        price=QVBoxLayout(); amount=label(money(r['price'])); amount.setStyleSheet('font-size:21px; font-weight:800; color:#182d49;'); price.addWidget(amount); price.addWidget(label('per passenger','subtitle')); layout.addLayout(price,1)
        right=QVBoxLayout(); book=button('BOOK',lambda checked=False,fid=r['id']:self.book_flight(fid)); book.setStyleSheet('background:#1264d5; color:white; border-radius:8px; padding:12px 20px; font-weight:800;'); right.addWidget(book); status=r['status']+(f" +{r['delay_minutes']}m" if r['delay_minutes'] else ''); right.addWidget(label(f"{status} · {r['available']} seats",'subtitle')); layout.addLayout(right,1)
        return card

    def bookings_page(self):
        w,l=self.page('All bookings' if self.admin else 'Your trips', 'A record of passenger reservations.' if self.admin else 'All your upcoming plans, in one place.')
        self.booking_table=table(['BOOKING','PASSENGER','FLIGHT','ROUTE','DEPARTURE','SEATS','TOTAL','STATUS']); l.addWidget(self.booking_table,1)
        actions=QHBoxLayout(); actions.addWidget(label('Select a booking to manage it.','muted')); actions.addStretch()
        if not self.admin: actions.addWidget(button('Cancel booking',self.cancel_booking,'danger'))
        actions.addWidget(button('Refresh',self.refresh_bookings,'secondary')); l.addLayout(actions); return w

    def safe(self, fn):
        try: fn()
        except (Error, ValueError) as e: QMessageBox.warning(self,'Unable to complete action',str(e))

    def navigate(self,index):
        self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.nav_buttons): b.setChecked(i==index)
        self.safe([self.refresh_stats,self.refresh_flights,self.refresh_bookings][index])

    def tick(self):
        try:
            self.db.simulate()
            if self.stack.currentIndex() < 3: [self.refresh_stats,self.refresh_flights,self.refresh_bookings][self.stack.currentIndex()]()
        except Error: pass

    def refresh_stats(self):
        flights=self.db.query("SELECT COUNT(*) AS n FROM flights WHERE departure>NOW() AND status <> 'Cancelled'")[0]['n']
        bookings=self.db.bookings(None if self.admin else self.user['id']); active=sum(b['status']=='Confirmed' for b in bookings)
        self.stats.setText(f'{flights} upcoming flights     •     {active} confirmed bookings')

    def clear_search(self): self.origin.clear(); self.destination.clear(); self.date_filter.setChecked(False); self.refresh_flights()
    def refresh_flights(self):
        if self.admin:
            rows=self.db.query("SELECT f.*, f.total_seats-COALESCE(SUM(CASE WHEN b.status='Confirmed' THEN b.seats ELSE 0 END),0) AS available FROM flights f LEFT JOIN bookings b ON f.id=b.flight_id WHERE (f.origin_city LIKE %s OR f.origin_code LIKE %s) AND (f.destination_city LIKE %s OR f.destination_code LIKE %s) GROUP BY f.id ORDER BY f.departure DESC LIMIT 200", tuple([f'%{self.origin.text().strip()}%']*2+[f'%{self.destination.text().strip()}%']*2))
        else: rows=self.db.flights(self.origin.text().strip(),self.destination.text().strip(), self.search_date.date().toPython() if self.date_filter.isChecked() else None)
        if self.admin and self.date_filter.isChecked(): rows=[r for r in rows if r['departure'].date()==self.search_date.date().toPython()]
        snapshot = repr(rows)
        if snapshot == self._flight_snapshot: return
        self._flight_snapshot = snapshot
        if self.admin:
            selected = selected_id(self.flight_table)
            fill(self.flight_table,[(r['id'],[r['flight_number']+'  ·  '+r['airline'], r['origin_code']+'  →  '+r['destination_code'],dt(r['departure']),dt(r['arrival']),r['status']+(f" +{r['delay_minutes']}m" if r['delay_minutes'] else ''),r['available'],money(r['price'])]) for r in rows])
            if selected is not None:
                for index in range(self.flight_table.rowCount()):
                    if self.flight_table.item(index,0).data(Qt.ItemDataRole.UserRole)==selected: self.flight_table.selectRow(index); break
        else:
            while self.results_layout.count():
                item=self.results_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            for r in rows: self.results_layout.addWidget(self.flight_card(r))
            if not rows: self.results_layout.addWidget(label('No flights found. Try another route or date.', 'subtitle'))
            self.results_layout.addStretch()
        self.flight_hint.setText(f'{len(rows)} flights found' + (' · select a flight to manage it' if self.admin else ' · prices per passenger'))

    def refresh_bookings(self):
        rows=self.db.bookings(None if self.admin else self.user['id'])
        snapshot=repr(rows)
        if snapshot == self._booking_snapshot: return
        self._booking_snapshot=snapshot
        selected=selected_id(self.booking_table)
        fill(self.booking_table,[(r['id'],[f"FD-{r['id']:05}",r['name'],r['flight_number'],r['origin_code']+'  →  '+r['destination_code'],dt(r['departure']),r['seats'],money(r['total_price']),r['status']+' / '+r['flight_status']]) for r in rows])
        if selected is not None:
            for index in range(self.booking_table.rowCount()):
                if self.booking_table.item(index,0).data(Qt.ItemDataRole.UserRole)==selected: self.booking_table.selectRow(index); break

    def book_flight(self, fid=None):
        if fid is None: return
        def action():
            rows=self.db.query('SELECT * FROM flights WHERE id=%s', (fid,))
            if not rows: raise ValueError('This flight is no longer available.')
            self.booking_page.open_flight(rows[0]); self.stack.setCurrentWidget(self.booking_page)
            for b in self.nav_buttons: b.setChecked(False)
        self.safe(action)

    def cancel_booking(self):
        bid=selected_id(self.booking_table)
        if bid is None: QMessageBox.information(self,'Select a booking','Choose a booking first.'); return
        if QMessageBox.question(self,'Cancel booking','Cancel this booking?') != QMessageBox.StandardButton.Yes: return
        self.safe(lambda:(self.db.cancel_booking(bid,self.user['id']),self.refresh_bookings()))

    def add_flight(self):
        dialog=FlightDialog(self)
        if dialog.exec(): self.safe(lambda:(self.db.execute('INSERT INTO flights (flight_number,airline,origin_code,origin_city,destination_code,destination_city,departure,arrival,price,total_seats) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',dialog.values),self.refresh_flights()))

    def delay_flight(self):
        fid=selected_id(self.flight_table)
        if fid is None: QMessageBox.information(self,'Select a flight','Choose a flight first.'); return
        minutes,ok=QInputDialog.getInt(self,'Update delay','Delay in minutes (0 clears delay):',0,0,1440)
        if ok: self.safe(lambda:(self.db.execute("UPDATE flights SET delay_minutes=%s, delay_locked=TRUE, delay_checked=TRUE WHERE id=%s AND status NOT IN ('Cancelled','Departed','Arrived')",(minutes,fid)),self.db.simulate(),self.refresh_flights()))

    def cancel_flight(self):
        fid=selected_id(self.flight_table)
        if fid is None: QMessageBox.information(self,'Select a flight','Choose a flight first.'); return
        if QMessageBox.question(self,'Cancel flight','Cancel this flight? Existing bookings will show the flight as cancelled.') != QMessageBox.StandardButton.Yes: return
        self.safe(lambda:(self.db.execute("UPDATE flights SET status='Cancelled' WHERE id=%s AND status NOT IN ('Departed','Arrived')",(fid,)),self.refresh_flights()))


class MainWindow(QMainWindow):
    def __init__(self,db):
        super().__init__(); self.db=db; self.setWindowTitle('TripWala'); self.setWindowIcon(brand_icon()); self.resize(1300,800); self.setMinimumSize(1050,650); self.auth=Auth(db,self.login); self.setCentralWidget(self.auth); self.timer=QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(2000)
    def tick(self):
        if isinstance(self.centralWidget(), Dashboard): self.centralWidget().tick()
        else:
            try: self.db.simulate()
            except Error: pass
    def login(self,user): self.setCentralWidget(Dashboard(self.db,user,self.signout))
    def signout(self): self.auth=Auth(self.db,self.login); self.setCentralWidget(self.auth)
    def closeEvent(self,event):
        if self.db.connection: self.db.connection.close()
        event.accept()


def run():
    import sys
    app=QApplication(sys.argv); app.setApplicationName('TripWala'); app.setWindowIcon(brand_icon()); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    db = None
    config_path = Path(__file__).resolve().parent.parent / 'mysql.local.json'
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding='utf-8'))
            db = Database(config['host'], config['port'], config['user'], config['password'])
            db.connect(); db.simulate()
        except (Error, OSError, ValueError, TypeError, KeyError) as exc:
            if db and db.connection: db.connection.close()
            db = None
            QMessageBox.warning(None, 'Automatic connection failed', f'Could not connect using mysql.local.json. Enter your MySQL details instead.\n\n{exc}')
    if db is None:
        setup=SetupDialog()
        if not setup.exec(): return
        db = setup.db
    window=MainWindow(db); window.show(); sys.exit(app.exec())
