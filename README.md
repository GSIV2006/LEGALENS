# Legal Metrology Compliance Assessment System

**Smart India Hackathon 2026**

Software System to Check Compliance of Packaged Commodities under Legal Metrology (Packaged Commodities) Rules, 2011

## Tech Stack

- Python 3.11+
- FastAPI
- Uvicorn
- SQLAlchemy
- Pydantic
- JWT Authentication (python-jose)
- Password Hashing (bcrypt/passlib)
- SQLite (local development) / PostgreSQL (production)
- ReportLab (PDF reports)
- python-docx (DOCX reports)
- python-multipart (file uploads)

## Project Structure

```
legal_metrology_backend/
├── api/
│   └── index.py              # Vercel deployment entry point
├── app/
│   ├── main.py               # FastAPI application entry
│   ├── config.py             # Configuration from environment
│   ├── database.py           # SQLAlchemy setup
│   ├── models/               # SQLAlchemy models
│   │   ├── user.py
│   │   ├── product.py
│   │   ├── inspection.py
│   │   ├── ocr_data.py
│   │   ├── image.py
│   │   ├── rule.py
│   │   ├── compliance_check.py
│   │   └── audit_log.py
│   ├── schemas/              # Pydantic schemas
│   │   ├── auth.py
│   │   ├── product.py
│   │   ├── inspection.py
│   │   ├── ocr.py
│   │   ├── rule.py
│   │   ├── compliance.py
│   │   ├── report.py
│   │   └── dashboard.py
│   ├── routers/              # API endpoints
│   │   ├── auth.py
│   │   ├── products.py
│   │   ├── inspections.py
│   │   ├── rules.py
│   │   ├── reports.py
│   │   ├── dashboard.py
│   │   └── history.py
│   ├── services/             # Business logic
│   │   ├── ocr_service.py    # OCR integration layer (MOCK)
│   │   ├── storage_service.py # File storage abstraction
│   │   ├── field_extractor.py # Field extraction from OCR
│   │   ├── compliance_engine.py # Compliance checking
│   │   ├── rule_engine.py    # Rule management
│   │   ├── visual_compliance_service.py
│   │   └── report_generator.py # PDF/DOCX generation
│   ├── dependencies/         # FastAPI dependencies
│   │   └── auth.py
│   └── utils/                # Helper functions
│       └── helpers.py
├── uploads/                  # Uploaded images (local dev)
├── tests/                    # Pytest tests
├── scripts/
│   └── seed.py               # Database seed script
├── .env.example
├── .gitignore
├── requirements.txt
├── vercel.json
└── README.md
```

## Quick Start - Local Development

### 1. Create Virtual Environment

```bash
cd legal_metrology_backend
python -m venv venv
```

### 2. Activate Virtual Environment

**Windows:**
```bash
venv\Scripts\activate
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Copy the example environment file and edit if needed:

```bash
cp .env.example .env
```

Default settings work for local development:
- SQLite database: `sqlite:///./legal_metrology.db`
- Development mode
- Local file storage

### 5. Seed the Database

Create tables and seed with sample data:

```bash
python scripts/seed.py
```

This creates:
- Default admin user: `admin@example.com` / `admin123`
- Sample products
- Prototype legal rules

**⚠️ IMPORTANT: Change the admin password in production!**

### 6. Run the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 7. Open API Documentation

Visit:
- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc
- **Health Check:** http://127.0.0.1:8000/health

---

## API Endpoints Overview

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login (OAuth2 password flow) |
| GET | `/auth/me` | Get current user info |

### Products
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/products/` | Create product |
| GET | `/products/` | List products |
| GET | `/products/{id}` | Get product by ID |
| PUT | `/products/{id}` | Update product |
| DELETE | `/products/{id}` | Delete product |
| GET | `/products/search?q=` | Search products |

### Inspections
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/inspections/` | Create inspection |
| GET | `/inspections/` | List inspections (filterable) |
| GET | `/inspections/{id}` | Get inspection with details |
| DELETE | `/inspections/{id}` | Delete inspection |
| POST | `/inspections/{id}/images` | Upload images |
| POST | `/inspections/{id}/ocr-data` | Submit OCR JSON |
| POST | `/inspections/{id}/run-ocr` | Run mock OCR |
| POST | `/inspections/{id}/extract-fields` | Extract fields |
| POST | `/inspections/{id}/check-compliance` | Check compliance |
| POST | `/inspections/{id}/analyze` | Full analysis pipeline |
| POST | `/inspections/{id}/analyze-from-ocr` | Analyze from OCR JSON |
| POST | `/inspections/{id}/checks/{check_id}/override` | Manual override |

### Rules
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/rules/` | Create rule (ADMIN) |
| GET | `/rules/` | List rules |
| GET | `/rules/{id}` | Get rule by ID |
| PUT | `/rules/{id}` | Update rule (ADMIN) |
| DELETE | `/rules/{id}` | Delete rule (ADMIN) |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/reports/{id}/pdf` | Download PDF report |
| GET | `/reports/{id}/docx` | Download DOCX report |

### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard/summary` | Dashboard summary |
| GET | `/dashboard/violations` | Violation statistics |

### History
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/history/` | Search compliance history |
| GET | `/history/{id}/full` | Full inspection details |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |

---

## OCR Integration

The OCR service is a **mock implementation** ready for real OCR integration.

### Current Status
- `app/services/ocr_service.py` contains mock OCR
- Returns sample text data for development
- OCR teammates will replace ONLY the internal implementation

### Expected OCR Output Format
```json
{
    "texts": [
        {
            "text": "MRP ₹120 incl. of all taxes",
            "confidence": 0.97,
            "bbox": [[10,20],[300,20],[300,50],[10,50]],
            "image_name": "back.jpg",
            "page_number": 1
        }
    ]
}
```

### Integration Points
1. Upload images via `/inspections/{id}/images`
2. Run OCR via `/inspections/{id}/run-ocr` (mock for now)
3. OR submit OCR data via `/inspections/{id}/ocr-data`
4. Extract fields via `/inspections/{id}/extract-fields`
5. Check compliance via `/inspections/{id}/check-compliance`

The pipeline continues automatically when real OCR is connected.

---

## Running Tests

```bash
# Activate virtual environment first
pytest tests/ -v
```

Tests cover:
- Authentication (register, login, tokens)
- Products (CRUD operations)
- Inspections (creation, OCR submission, field extraction, compliance)
- Field extraction service
- Compliance engine
- Health endpoint

---

## Deployment

### Local Development
See "Quick Start - Local Development" above.

### Vercel Deployment

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-url>
   git push -u origin main
   ```

2. **Import to Vercel**
   - Go to https://vercel.com
   - Click "New Project"
   - Import your GitHub repository

3. **Configure Environment Variables**
   In Vercel project settings, set:
   - `DATABASE_URL`: PostgreSQL connection string (e.g., from Neon, Supabase)
   - `SECRET_KEY`: Secure random string (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
   - `FRONTEND_URL`: Your frontend URL (e.g., `https://your-app.vercel.app`)
   - `STORAGE_MODE`: Set to `memory` for serverless (or configure S3)
   - `ENVIRONMENT`: `production`

4. **Deploy**
   - Vercel auto-deploys on push to main
   - Or trigger manual deployment from Vercel dashboard

5. **Test Deployment**
   - `https://your-project.vercel.app/health`
   - `https://your-project.vercel.app/docs`

### Storage Configuration

| STORAGE_MODE | Behavior |
|-------------|----------|
| `local` | Saves to `uploads/` folder (development) |
| `memory` | Stores metadata only (serverless prototype) |
| `s3` | External object storage (future integration) |

For production with Vercel, use `STORAGE_MODE=memory` or integrate Supabase Storage / AWS S3.

---

## Environment Variables (.env)

```env
# Database Configuration
DATABASE_URL=sqlite:///./legal_metrology.db
# For production: postgresql://user:password@host:port/dbname

# JWT Configuration
SECRET_KEY=your-super-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Frontend
FRONTEND_URL=http://localhost:3000

# Storage
STORAGE_MODE=local

# Environment
ENVIRONMENT=development
```

### Generating a Secure SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Database

### Local (SQLite)
Default: `sqlite:///./legal_metrology.db`

### Production (PostgreSQL)
Set `DATABASE_URL` to PostgreSQL connection string:
```
postgresql://username:password@hostname:port/database_name
```

Compatible with:
- Neon
- Supabase
- AWS RDS
- Any PostgreSQL provider

---

## Default Users (Development Only)

After running `scripts/seed.py`:

| Email | Password | Role |
|-------|----------|------|
| admin@example.com | admin123 | ADMIN |
| (create your own) | - | - |

**⚠️ WARNING: Change admin password before production deployment!**

---

## Roles

| Role | Permissions |
|------|-------------|
| ADMIN | Full access, manage users/rules |
| INSPECTOR | Create inspections, upload images, run analysis |
| VIEWER | View data only |

---

## Compliance Pipeline

```
Package Images
      ↓
OCR Service (mock → PaddleOCR)
      ↓
Field Extraction (regex-based)
      ↓
Legal Rule Engine (configurable rules)
      ↓
Compliance Engine (PASS/FAIL/MANUAL_REVIEW)
      ↓
Database + PDF/DOCX Reports
```

---

## Limitations & Future Work

1. **OCR**: Currently mock - needs PaddleOCR/OpenCV integration
2. **Visual Compliance**: Font size/readability checking is placeholder
3. **Legal Rules**: Prototype rules need verification by legal team
4. **Storage**: For production, integrate Supabase Storage or S3

---

## License

This project is open-source software for the Smart India Hackathon 2026.

---

## Support

For issues or questions, check:
- API Documentation: `/docs`
- This README
- Code comments in service files
