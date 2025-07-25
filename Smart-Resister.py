import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import random
from datetime import datetime, timedelta
from twilio.rest import Client
import os
import re

# Database setup
conn = sqlite3.connect('db10.db')
cursor = conn.cursor()
cursor.execute(''' 
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY,
    phone_number TEXT,
    name TEXT,
    otp TEXT,
    created_at DATETIME,
    ticket_details TEXT,
    booking_id TEXT,
    num_tickets INTEGER,
    status TEXT DEFAULT 'pending',
    timeslot TEXT,
    seat TEXT,
    college_id TEXT
)
''')
conn.commit()

# Twilio setup
twilio_account_sid = 'acc_sid'
twilio_auth_token = 'auth_token'
twilio_phone_number = 'twilio_number'
client = Client(twilio_account_sid, twilio_auth_token)

# Globals
OTP_VALIDITY_DURATION = 0.5  # minutes
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
OTP_ATTEMPTS_LIMIT = 3

class SmartRegister:
    def __init__(self, root):
        self.root = root
        self.root.title("SmartRegister-College Event Manager")
        self.otp_attempts_remaining = OTP_ATTEMPTS_LIMIT
        self.otp_expiry_time = None
        self.welcome_screen()

    def generate_booking_id(self):
        return f"BK{random.randint(100000, 999999)}"

    def send_otp(self, phone_number):
        otp = str(random.randint(100000, 999999))
        created_at = datetime.now()
        self.otp_expiry_time = created_at + timedelta(minutes=OTP_VALIDITY_DURATION)

        try:
            cursor.execute("DELETE FROM tickets WHERE phone_number=? AND ticket_details IS NULL", (phone_number,))
            cursor.execute("INSERT INTO tickets (phone_number, otp, created_at, status) VALUES (?, ?, ?, 'pending')", (phone_number, otp, created_at))
            conn.commit()

            client.messages.create(
                body=f"Your OTP is {otp}. It is valid for {OTP_VALIDITY_DURATION} minutes.",
                from_=twilio_phone_number,
                to=phone_number
            )
            return otp
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send OTP: {str(e)}")
            return None

    def verify_otp(self, phone_number, entered_otp):
        cursor.execute("SELECT otp, created_at FROM tickets WHERE phone_number=? AND status='pending' ORDER BY created_at DESC LIMIT 1", (phone_number,))
        record = cursor.fetchone()
        if record:
            db_otp, created_at = record
            created_at = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S.%f')
            expiry_time = created_at + timedelta(minutes=OTP_VALIDITY_DURATION)
            if entered_otp == db_otp and datetime.now() < expiry_time:
                self.otp_attempts_remaining = OTP_ATTEMPTS_LIMIT
                return True
            else:
                self.otp_attempts_remaining -= 1
                return False
        return False

    def regenerate_otp(self, phone_number):
        if self.otp_attempts_remaining <= 0:
            messagebox.showwarning("Warning", "No attempts left to regenerate OTP.")
            return

        cursor.execute("DELETE FROM tickets WHERE phone_number=? AND status='pending'", (phone_number,))
        conn.commit()
        otp = self.send_otp(phone_number)
        if otp:
            self.otp_attempts_remaining -= 1
            self.clear_frame()
            messagebox.showinfo("Regenerate OTP", f"New OTP sent. Attempts left: {self.otp_attempts_remaining}.")
            self.verify_otp_screen(phone_number)

    def update_timer(self, label):
        if self.otp_expiry_time and label.winfo_exists():
            remaining_time = self.otp_expiry_time - datetime.now()
            if remaining_time.total_seconds() > 0:
                minutes, seconds = divmod(int(remaining_time.total_seconds()), 60)
                label.config(text=f"Time left: {minutes} minutes {seconds} seconds")
                self.root.after(1000, lambda: self.update_timer(label))
            else:
                label.config(text="OTP expired. Please request a new one.")

    def generate_ticket(self, phone_number, name, timeslot, seat, college_id):
        booking_id = self.generate_booking_id()
        ticket_details = f"""
Booking ID: {booking_id}
Name: {name}
Phone Number: {phone_number}
College ID: {college_id}
Timeslot: {timeslot}
Seat: {seat}
"""
        try:
            cursor.execute("""
                UPDATE tickets 
                SET name=?, ticket_details=?, booking_id=?, num_tickets=?, status='active', timeslot=?, seat=?, college_id=?
                WHERE phone_number=? AND status='pending'
            """, (name, ticket_details, booking_id, 1, timeslot, seat, college_id, phone_number))
            conn.commit()
            self.send_ticket_to_phone(ticket_details, phone_number)
            self.show_ticket_details(ticket_details)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate ticket: {str(e)}")

    def send_ticket_to_phone(self, ticket_details, phone_number):
        try:
            client.messages.create(
                body=f"Your workshop ticket:\n{ticket_details}",
                from_=twilio_phone_number,
                to=phone_number
            )
            messagebox.showinfo("Success", "Ticket sent to your phone.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send ticket: {str(e)}")

    def show_ticket_details(self, ticket_details):
        self.clear_frame()
        frame = tk.Frame(self.root)
        frame.pack(pady=20)
        tk.Label(frame, text="Your Workshop Ticket", font=('Helvetica', 14, 'bold')).pack(pady=10)
        tk.Label(frame, text=ticket_details, justify=tk.LEFT).pack(pady=10)
        tk.Button(frame, text="Main Menu", command=self.handle_logout).pack(pady=10)

    def handle_book_tickets(self):
        self.clear_frame()
        frame = tk.Frame(self.root)
        frame.pack(pady=50)
        tk.Label(frame, text="Enter your phone number:").pack(pady=10)
        phone_entry = tk.Entry(frame)
        phone_entry.insert(0, "+91")
        phone_entry.pack(pady=10)
        tk.Button(frame, text="Request OTP", command=lambda: self.handle_request_otp(phone_entry.get())).pack(pady=10)

    def handle_request_otp(self, phone_number):
        if not phone_number.strip():
            messagebox.showerror("Error", "Enter a phone number")
            return
        otp = self.send_otp(phone_number)
        if otp:
            self.verify_otp_screen(phone_number)

    def verify_otp_screen(self, phone_number):
        self.clear_frame()
        frame = tk.Frame(self.root)
        frame.pack(pady=20)
        tk.Label(frame, text="Enter OTP sent to your phone:").pack(pady=10)
        entry_otp = tk.Entry(frame)
        entry_otp.pack(pady=10)
        tk.Button(frame, text="Verify OTP", command=lambda: self.handle_verify_otp(phone_number, entry_otp.get())).pack(pady=10)
        tk.Button(frame, text="Regenerate OTP", command=lambda: self.regenerate_otp(phone_number)).pack(pady=10)
        time_label = tk.Label(frame, text="")
        time_label.pack(pady=10)
        self.update_timer(time_label)

    def handle_verify_otp(self, phone_number, entered_otp):
        if self.otp_attempts_remaining <= 0:
            messagebox.showerror("Error", "No OTP attempts left.")
            return
        if self.verify_otp(phone_number, entered_otp):
            self.seat_selection(phone_number)
        else:
            self.otp_attempts_remaining -= 1
            messagebox.showerror("Error", f"Invalid OTP. Attempts left: {self.otp_attempts_remaining}")
            if self.otp_attempts_remaining == 0:
                self.regenerate_otp(phone_number)

    def seat_selection(self, phone_number):
        self.clear_frame()
        frame = tk.Frame(self.root)
        frame.pack(pady=20)
        tk.Label(frame, text="Select Your Seat", font=('Helvetica', 14, 'bold')).pack(pady=10)

        seat_frame = tk.Frame(frame)
        seat_frame.pack(pady=10)
        rows, columns = 5, 10
        selected_seats = []
        seat_buttons = {}

        for row in range(rows):
            for col in range(columns):
                seat_id = f"{row+1}{chr(65+col)}"
                is_booked = self.is_seat_booked(seat_id)
                button = tk.Button(
                    seat_frame, text=seat_id, width=4, height=2,
                    bg="red" if is_booked else "lightgray",
                    state="disabled" if is_booked else "normal",
                    command=lambda sid=seat_id: self.toggle_seat(sid, selected_seats, seat_buttons)
                )
                button.grid(row=row, column=col, padx=2, pady=2)
                seat_buttons[seat_id] = button

        tk.Button(frame, text="Confirm", command=lambda: self.handle_ticket_details(phone_number, selected_seats)).pack(pady=10)

    def toggle_seat(self, seat_id, selected_seats, seat_buttons):
        if seat_id in selected_seats:
            selected_seats.remove(seat_id)
            seat_buttons[seat_id].config(bg="lightgray")
        elif len(selected_seats) == 0:
            selected_seats.append(seat_id)
            seat_buttons[seat_id].config(bg="green")
        else:
            messagebox.showwarning("Only One Seat", "Only one seat can be selected.")

    def handle_ticket_details(self, phone_number, selected_seats):
        if len(selected_seats) != 1:
            messagebox.showerror("Error", "Please select exactly one seat.")
            return

        self.clear_frame()
        frame = tk.Frame(self.root)
        frame.pack(pady=20)
        tk.Label(frame, text="Enter your Name:").pack(pady=10)
        name_entry = tk.Entry(frame)
        name_entry.pack(pady=10)

        tk.Label(frame, text="Enter your College ID:").pack(pady=10)
        college_id_entry = tk.Entry(frame)
        college_id_entry.pack(pady=10)

        tk.Label(frame, text="Select Timeslot:").pack(pady=10)
        timeslot_var = tk.StringVar()
        timeslot_dropdown = ttk.Combobox(frame, textvariable=timeslot_var)
        timeslot_dropdown['values'] = ('10:00 AM - 1:00 PM', '2:00 PM - 5:00 PM')
        timeslot_dropdown.pack(pady=10)

        tk.Button(frame, text="Generate Ticket", command=lambda: self.validate_ticket_details(
            phone_number, name_entry.get(), timeslot_var.get(), selected_seats[0], college_id_entry.get()
        )).pack(pady=10)

    def validate_ticket_details(self, phone_number, name, timeslot, seat, college_id):
        if not name.strip() or not re.match(r'^[a-zA-Z\s]+$', name):
            messagebox.showerror("Error", "Invalid name")
            return
        if not college_id.strip() or not re.match(r'^\d{4}-\d{2}-\d{3}-\d{3}$', college_id):
            messagebox.showerror("Error", "Invalid College ID (e.g. 1602-23-737-012)")
            return
        if not timeslot:
            messagebox.showerror("Error", "Please select a timeslot")
            return
        cursor.execute("SELECT 1 FROM tickets WHERE college_id=? AND status='active'", (college_id,))
        if cursor.fetchone():
            messagebox.showerror("Error", "This College ID is already registered.")
            return

        self.generate_ticket(phone_number, name, timeslot, seat, college_id)

    def is_seat_booked(self, seat_id):
        cursor.execute("SELECT 1 FROM tickets WHERE seat LIKE ? AND status='active'", (f"%{seat_id}%",))
        return cursor.fetchone() is not None

    def handle_logout(self):
        self.clear_frame()
        self.welcome_screen()

    def clear_frame(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def welcome_screen(self):
        frame = tk.Frame(self.root)
        frame.pack(pady=50)
        tk.Label(frame, text="SmartRegister-College Event Manager", font=('Helvetica', 16, 'bold')).pack(pady=10)
        tk.Button(frame, text="Register", command=self.handle_book_tickets).pack(pady=10)
        tk.Button(frame, text="Admin Login", command=self.admin_login).pack(pady=10)

    def admin_login(self):
        self.clear_frame()
        frame = tk.Frame(self.root)
        frame.pack(pady=20)
        tk.Label(frame, text="Enter Admin Password:").pack(pady=10)
        entry_password = tk.Entry(frame, show="*")
        entry_password.pack(pady=10)
        tk.Button(frame, text="Login", command=lambda: self.handle_admin_login(entry_password.get())).pack(pady=10)

    def handle_admin_login(self, password):
        if password == ADMIN_PASSWORD:
            self.show_admin_dashboard()
        else:
            messagebox.showerror("Error", "Incorrect password.")

    def show_admin_dashboard(self):
        self.clear_frame()
        frame = tk.Frame(self.root)
        frame.pack(pady=20)
        tk.Label(frame, text="Admin Dashboard", font=('Helvetica', 14, 'bold')).pack(pady=10)
        records = cursor.execute("SELECT * FROM tickets WHERE status='active'").fetchall()

        if not records:
            tk.Label(frame, text="No active registrations").pack(pady=10)
        else:
            for record in records:
                record_frame = tk.Frame(frame)
                record_frame.pack(pady=5, fill='x')
                tk.Label(record_frame, text=f"Booking ID: {record[6]}").pack(side='left', padx=5)
                tk.Label(record_frame, text=f"Name: {record[2]}").pack(side='left', padx=5)
                tk.Label(record_frame, text=f"Phone: {record[1]}").pack(side='left', padx=5)
                tk.Label(record_frame, text=f"College ID: {record[11]}").pack(side='left', padx=5)
                tk.Label(record_frame, text=f"Seat: {record[10]}").pack(side='left', padx=5)
                tk.Label(record_frame, text=f"Timeslot: {record[9]}").pack(side='left', padx=5)

        tk.Button(frame, text="Back", command=self.handle_logout).pack(pady=20)

if __name__ == "__main__":
    root = tk.Tk()
    app = SmartRegister(root)
    root.mainloop()
    conn.close()
