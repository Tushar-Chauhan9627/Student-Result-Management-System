const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const crypto = require('crypto');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname)));

const db = new sqlite3.Database(path.join(__dirname, 'students.db'), (err) => {
  if (err) console.error('Database connection error:', err.message);
  else console.log('Connected to SQLite students.db successfully.');
});

function sha256(str) {
  return crypto.createHash('sha256').update(str).digest('hex');
}

function normalizeDateVariants(str) {
  if (!str) return [];
  const clean = str.trim();
  const variants = [clean];
  const m1 = clean.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/);
  if (m1) {
    const [_, y, m, d] = m1;
    const mm = m.padStart(2, '0');
    const dd = d.padStart(2, '0');
    variants.push(`${y}-${mm}-${dd}`);
    variants.push(`${dd}${mm}${y}`);
    variants.push(`${dd}-${mm}-${y}`);
    variants.push(`${dd}/${mm}/${y}`);
  }
  const m2 = clean.match(/^(\d{2})(\d{2})(\d{4})$/);
  if (m2) {
    const [_, d, m, y] = m2;
    variants.push(`${y}-${m}-${d}`);
    variants.push(`${d}${m}${y}`);
    variants.push(`${d}-${m}-${y}`);
    variants.push(`${d}/${m}/${y}`);
  }
  const m3 = clean.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/);
  if (m3) {
    const [_, d, m, y] = m3;
    const mm = m.padStart(2, '0');
    const dd = d.padStart(2, '0');
    variants.push(`${y}-${mm}-${dd}`);
    variants.push(`${dd}${mm}${y}`);
    variants.push(`${dd}-${mm}-${y}`);
    variants.push(`${dd}/${mm}/${y}`);
  }
  return [...new Set(variants)];
}

// ── Authentication API ──
app.post('/api/auth/login', (req, res) => {
  const { identifier, password, role } = req.body;
  if (!identifier || !password) {
    return res.status(400).json({ error: 'Missing identifier or password' });
  }

  if (role === 'admin') {
    db.get('SELECT * FROM admin_users WHERE username = ? OR email = ?', [identifier, identifier], (err, admin) => {
      if (err) return res.status(500).json({ error: err.message });
      if (!admin) return res.status(401).json({ error: 'Invalid faculty credentials' });

      const hash = sha256(password + admin.salt);
      if (hash === admin.password_hash) {
        return res.json({
          status: 'success',
          role: 'admin',
          user: { username: admin.username, name: admin.full_name, role: admin.role, department: admin.department }
        });
      }
      return res.status(401).json({ error: 'Invalid faculty credentials' });
    });
  } else {
    db.get('SELECT * FROM students WHERE roll_no = ? OR enrollment_no = ?', [identifier, identifier], (err, student) => {
      if (err) return res.status(500).json({ error: err.message });
      if (!student) return res.status(401).json({ error: 'Student not found' });

      const variants = normalizeDateVariants(password);
      const matched = variants.some(v => sha256(v + student.salt) === student.password_hash);

      if (matched) {
        // Return student record without password hash/salt
        const safeStudent = { ...student };
        delete safeStudent.password_hash;
        delete safeStudent.salt;
        return res.json({ status: 'success', role: 'student', student: safeStudent });
      }
      return res.status(401).json({ error: 'Invalid roll number or password (DOB)' });
    });
  }
});

// ── Unique Roll Check & Student Creation API ──
app.post('/api/student', (req, res) => {
  const { roll_no, name, dob, course_name, section, email, phone, city } = req.body;
  if (!roll_no || !name || !dob) {
    return res.status(400).json({ error: 'roll_no, name, and dob are required' });
  }

  // Enforce unique roll number
  db.get('SELECT roll_no FROM students WHERE roll_no = ?', [roll_no], (err, existing) => {
    if (err) return res.status(500).json({ error: err.message });
    if (existing) {
      return res.status(409).json({ error: `Roll number ${roll_no} already exists. Roll numbers must be unique.` });
    }

    const salt = 'salt_' + roll_no + '_srv';
    const pwd_hash = sha256(dob + salt);
    const enrollment_no = 'TCA' + roll_no;

    db.run(
      `INSERT INTO students (roll_no, enrollment_no, name, dob, course_name, section, email, phone, city, state, attendance, percentage, fees_total, fees_paid, fees_due, status, password_hash, salt)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [roll_no, enrollment_no, name, dob, course_name || 'B.C.A.', section || 'A', email || '', phone || '', city || 'Moradabad', 'UP', 85, 75.0, 71200, 71200, 0, 'Student', pwd_hash, salt],
      function(insErr) {
        if (insErr) return res.status(500).json({ error: insErr.message });
        res.status(201).json({ status: 'success', message: 'Student created successfully', roll_no });
      }
    );
  });
});

// ── Teacher: Edit Student Record ──
app.put('/api/student/:roll', (req, res) => {
  const roll = req.params.roll;
  const { name, dob, course_name, section, email, city, attendance, fees_total, fees_paid, fees_due } = req.body;

  db.run(
    `UPDATE students SET name = COALESCE(?, name), dob = COALESCE(?, dob), course_name = COALESCE(?, course_name),
     section = COALESCE(?, section), email = COALESCE(?, email), city = COALESCE(?, city),
     attendance = COALESCE(?, attendance), fees_total = COALESCE(?, fees_total), fees_paid = COALESCE(?, fees_paid),
     fees_due = COALESCE(?, fees_due) WHERE roll_no = ?`,
    [name, dob, course_name, section, email, city, attendance, fees_total, fees_paid, fees_due, roll],
    function(err) {
      if (err) return res.status(500).json({ error: err.message });
      res.json({ status: 'success', changes: this.changes });
    }
  );
});

// ── Teacher: Delete Student Record ──
app.delete('/api/student/:roll', (req, res) => {
  const roll = req.params.roll;
  db.run('DELETE FROM marks WHERE roll_no = ?', [roll], () => {
    db.run('DELETE FROM fee_transactions WHERE roll_no = ?', [roll], () => {
      db.run('DELETE FROM students WHERE roll_no = ?', [roll], function(err) {
        if (err) return res.status(500).json({ error: err.message });
        res.json({ status: 'success', message: `Student ${roll} and associated records deleted.` });
      });
    });
  });
});

// ── Teacher: Marks Management (Add, Update, Delete) ──
app.post('/api/student/:roll/marks', (req, res) => {
  const roll = req.params.roll;
  const { sem_no, subject_code, subject_name, internal, external, credits, grade, grade_point } = req.body;
  const total = (internal || 0) + (external || 0);

  db.run(
    `INSERT INTO marks (roll_no, sem_no, subject_code, subject_name, internal, external, total, max_marks, pct, grade, grade_point, credits, status)
     VALUES (?, ?, ?, ?, ?, ?, ?, 100, ?, ?, ?, ?, ?)`,
    [roll, sem_no || 1, subject_code, subject_name, internal || 0, external || 0, total, total, grade || 'A', grade_point || 8, credits || 4, total >= 40 ? 'Pass' : 'Fail'],
    function(err) {
      if (err) return res.status(500).json({ error: err.message });
      res.status(201).json({ status: 'success', id: this.lastID });
    }
  );
});

app.put('/api/student/:roll/marks', (req, res) => {
  const roll = req.params.roll;
  const { sem_no, subject_code, subject_name, internal, external, credits, grade, grade_point } = req.body;
  const total = (internal || 0) + (external || 0);

  db.run(
    `UPDATE marks SET subject_name = ?, internal = ?, external = ?, total = ?, grade = ?, grade_point = ?, credits = ?
     WHERE roll_no = ? AND subject_code = ? AND sem_no = ?`,
    [subject_name, internal, external, total, grade, grade_point, credits, roll, subject_code, sem_no],
    function(err) {
      if (err) return res.status(500).json({ error: err.message });
      res.json({ status: 'success', changes: this.changes });
    }
  );
});

app.delete('/api/student/:roll/marks', (req, res) => {
  const roll = req.params.roll;
  const { sem_no, subject_code } = req.body;
  db.run('DELETE FROM marks WHERE roll_no = ? AND subject_code = ? AND sem_no = ?', [roll, subject_code, sem_no], function(err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ status: 'success', changes: this.changes });
  });
});

// ── Student Academic History API ──
app.get('/api/student/:roll/results', (req, res) => {
  const roll = req.params.roll;
  db.all('SELECT * FROM semesters WHERE roll_no = ? ORDER BY sem_no ASC', [roll], (err, semesters) => {
    if (err) return res.status(500).json({ error: err.message });
    db.all('SELECT * FROM marks WHERE roll_no = ? ORDER BY sem_no ASC, subject_code ASC', [roll], (err, marks) => {
      if (err) return res.status(500).json({ error: err.message });
      res.json({ semesters, marks });
    });
  });
});

// ── Admin: List Students (Filtered & Paginated) ──
app.get('/api/admin/students', (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const limit = parseInt(req.query.limit) || 15;
  const offset = (page - 1) * limit;
  const search = req.query.search ? `%${req.query.search}%` : null;
  const course = req.query.course ? `%${req.query.course}%` : null;

  let query = 'SELECT roll_no, enrollment_no, name, course_name, section, email, phone, city, attendance, fees_total, fees_paid, fees_due, status FROM students WHERE 1=1';
  let params = [];

  if (search) {
    query += ' AND (name LIKE ? OR roll_no LIKE ? OR enrollment_no LIKE ? OR city LIKE ?)';
    params.push(search, search, search, search);
  }
  if (course) {
    query += ' AND course_name LIKE ?';
    params.push(course);
  }

  query += ' ORDER BY roll_no ASC LIMIT ? OFFSET ?';
  params.push(limit, offset);

  db.all(query, params, (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    db.get('SELECT COUNT(*) as count FROM students', (err, countRow) => {
      res.json({ total: countRow.count, page, limit, students: rows });
    });
  });
});

// ── Admin: Execute Custom SQL Query ──
app.post('/api/admin/query', (req, res) => {
  const { sql } = req.body;
  if (!sql) return res.status(400).json({ error: 'SQL query required' });

  const start = Date.now();
  const trimmed = sql.trim().toUpperCase();
  if (trimmed.startsWith('SELECT') || trimmed.startsWith('PRAGMA') || trimmed.startsWith('EXPLAIN')) {
    db.all(sql, [], (err, rows) => {
      const elapsed = Date.now() - start;
      if (err) return res.status(400).json({ error: err.message, elapsed });
      res.json({ rows, rowCount: rows.length, elapsed });
    });
  } else {
    db.run(sql, [], function(err) {
      const elapsed = Date.now() - start;
      if (err) return res.status(400).json({ error: err.message, elapsed });
      res.json({ rows: [], rowCount: 0, changes: this.changes, lastID: this.lastID, elapsed });
    });
  }
});

app.listen(PORT, () => {
  console.log(`SRMS Server running on http://localhost:${PORT}`);
});
