"""
Student Management System
Storage backends: CSV | JSON | SQLite (SQL)
Features:
  - Add, update, delete, and search student records
  - Store data using CSV / JSON / SQLite files (switchable at runtime)
  - Sort records by name or marks
  - Admin login authentication
  - Generate reports (topper, average marks, etc.)
  - Exception handling for invalid inputs
"""

import json
import csv
import os
import sqlite3
import hashlib
import getpass
from abc import ABC, abstractmethod
from datetime import datetime

# ─────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────
DATA_FILE_JSON = "students.json"
DATA_FILE_CSV  = "students.csv"
DATA_FILE_SQL  = "students.db"
ADMIN_FILE     = "admin.json"

FIELDS = ["id", "name", "age", "subject", "marks", "grade", "added_on"]

DEFAULT_ADMIN = {
    "username": "admin",
    "password": hashlib.sha256("admin123".encode()).hexdigest()
}

# ─────────────────────────────────────────────
#  Utility Helpers
# ─────────────────────────────────────────────

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def divider(ch="─", w=60):
    print(ch * w)

def header(title: str):
    divider("═")
    print(f"  {title}")
    divider("═")

def pause():
    input("\n  Press Enter to continue...")

def print_table(data: list):
    if not data:
        print("  No records found.")
        return
    print(f"\n  {'ID':<10} {'Name':<20} {'Age':<5} {'Marks':<8} {'Grade':<6} {'Subject':<15} {'Added On'}")
    divider()
    for s in data:
        print(f"  {s['id']:<10} {s['name']:<20} {int(s['age']):<5} "
              f"{float(s['marks']):<8.1f} {s['grade']:<6} {s['subject']:<15} {s['added_on']}")
    print()

# ─────────────────────────────────────────────
#  Storage Backends (Strategy Pattern)
# ─────────────────────────────────────────────


class StorageBackend(ABC):
    """Abstract base class — all backends implement this interface."""

    @abstractmethod
    def load(self) -> list: ...

    @abstractmethod
    def save(self, students: list): ...

    @abstractmethod
    def add(self, student: dict): ...

    @abstractmethod
    def update(self, student: dict): ...

    @abstractmethod
    def delete(self, sid: str): ...

    @property
    @abstractmethod
    def name(self) -> str: ...


# ── 1. JSON Backend ───────────────────────────

class JSONStorage(StorageBackend):
    name = "JSON"

    def load(self) -> list:
        if not os.path.exists(DATA_FILE_JSON):
            return []
        with open(DATA_FILE_JSON, "r") as f:
            return json.load(f)

    def save(self, students: list):
        with open(DATA_FILE_JSON, "w") as f:
            json.dump(students, f, indent=2)

    def add(self, student: dict):
        students = self.load()
        students.append(student)
        self.save(students)

    def update(self, student: dict):
        students = self.load()
        for i, s in enumerate(students):
            if s["id"] == student["id"]:
                students[i] = student
                break
        self.save(students)

    def delete(self, sid: str):
        self.save([s for s in self.load() if s["id"] != sid])


# ── 2. CSV Backend ────────────────────────────

class CSVStorage(StorageBackend):
    name = "CSV"

    def load(self) -> list:
        if not os.path.exists(DATA_FILE_CSV):
            return []
        with open(DATA_FILE_CSV, "r", newline="") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            row["age"]   = int(row["age"])
            row["marks"] = float(row["marks"])
        return rows

    def save(self, students: list):
        with open(DATA_FILE_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            if students:
                writer.writerows(students)

    def add(self, student: dict):
        students = self.load()
        students.append(student)
        self.save(students)

    def update(self, student: dict):
        students = self.load()
        for i, s in enumerate(students):
            if s["id"] == student["id"]:
                students[i] = student
                break
        self.save(students) 

    def delete(self, sid: str):
        self.save([s for s in self.load() if s["id"] != sid])


# ── 3. SQLite Backend ─────────────────────────

class SQLiteStorage(StorageBackend):
    name = "SQLite"

    def __init__(self):
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(DATA_FILE_SQL)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id       TEXT PRIMARY KEY,
                    name     TEXT NOT NULL,
                    age      INTEGER NOT NULL,
                    subject  TEXT NOT NULL,
                    marks    REAL NOT NULL,
                    grade    TEXT NOT NULL,
                    added_on TEXT NOT NULL
                )
            """)
            conn.commit()

    def load(self) -> list:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM students ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def save(self, students: list):
        """Bulk replace — used for imports."""
        with self._connect() as conn:
            conn.execute("DELETE FROM students")
            conn.executemany(
                "INSERT INTO students VALUES (:id,:name,:age,:subject,:marks,:grade,:added_on)",
                students
            )
            conn.commit()

    def add(self, student: dict):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO students VALUES (:id,:name,:age,:subject,:marks,:grade,:added_on)",
                student
            )
            conn.commit()

    def update(self, student: dict):
        with self._connect() as conn:
            conn.execute(
                """UPDATE students SET name=:name, age=:age, subject=:subject,
                   marks=:marks, grade=:grade WHERE id=:id""",
                student
            )
            conn.commit()

    def delete(self, sid: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM students WHERE id=?", (sid,))
            conn.commit()

    # ── SQL-specific queries ──────────────────

    def search_by_name(self, query: str) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM students WHERE LOWER(name) LIKE ?",
                (f"%{query.lower()}%",)
            ).fetchall()
        return [dict(r) for r in rows]

    def search_by_subject(self, query: str) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM students WHERE LOWER(subject) LIKE ?",
                (f"%{query.lower()}%",)
            ).fetchall()
        return [dict(r) for r in rows]

    def top_n(self, n: int) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM students ORDER BY marks DESC LIMIT ?", (n,)
            ).fetchall()
        return [dict(r) for r in rows]

    def subject_averages(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT subject, AVG(marks) as avg_marks, COUNT(*) as total "
                "FROM students GROUP BY subject ORDER BY avg_marks DESC"
            ).fetchall()
        return [(r["subject"], r["avg_marks"], r["total"]) for r in rows]

    def above_average(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM students WHERE marks > (SELECT AVG(marks) FROM students) "
                "ORDER BY marks DESC"
            ).fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────
#  Admin Authentication
# ─────────────────────────────────────────────

class AdminAuth:
    def __init__(self):
        self._load()

    def _load(self):
        if not os.path.exists(ADMIN_FILE):
            with open(ADMIN_FILE, "w") as f:
                json.dump(DEFAULT_ADMIN, f, indent=2)
        with open(ADMIN_FILE, "r") as f:
            self.creds = json.load(f)

    def login(self) -> bool:
        header("Admin Login")
        for attempt in range(3):
            username = input("  Username: ").strip()
            try:
                password = getpass.getpass("  Password: ")
            except Exception:
                password = input("  Password: ")

            if (username == self.creds["username"] and
                    hash_password(password) == self.creds["password"]):
                print("\n  ✔  Login successful!\n")
                return True
            left = 2 - attempt
            if left:
                print(f"  ✘  Invalid credentials. {left} attempt(s) left.\n")
        print("  ✘  Too many failed attempts.\n")
        return False

    def change_password(self, new_pw: str):
        self.creds["password"] = hash_password(new_pw)
        with open(ADMIN_FILE, "w") as f:
            json.dump(self.creds, f, indent=2)
        print("  ✔  Password updated.")


# ─────────────────────────────────────────────
#  Student Manager
# ─────────────────────────────────────────────

class StudentManager:
    def __init__(self, backend: StorageBackend):
        self.db = backend

    def _all(self) -> list:
        return self.db.load()

    def _find_by_id(self, sid: str):
        return next((s for s in self._all() if s["id"] == sid), None)

    def _next_id(self) -> str:
        students = self._all()
        if not students:
            return "STU001"
        nums = [int(s["id"].replace("STU", "")) for s in students]
        return f"STU{max(nums) + 1:03d}"

    @staticmethod
    def _grade(marks: float) -> str:
        if marks >= 90: return "A+"
        if marks >= 80: return "A"
        if marks >= 70: return "B"
        if marks >= 60: return "C"
        if marks >= 50: return "D"
        return "F"

    @staticmethod
    def _validate_name(name: str) -> str:
        name = name.strip()
        if not name:
            raise ValueError("Name cannot be empty.")
        if not all(c.isalpha() or c.isspace() for c in name):
            raise ValueError("Name must contain only letters and spaces.")
        return name.title()

    @staticmethod
    def _validate_marks(value: str) -> float:
        m = float(value)
        if not (0 <= m <= 100):
            raise ValueError("Marks must be between 0 and 100.")
        return m

    # ── CRUD ──────────────────────────────────

    def add_student(self):
        header("Add Student")
        try:
            name    = self._validate_name(input("  Name    : "))
            age     = int(input("  Age     : "))
            if not (5 <= age <= 100):
                raise ValueError("Age must be between 5 and 100.")
            subject = input("  Subject : ").strip()
            if not subject:
                raise ValueError("Subject cannot be empty.")
            marks   = self._validate_marks(input("  Marks   : "))

            student = {
                "id"      : self._next_id(),
                "name"    : name,
                "age"     : age,
                "subject" : subject.title(),
                "marks"   : marks,
                "grade"   : self._grade(marks),
                "added_on": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            self.db.add(student)
            print(f"\n  ✔  Student added with ID: {student['id']}")
        except ValueError as e:
            print(f"\n  ✘  {e}")

    def update_student(self):
        header("Update Student")
        sid = input("  Student ID: ").strip().upper()
        s   = self._find_by_id(sid)
        if not s:
            print(f"  ✘  No student with ID '{sid}'."); return
        print(f"\n  Editing: {s['name']}  (blank = keep current)\n")
        try:
            n = input(f"  Name    [{s['name']}]: ").strip()
            if n: s["name"] = self._validate_name(n)

            a = input(f"  Age     [{s['age']}]: ").strip()
            if a:
                age = int(a)
                if not (5 <= age <= 100): raise ValueError("Age must be 5–100.")
                s["age"] = age

            sub = input(f"  Subject [{s['subject']}]: ").strip()
            if sub: s["subject"] = sub.title()

            m = input(f"  Marks   [{s['marks']}]: ").strip()
            if m:
                s["marks"] = self._validate_marks(m)
                s["grade"] = self._grade(s["marks"])

            self.db.update(s)
            print(f"\n  ✔  Student '{sid}' updated.")
        except ValueError as e:
            print(f"\n  ✘  {e}")

    def delete_student(self):
        header("Delete Student")
        sid = input("  Student ID to delete: ").strip().upper()
        s   = self._find_by_id(sid)
        if not s:
            print(f"  ✘  No student with ID '{sid}'."); return
        if input(f"  Delete '{s['name']}' ({sid})? [y/N]: ").lower() == "y":
            self.db.delete(sid)
            print(f"  ✔  Deleted '{sid}'.")
        else:
            print("  Cancelled.")

    def search_student(self):
        header("Search Student")
        print("  1) By ID   2) By Name   3) By Subject", end="")
        if isinstance(self.db, SQLiteStorage):
            print("   4) Above Average (SQL)")
        else:
            print()
        choice = input("  Choice: ").strip()
        results = []
        try:
            if choice == "1":
                sid = input("  ID: ").strip().upper()
                s   = self._find_by_id(sid)
                results = [s] if s else []
            elif choice == "2":
                q = input("  Name (partial): ").strip()
                if not q: raise ValueError("Query cannot be empty.")
                if isinstance(self.db, SQLiteStorage):
                    results = self.db.search_by_name(q)
                else:
                    results = [s for s in self._all() if q.lower() in s["name"].lower()]
            elif choice == "3":
                q = input("  Subject: ").strip()
                if not q: raise ValueError("Query cannot be empty.")
                if isinstance(self.db, SQLiteStorage):
                    results = self.db.search_by_subject(q)
                else:
                    results = [s for s in self._all() if q.lower() in s["subject"].lower()]
            elif choice == "4" and isinstance(self.db, SQLiteStorage):
                results = self.db.above_average()
                print("\n  Students scoring above class average (SQL):")
            else:
                print("  ✘  Invalid choice."); return
        except ValueError as e:
            print(f"\n  ✘  {e}"); return

        print(f"\n  {len(results)} record(s) found:")
        print_table(results)

    def view_all(self):
        header(f"All Students  [{self.db.name}]")
        print_table(self._all())

    def sort_records(self):
        header("Sort Records")
        print("  1) Name (A→Z)   2) Marks (Low→High)   3) Marks (High→Low)")
        choice = input("  Choice: ").strip()
        students = self._all()
        if choice == "1":
            res, label = sorted(students, key=lambda s: s["name"]), "Name A → Z"
        elif choice == "2":
            res, label = sorted(students, key=lambda s: float(s["marks"])), "Marks Low → High"
        elif choice == "3":
            res, label = sorted(students, key=lambda s: float(s["marks"]), reverse=True), "Marks High → Low"
        else:
            print("  ✘  Invalid choice."); return
        print(f"\n  Sorted by {label}:")
        print_table(res)

    def generate_report(self):
        header("Report")
        students = self._all()
        if not students:
            print("  No data available."); return

        marks_list = [float(s["marks"]) for s in students]
        avg    = sum(marks_list) / len(marks_list)
        topper = max(students, key=lambda s: float(s["marks"]))
        lowest = min(students, key=lambda s: float(s["marks"]))
        passed = [s for s in students if float(s["marks"]) >= 50]
        failed = [s for s in students if float(s["marks"]) <  50]

        grade_dist: dict = {}
        for s in students:
            grade_dist[s["grade"]] = grade_dist.get(s["grade"], 0) + 1

        print(f"\n  {'Total Students':<30}: {len(students)}")
        print(f"  {'Average Marks':<30}: {avg:.2f}")
        print(f"  {'Highest Marks':<30}: {float(topper['marks']):.1f}  ({topper['name']})")
        print(f"  {'Lowest Marks':<30}: {float(lowest['marks']):.1f}  ({lowest['name']})")
        print(f"  {'Passed (>=50)':<30}: {len(passed)}")
        print(f"  {'Failed (<50)':<30}: {len(failed)}")
        print(f"  {'Pass %':<30}: {len(passed)/len(students)*100:.1f}%")

        divider()
        print("  Grade Distribution:")
        for g in ["A+", "A", "B", "C", "D", "F"]:
            n = grade_dist.get(g, 0)
            print(f"    {g:<4}: {'|' * n}  ({n})")

        divider()
        print("  Subject Averages:")
        if isinstance(self.db, SQLiteStorage):
            for subj, avg_m, total in self.db.subject_averages():
                print(f"    {subj:<20}: {avg_m:.2f}  ({total} student(s))  [SQL AVG()]")
        else:
            subj_map: dict = {}
            for s in students:
                subj_map.setdefault(s["subject"], []).append(float(s["marks"]))
            for subj in sorted(subj_map):
                m = subj_map[subj]
                print(f"    {subj:<20}: {sum(m)/len(m):.2f}  ({len(m)} student(s))")

        if isinstance(self.db, SQLiteStorage):
            divider()
            top5 = self.db.top_n(5)
            print("  Top 5 Students (SQL: ORDER BY marks DESC LIMIT 5):")
            print_table(top5)
        else:
            divider()
            print(f"  Topper: {topper['name']} -- {float(topper['marks']):.1f} ({topper['grade']})")
        print()

    # ── Export ────────────────────────────────

    def export_to(self):
        header("Export Data")
        students = self._all()
        if not students:
            print("  No data to export."); return
        print("  Export to:  1) JSON   2) CSV   3) SQLite")
        choice = input("  Choice: ").strip()
        if choice == "1":
            JSONStorage().save(students)
            print(f"  Exported {len(students)} record(s) to '{DATA_FILE_JSON}'.")
        elif choice == "2":
            CSVStorage().save(students)
            print(f"  Exported {len(students)} record(s) to '{DATA_FILE_CSV}'.")
        elif choice == "3":
            SQLiteStorage().save(students)
            print(f"  Exported {len(students)} record(s) to '{DATA_FILE_SQL}'.")
        else:
            print("  Invalid choice.")

    # ── Import ────────────────────────────────

    def import_from(self):
        header("Import Data")
        print("  Import from:  1) JSON   2) CSV   3) SQLite")
        choice = input("  Choice: ").strip()
        src_map = {"1": (JSONStorage, DATA_FILE_JSON),
                   "2": (CSVStorage,  DATA_FILE_CSV),
                   "3": (SQLiteStorage, DATA_FILE_SQL)}
        if choice not in src_map:
            print("  Invalid choice."); return
        Cls, path = src_map[choice]
        if not os.path.exists(path):
            print(f"  '{path}' not found."); return
        src  = Cls()
        data = src.load()
        if not data:
            print("  Source file is empty."); return
        confirm = input(f"  Import {len(data)} record(s) into [{self.db.name}]? [y/N]: ")
        if confirm.lower() == "y":
            self.db.save(data)
            print(f"  Imported {len(data)} record(s).")
        else:
            print("  Cancelled.")


# ─────────────────────────────────────────────
#  Storage Selection
# ─────────────────────────────────────────────

def choose_backend() -> StorageBackend:
    header("Select Storage Backend")
    print("  1)  JSON    ──  students.json  (human-readable)")
    print("  2)  CSV     ──  students.csv   (spreadsheet-compatible)")
    print("  3)  SQLite  ──  students.db    (SQL queries, relational)")
    divider()
    while True:
        c = input("  Choice [1/2/3]: ").strip()
        if c == "1": return JSONStorage()
        if c == "2": return CSVStorage()
        if c == "3": return SQLiteStorage()
        print("  Enter 1, 2, or 3.")


# ─────────────────────────────────────────────
#  Main Menu
# ─────────────────────────────────────────────

def main_menu(sm: StudentManager, auth: AdminAuth):
    while True:
        clear()
        header(f"Student Management System  [{sm.db.name}]")
        print("  1)  Add Student")
        print("  2)  Update Student")
        print("  3)  Delete Student")
        print("  4)  Search Student")
        print("  5)  View All Students")
        print("  6)  Sort Records")
        print("  7)  Generate Report")
        print("  8)  Export  ──  save to JSON / CSV / SQLite")
        print("  9)  Import  ──  load from JSON / CSV / SQLite")
        print("  P)  Change Admin Password")
        print("  S)  Switch Storage Backend")
        print("  0)  Exit")
        divider()
        choice = input("  Select: ").strip().upper()
        clear()

        actions = {
            "1": sm.add_student,
            "2": sm.update_student,
            "3": sm.delete_student,
            "4": sm.search_student,
            "5": sm.view_all,
            "6": sm.sort_records,
            "7": sm.generate_report,
            "8": sm.export_to,
            "9": sm.import_from,
        }

        if choice in actions:
            actions[choice]()
        elif choice == "P":
            header("Change Password")
            try:
                np1 = getpass.getpass("  New password    : ")
                np2 = getpass.getpass("  Confirm password: ")
                if np1 != np2:
                    print("  Passwords do not match.")
                elif len(np1) < 6:
                    print("  Minimum 6 characters required.")
                else:
                    auth.change_password(np1)
            except Exception:
                print("  Could not read password securely.")
        elif choice == "S":
            backend = choose_backend()
            sm.db   = backend
            print(f"\n  Switched to {backend.name} backend.")
        elif choice == "0":
            print("  Goodbye!\n"); break
        else:
            print("  Invalid option.")

        pause()


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────

def main():
    auth = AdminAuth()
    if not auth.login():
        return
    backend = choose_backend()
    sm = StudentManager(backend)
    main_menu(sm, auth)


if __name__ == "__main__":
    main()
