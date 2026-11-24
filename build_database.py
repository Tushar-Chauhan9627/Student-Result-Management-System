import zipfile
import xml.etree.ElementTree as ET
import hashlib
import json
import os
import sqlite3
import random
import datetime

# Seed for deterministic generation
random.seed(42)

print("Starting student data extraction from Excel...")

with zipfile.ZipFile('Student List with enrollment No. Session 2024-25.xlsx', 'r') as z:
    ss_xml = z.read('xl/sharedStrings.xml')
    ss_root = ET.fromstring(ss_xml)
    shared_strings = [elem.text if elem.text is not None else '' for elem in ss_root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')]
    
    sheet_xml = z.read('xl/worksheets/sheet1.xml')
    sheet_root = ET.fromstring(sheet_xml)
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    
    rows = []
    for row in sheet_root.iter(f'{ns}row'):
        r = []
        for c in row.iter(f'{ns}c'):
            t = c.get('t')
            v = c.find(f'{ns}v')
            val = v.text if v is not None else ''
            if t == 's' and val.isdigit():
                val = shared_strings[int(val)] if int(val) < len(shared_strings) else val
            r.append(val.strip())
        rows.append(r)

headers = rows[0]
raw_students = rows[1:]
print(f"Total rows extracted: {len(raw_students)}")

# Subject templates by course category
COURSE_SUBJECTS = {
    "BCA": [
        ("AI & Intelligent Systems", "BCAAI240101", 4),
        ("Modern Office Automation", "TMUSE240101", 3),
        ("Programming in C", "BCACC240101", 4),
        ("Indian Knowledge Systems", "TMUVA240101", 2),
        ("English & Professional Communication", "EN101", 2)
    ],
    "BCA_SEM2": [
        ("Machine Learning Fundamentals", "BCAAI240201", 4),
        ("Ethical Hacking & Cybersecurity", "BCACS240101", 4),
        ("Data Structures & Algorithms", "BCACC240201", 4),
        ("Entrepreneurship & Innovation", "TMUVA240201", 2),
        ("Environmental Studies", "TMUSE240201", 2)
    ],
    "BTECH_AIML": [
        ("Artificial Intelligence Principles", "CSAI101", 4),
        ("Data Structures with C++", "CS102", 4),
        ("Applied Mathematics & Linear Algebra", "MA101", 4),
        ("Digital Logic & Computer Design", "EC101", 3),
        ("Technical Communication Skills", "EN101", 2)
    ],
    "BTECH_AIML_SEM2": [
        ("Deep Learning & Neural Networks", "CSAI201", 4),
        ("Database Management Systems", "CS202", 4),
        ("Discrete Mathematical Structures", "MA201", 4),
        ("Computer Organization & Architecture", "CS203", 3),
        ("Environmental Science & Sustainability", "EV201", 2)
    ],
    "BTECH_CS": [
        ("Engineering Mathematics I", "MA101", 4),
        ("Physics for Computing", "PH101", 4),
        ("Object-Oriented Programming (C++)", "CS101", 4),
        ("Engineering Mechanics & Workshop", "ME101", 2),
        ("Professional English", "EN101", 2)
    ],
    "BTECH_CS_SEM2": [
        ("Engineering Mathematics II", "MA201", 4),
        ("Data Structures & Analysis", "CS201", 4),
        ("Digital Electronics", "EC201", 4),
        ("Operating Systems Concepts", "CS202", 3),
        ("Environmental Engineering", "EV201", 2)
    ],
    "MCA": [
        ("Advanced Object Oriented Programming (Java)", "MCA101", 4),
        ("Relational DBMS & SQL Architecture", "MCA102", 4),
        ("Advanced Operating Systems & Linux", "MCA103", 4),
        ("Mathematical Foundations of CS", "MCA104", 4),
        ("Software Engineering & Agile Methodologies", "MCA105", 3)
    ],
    "MCA_SEM2": [
        ("Cloud Computing & DevOps", "MCA201", 4),
        ("Full-Stack Web Technologies", "MCA202", 4),
        ("Python for Data Analytics & AI", "MCA203", 4),
        ("Computer Networks & Protocol Security", "MCA204", 4),
        ("Research Methodology & Project", "MCA205", 3)
    ],
    "BSC_ANIM": [
        ("Principles of 2D Animation", "AN101", 4),
        ("Digital Art & Vector Illustration", "AN102", 4),
        ("Typography & Visual Layout", "AN103", 3),
        ("History of Animation & Cinema", "AN104", 3),
        ("English Communication", "EN101", 2)
    ],
    "BSC_ANIM_SEM2": [
        ("3D Modeling & Polygon Texturing", "AN201", 4),
        ("Character Rigging & Anatomy", "AN202", 4),
        ("Cinematic Lighting & Rendering", "AN203", 4),
        ("Digital Audio & Video Compositing", "AN204", 3),
        ("Environmental Studies", "EV201", 2)
    ],
    "MTECH": [
        ("Advanced Algorithm Design & Optimization", "MT101", 4),
        ("High-Performance Computing & Parallel Architecture", "MT102", 4),
        ("Advanced Machine Learning Systems", "MT103", 4),
        ("Cloud Infrastructure & Distributed Systems", "MT104", 4),
        ("Research Seminar & Thesis Formulation", "MT105", 3)
    ]
}

def get_subjects_for_course(c_name, sem_no=1):
    c_upper = c_name.upper()
    if "MCA" in c_upper:
        return COURSE_SUBJECTS["MCA_SEM2"] if sem_no == 2 else COURSE_SUBJECTS["MCA"]
    elif "ANIMATION" in c_upper or "BSC-N-002" in c_upper:
        return COURSE_SUBJECTS["BSC_ANIM_SEM2"] if sem_no == 2 else COURSE_SUBJECTS["BSC_ANIM"]
    elif "ARTIFICIAL INTELLIGENCE" in c_upper or "MACHINE LEARNING" in c_upper or "DATA SCIENCE" in c_upper or "CYBER" in c_upper:
        return COURSE_SUBJECTS["BTECH_AIML_SEM2"] if sem_no == 2 else COURSE_SUBJECTS["BTECH_AIML"]
    elif "M.TECH" in c_upper or "MTECH" in c_upper:
        return COURSE_SUBJECTS["MTECH"]
    elif "B.TECH" in c_upper or "BTECH" in c_upper:
        return COURSE_SUBJECTS["BTECH_CS_SEM2"] if sem_no == 2 else COURSE_SUBJECTS["BTECH_CS"]
    else:
        return COURSE_SUBJECTS["BCA_SEM2"] if sem_no == 2 else COURSE_SUBJECTS["BCA"]

def get_grade(pct):
    if pct >= 90: return ("O", 10, "gO")
    if pct >= 80: return ("A+", 9, "gAp")
    if pct >= 70: return ("A", 8, "gA")
    if pct >= 60: return ("B+", 7, "gBp")
    if pct >= 50: return ("B", 6, "gB")
    if pct >= 40: return ("C", 5, "gC")
    return ("F", 0, "gF")

def hash_pass(pwd, salt):
    return hashlib.sha256((pwd + salt).encode('utf-8')).hexdigest()

def format_excel_dob(raw_val):
    if not raw_val:
        return "2005-01-01"
    try:
        f = float(raw_val)
        dt = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=f)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        s = str(raw_val).strip()
        if len(s) == 8 and s.isdigit():
            return f"{s[4:]}-{s[2:4]}-{s[:2]}"
        return s

def mask_mobile(m):
    digits = ''.join(c for c in str(m) if c.isdigit())
    if len(digits) >= 10:
        return f"+91 {digits[:2]}*** ***{digits[-3:]}"
    elif len(digits) >= 4:
        return f"+91 *** ***{digits[-3:]}"
    return "+91 98*** ***123"

def mask_address(city, state):
    c = str(city).strip().title() if city else "Moradabad"
    s = str(state).strip().upper() if state else "UP"
    return f"{c}, {s}"

# Setup SQLite database
db_path = "students.db"
if os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("""
CREATE TABLE admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL,
    department TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

cur.execute("""
CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no TEXT UNIQUE NOT NULL,
    enrollment_no TEXT,
    app_no TEXT,
    name TEXT NOT NULL,
    father_name TEXT,
    mother_name TEXT,
    course_code TEXT,
    course_name TEXT,
    college_name TEXT,
    academic_year TEXT,
    semester TEXT,
    section TEXT,
    batch TEXT,
    email TEXT,
    phone TEXT,
    guardian_phone TEXT,
    dob TEXT,
    gender TEXT,
    category TEXT,
    city TEXT,
    district TEXT,
    state TEXT,
    address TEXT,
    percentage REAL,
    attendance INTEGER,
    fees_total REAL,
    fees_paid REAL,
    fees_due REAL,
    status TEXT,
    hostel_alloted TEXT,
    room_no TEXT,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    initials TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

cur.execute("""
CREATE TABLE semesters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no TEXT NOT NULL,
    sem_no INTEGER NOT NULL,
    sem_name TEXT NOT NULL,
    attendance INTEGER NOT NULL,
    sgpa REAL NOT NULL,
    credits INTEGER NOT NULL,
    result TEXT NOT NULL,
    FOREIGN KEY(roll_no) REFERENCES students(roll_no)
);
""")

cur.execute("""
CREATE TABLE marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no TEXT NOT NULL,
    sem_no INTEGER NOT NULL,
    subject_code TEXT NOT NULL,
    subject_name TEXT NOT NULL,
    internal INTEGER NOT NULL,
    external INTEGER NOT NULL,
    total INTEGER NOT NULL,
    max_marks INTEGER NOT NULL,
    pct REAL NOT NULL,
    grade TEXT NOT NULL,
    grade_point INTEGER NOT NULL,
    credits INTEGER NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY(roll_no) REFERENCES students(roll_no)
);
""")

cur.execute("""
CREATE TABLE fee_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no TEXT NOT NULL,
    txn_date TEXT NOT NULL,
    fee_type TEXT NOT NULL,
    amount REAL NOT NULL,
    receipt_no TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY(roll_no) REFERENCES students(roll_no)
);
""")

cur.execute("""
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# Insert Admin/Teacher users
admin_salt = "tmu_faculty_salt_2025"
admin_pwd_hash = hash_pass("Teacher@2025", admin_salt)

cur.execute("""
INSERT INTO admin_users (username, full_name, email, role, department, password_hash, salt)
VALUES (?, ?, ?, ?, ?, ?, ?)
""", ("admin", "Dr. Rajesh Sharma (Faculty Master)", "teacher@tmu.ac.in", "Faculty Administrator", "College of Computing Sciences & IT", admin_pwd_hash, admin_salt))

cur.execute("""
INSERT INTO admin_users (username, full_name, email, role, department, password_hash, salt)
VALUES (?, ?, ?, ?, ?, ?, ?)
""", ("dean", "Prof. R.K. Jain (Dean CCSIT)", "dean.ccsit@tmu.ac.in", "Dean Academic Affairs", "College of Computing Sciences & IT", hash_pass("Dean@2025", "tmu_dean_salt"), "tmu_dean_salt"))

cur.execute("""
INSERT INTO audit_logs (user, action, details) VALUES ('SYSTEM', 'INITIALIZATION', 'Admin users and database schemas created successfully')
""")

students_json_store = {}
processed_rolls = set()

# Process each student row
for r in raw_students:
    if len(r) < 73:
        continue
    
    no = r[0] if len(r) > 0 else ""
    enrollment = r[1] if len(r) > 1 else ""
    name = r[2] if len(r) > 2 else ""
    father = r[3] if len(r) > 3 else ""
    course_code = r[4] if len(r) > 4 else ""
    mobile = r[5] if len(r) > 5 else ""
    guardian_mobile = r[6] if len(r) > 6 else ""
    app_no = r[10] if len(r) > 10 else ""
    dob = r[11] if len(r) > 11 else ""
    gender = r[12] if len(r) > 12 else ""
    category = r[13] if len(r) > 13 else "GEN"
    mother = r[18] if len(r) > 18 else ""
    acad_year = r[26] if len(r) > 26 and r[26] else "24-25"
    sem = r[27] if len(r) > 27 and r[27] else "I"
    section = r[28] if len(r) > 28 and r[28] else "A"
    status = r[29] if len(r) > 29 and r[29] else "Student"
    state = r[35] if len(r) > 35 else "UP"
    city = r[36] if len(r) > 36 else "Moradabad"
    address = r[37] if len(r) > 37 else ""
    email = r[38] if len(r) > 38 and r[38] else f"{name.lower().replace(' ', '')}@tmu.ac.in"
    pct_str = r[45] if len(r) > 45 else ""
    course_name = r[60] if len(r) > 60 and r[60] else (course_code if course_code else "B.C.A.")
    batch = r[61] if len(r) > 61 and r[61] else "2024-2027"
    hostel = r[65] if len(r) > 65 else "FALSE"
    room_no = r[88] if len(r) > 88 else ""
    dob_formatted = format_excel_dob(dob)
    # Default password is their DOB (YYYY-MM-DD or DDMMYYYY)
    password = dob_formatted

    # Derive unique Roll Number
    # If enrollment has digits (e.g. TCA2468532 -> 2468532)
    digits = ''.join(c for c in enrollment if c.isdigit())
    if digits and len(digits) >= 5:
        roll_no = digits
    elif no and any(c.isdigit() for c in no):
        roll_no = ''.join(c for c in no if c.isdigit())
    elif enrollment:
        roll_no = enrollment
    else:
        roll_no = f"24{len(processed_rolls)+1000:05d}"
        
    if roll_no in processed_rolls:
        # avoid collision
        roll_no = f"{roll_no}_{len(processed_rolls)}"
    processed_rolls.add(roll_no)

    try:
        pct = float(pct_str) if pct_str else round(random.uniform(58.0, 88.0), 1)
    except:
        pct = round(random.uniform(60.0, 85.0), 1)

    initials = "".join(part[0] for part in name.split() if part)[:2].upper()
    if not initials:
        initials = "ST"

    # Specific preset overrides for existing demo accounts to maintain 100% backward compatibility
    if roll_no == "2468532":
        name = "Sanjay Kumar"
        dob_formatted = "2005-06-01"
        password = "2005-06-01"
        course_name = "BCA"
        section = "C"
    elif roll_no == "2468297":
        name = "Manmohan Singh"
        dob_formatted = "2007-05-27"
        password = "2007-05-27"
        course_name = "BCA"
        section = "C"
    elif roll_no == "2468497":
        name = "Ritik Singh"
        dob_formatted = "2005-08-15"
        password = "2005-08-15"
        course_name = "B.Tech Mechanical"
        section = "A"

    salt = f"salt_{roll_no}_{random.randint(1000, 9999)}"
    pwd_hash = hash_pass(password, salt)

    safe_phone = mask_mobile(mobile)
    safe_guardian = mask_mobile(guardian_mobile)
    safe_address = mask_address(city, state)

    # Attendance & Fees
    attendance = random.randint(76, 95)
    total_fee = 71200 if "BCA" in course_name.upper() else (118000 if "MCA" in course_name.upper() else 145000)
    has_dues = random.choice([True, False, False])
    paid_fee = total_fee - 4000 if has_dues else total_fee
    due_fee = total_fee - paid_fee

    if roll_no == "2468532":
        attendance = 91
        total_fee = 71200
        paid_fee = 67200
        due_fee = 4000
    elif roll_no == "2468297":
        attendance = 82
        total_fee = 118000
        paid_fee = 118000
        due_fee = 0
    elif roll_no == "2468497":
        attendance = 86
        total_fee = 110000
        paid_fee = 80000
        due_fee = 30000

    # Insert into students table
    cur.execute("""
    INSERT INTO students (
        roll_no, enrollment_no, app_no, name, father_name, mother_name,
        course_code, course_name, college_name, academic_year, semester,
        section, batch, email, phone, guardian_phone, dob, gender, category,
        city, district, state, address, percentage, attendance,
        fees_total, fees_paid, fees_due, status, hostel_alloted, room_no,
        password_hash, salt, initials
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        roll_no, enrollment, app_no, name, father, mother,
        course_code, course_name, "College of Computing Sciences & IT, TMU", acad_year, sem,
        section, batch, email, safe_phone, safe_guardian, dob_formatted, gender, category,
        city.strip().title() if city else "Moradabad", city.strip().title() if city else "Moradabad", state.strip().upper() if state else "UP", safe_address, pct, attendance,
        total_fee, paid_fee, due_fee, status, hostel, room_no,
        pwd_hash, salt, initials
    ))

    # Generate Semester 1 (and Semester 2 for some)
    num_sems = 2 if roll_no in ["2468532", "2468497"] or random.random() > 0.4 else 1
    semesters_data = []

    for s_idx in range(1, num_sems + 1):
        sem_name = f"Semester {s_idx}"
        sem_att = attendance if s_idx == num_sems else random.randint(78, 94)
        subs = get_subjects_for_course(course_name, s_idx)
        
        sub_list = []
        tot_pts = 0
        tot_cr = 0
        all_passed = True

        for sname, scode, cr in subs:
            base_score = pct / 100.0
            int_marks = int(max(18, min(39, round(base_score * 40 + random.randint(-4, 3)))))
            ext_marks = int(max(24, min(59, round(base_score * 60 + random.randint(-6, 4)))))
            tot = int_marks + ext_marks
            sub_pct = (tot / 100.0) * 100.0
            g, gp, cls = get_grade(sub_pct)
            passed = sub_pct >= 40
            if not passed: all_passed = False

            tot_pts += gp * cr
            tot_cr += cr

            cur.execute("""
            INSERT INTO marks (
                roll_no, sem_no, subject_code, subject_name, internal, external,
                total, max_marks, pct, grade, grade_point, credits, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                roll_no, s_idx, scode, sname, int_marks, ext_marks,
                tot, 100, round(sub_pct, 1), g, gp, cr, "Pass" if passed else "Fail"
            ))

            sub_list.append({
                "name": sname, "code": scode, "int": int_marks, "ext": ext_marks,
                "max": 100, "credits": cr, "grade": g, "gp": gp, "cls": cls
            })

        sgpa = round(tot_pts / tot_cr, 2) if tot_cr else 7.5
        res_str = "PASS" if all_passed else "BACKLOG"

        cur.execute("""
        INSERT INTO semesters (
            roll_no, sem_no, sem_name, attendance, sgpa, credits, result
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (roll_no, s_idx, sem_name, sem_att, sgpa, tot_cr, res_str))

        semesters_data.append({
            "name": sem_name,
            "subjects": sub_list,
            "attendance": sem_att,
            "sgpa": sgpa
        })

    # Fee transactions
    txns = []
    t1_amt = round(total_fee * 0.45)
    t2_amt = round(total_fee * 0.45)
    t3_amt = total_fee - t1_amt - t2_amt

    txns.append({"date": "10 Jul 2024", "type": "Tuition Fee Installment 1", "amount": t1_amt, "status": "Paid", "receipt": f"REC-24-{random.randint(1000, 9999)}"})
    txns.append({"date": "15 Jul 2024", "type": "Lab & Library Development", "amount": t2_amt, "status": "Paid", "receipt": f"REC-24-{random.randint(1000, 9999)}"})
    
    if due_fee == 0:
        txns.append({"date": "10 Jan 2025", "type": "Tuition Fee Installment 2", "amount": t3_amt, "status": "Paid", "receipt": f"REC-25-{random.randint(1000, 9999)}"})
    else:
        txns.append({"date": "20 Feb 2025", "type": "Outstanding Examination & Tuition Fee", "amount": due_fee, "status": "Pending", "receipt": "—"})

    for t in txns:
        cur.execute("""
        INSERT INTO fee_transactions (roll_no, txn_date, fee_type, amount, receipt_no, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (roll_no, t["date"], t["type"], t["amount"], t["receipt"], t["status"]))

    # Add to in-memory JSON structure for fast client-side query / fallback
    students_json_store[roll_no] = {
        "roll": roll_no,
        "enrollment": enrollment,
        "name": name,
        "initials": initials,
        "course": course_name,
        "course_code": course_code,
        "batch": batch,
        "section": section,
        "email": email,
        "phone": safe_phone,
        "dob": dob_formatted,
        "gender": gender,
        "category": category,
        "city": city.strip().title() if city else "Moradabad",
        "state": state.strip().upper() if state else "UP",
        "address": safe_address,
        "attendance": attendance,
        "status": status,
        "percentage": pct,
        "pwd_hash": pwd_hash,
        "salt": salt,
        "semesters": semesters_data,
        "fees": {
            "total": total_fee,
            "paid": paid_fee,
            "due": due_fee,
            "txns": txns
        }
    }

conn.commit()
print(f"Successfully populated SQLite database with {len(processed_rolls)} students!")
conn.close()

# Save clean data.js for in-browser client execution
enrollment_map = {s["enrollment"]: s["roll"] for s in students_json_store.values() if s.get("enrollment")}
bundle = {
    "admins": [{
        "username": "admin",
        "name": "Dr. Rajesh Sharma (Faculty Master)",
        "email": "teacher@tmu.ac.in",
        "role": "Faculty Administrator",
        "department": "College of Computing Sciences & IT",
        "password_hash": admin_pwd_hash,
        "salt": admin_salt
    }],
    "enrollment_map": enrollment_map,
    "students": students_json_store
}

with open("data.js", "w", encoding="utf-8") as f:
    f.write("// TMU Student Result Management System - Embedded Dataset\n")
    f.write("// Secure SHA-256 password hashes - Zero plaintext passwords\n")
    f.write("window.SRMS_DATA = ")
    f.write(json.dumps(bundle, separators=(',', ':')))
    f.write(";\n")

print(f"Exported data.js successfully (size: {os.path.getsize('data.js') / 1024:.1f} KB)")
