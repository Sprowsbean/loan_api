CREATE TABLE borrowers (
  id        INTEGER PRIMARY KEY,
  full_name TEXT NOT NULL,
  phone     TEXT NOT NULL UNIQUE,
  province  TEXT NOT NULL
);
CREATE TABLE loan_applications (
  id           INTEGER PRIMARY KEY,
  borrower_id  INTEGER NOT NULL REFERENCES borrowers(id),
  amount_usd   INTEGER NOT NULL CHECK (amount_usd BETWEEN 100 AND 5000),
  term_months  INTEGER NOT NULL,
  status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  submitted_at DATE NOT NULL
);
INSERT INTO borrowers VALUES
  (1, 'Sok Dara', '012345678', 'Battambang'),
  (2, 'Chan Sreyneang', '097654321', 'Siem Reap'),
  (3, 'Kim Vuthy', '088112233', 'Battambang'),
  (4, 'Heng Malis', '015998877', 'Kampot');
INSERT INTO loan_applications VALUES
  (101, 1, 1500, 12, 'pending',  '2026-10-01'),
  (102, 2,  800,  6, 'approved', '2026-10-02'),
  (103, 3, 3200, 24, 'pending',  '2026-10-04'),
  (104, 4, 2000, 18, 'rejected', '2026-10-05'),
  (105, 1,  600,  6, 'pending',  '2026-10-08'),
  (106, 4, 1200, 12, 'pending',  '2026-10-10');