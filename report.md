# MedSafe Project Architecture and Technologies Report

## Overview
The MedSafe project is a modern, distributed web application designed as an intelligent drug-drug interaction checker tailored specifically for the Algerian market. It features a scalable microservices-style architecture consisting of a React-based frontend, a Django backend for core relational data and user management, and a dedicated high-performance FastAPI microservice (MedSafe API) handling complex machine learning and generative AI tasks.

---

## 1. Frontend (React + Vite)
Located in `frontend/`, this single-page application (SPA) focuses on providing a clean, "Apple-esque" minimalist design with fluid animations and responsive layouts. It caters to multiple roles, including patients checking their medication profiles, and pharmacists performing rapid, dense clinical checks.

### Core Technologies
- **Framework:** React 19, bundled via Vite for extremely fast hot-module replacement and builds.
- **Routing:** React Router v7 with custom `ProtectedRoute` and `AdminRoute` wrappers to handle role-based access.
- **Styling & Theming:** Tailwind CSS v4, PostCSS, and a custom theme provider handling Light/Dark modes.
- **UI Components:** Built using Radix UI primitives (via shadcn/ui framework) and Base UI for accessible, unstyled building blocks.
- **Animations:** Framer Motion and `tw-animate-css` for micro-animations, smooth transitions, and split-screen dynamic effects.
- **Icons & Data Viz:** Lucide React for crisp iconography, Recharts for dashboard analytics, and Ogl for advanced WebGL graphics.
- **API & Auth:** Axios for data fetching and `jwt-decode` for managing SimpleJWT tokens stored locally.

### Key Workflows & Pages
- **Authentication (`Login.jsx`, `Register.jsx`):** Features a split-screen aesthetic with thread-based animations.
- **Pharmacist Mode (`PharmacistMode.jsx`):** A dense, information-forward interface allowing clinicians to quickly input multiple drugs and receive immediate interaction feedback.
- **Patient Dashboard (`Profile.jsx`, `Interactions.jsx`):** Allows patients to view their saved `MedicationProfile` and check new prescriptions against their history.

---

## 2. Backend (Django REST Framework)
Located in `backend/`, this application serves as the primary data persistence layer, authentication provider, and orchestrator. It manages the core entity relationships using a relational database.

### Core Technologies
- **Framework:** Django 5+ and Django REST Framework (DRF).
- **Database:** SQLite3 (development) with Psycopg2 binary installed for seamless production deployment to PostgreSQL.
- **Authentication:** `djangorestframework-simplejwt` handling JWT generation, refresh, and stateless authentication via Bearer tokens.
- **Image Processing/OCR:** Pillow is used for image handling, and the directory includes scripts (`scratch_ocr.py`, `test_ocr.py`) indicating prescription scanning capabilities via Tesseract OCR.

### Data Models (`backend/apis/models.py`)
- **Users:** A custom `User` model inheriting from `AbstractUser` featuring a `role` field (PATIENT, PHARMACIST, ADMIN). Subclasses (`Patient`, `Pharmacist`, `Administrator`) store specific metadata like Wilaya, pharmacy license numbers, and departments.
- **Drugs:** The `Drug` model stores comprehensive localized data, including `registration_number`, `generic_name`, `brand_name`, `form`, `dosage`, and `packaging`.
- **Profiles:** The `MedicationProfile` model maps a `User` to multiple `Drug` instances, enabling historical tracking and automated contraindication checks.

### Exposed Endpoints
- **Auth:** `/api/auth/register/`, `/api/auth/login/`, `/api/auth/refresh/`
- **Users:** `/api/users/`, `/api/auth/profile/`
- **Drugs:** `/api/drugs/`
- **Medication:** `/api/medication-profile/`, `/api/medication-profile/check/`, `/api/medication-profile/scan/`
- **Orchestration:** `/api/interactions/analyze/` (proxies or coordinates requests to the FastAPI microservice).

---

## 3. MedSafe API (FastAPI ML/LLM Microservice)
Located in `medsafe_api/`, this is a dedicated, high-performance Python microservice handling complex clinical logic, predictive machine learning, and AI generation. 

### Core Technologies
- **Framework:** FastAPI running on Uvicorn (ASGI server).
- **Machine Learning:** CatBoost and Scikit-Learn for tabular data prediction.
- **Generative AI:** `llama-cpp-python` allows running the BioMistral model (in GGUF format) locally without relying on external cloud APIs, ensuring patient privacy.
- **Data Engineering:** Pandas and NumPy for high-performance memory operations; RapidFuzz / thefuzz for fuzzy string matching (handling misspellings in drug names).
- **Validation:** Pydantic models ensure strict schema validation for AI inputs/outputs.

### Service Layer Architecture (`medsafe_api/app/services/`)
- `ddinter_service.py`: Loads the massive DDInter database CSVs into memory on startup and handles exact and fuzzy matching of drug pairs.
- `ml_service.py`: If two drugs are not found in the DDInter database, this service utilizes a CatBoost model to predict the likelihood and severity of an interaction based on molecular and structural features.
- `biomistral_service.py`: Generates deep clinical reasoning and specific pharmacological advisories using the locally hosted BioMistral LLM.
- `translation_service.py`: Takes the clinical output and translates it into Algerian Darija to ensure localized patient understanding.
- `interaction_service.py`: Orchestrates the entire pipeline (DDInter -> CatBoost Fallback -> BioMistral -> Translation).

### Exposed Endpoints (`medsafe_api/app/api/routes/`)
- **`/api/analyze`:** The main entry point for interaction checking.
- **`/api/explain` & `/api/conversation`:** Endpoints for deeper clinical explanations and potentially stateful, interactive AI chats.

---

## How It All Ties Together (System Workflow)

1. **User Action:** A Pharmacist enters a list of brand-name drugs in the React frontend (`PharmacistMode.jsx`) and hits "Analyze".
2. **Initial Request:** The frontend makes an Axios call to the Django Backend (`/api/interactions/analyze/`), attaching the user's JWT Bearer token for authentication.
3. **Orchestration:** Django authenticates the user, logs the query for auditing (if needed), and forwards the payload to the MedSafe API utilizing the internal `FASTAPI_BASE` URL (`http://localhost:8001`).
4. **Analysis Pipeline:**
   - The **MedSafe API** receives the payload.
   - It normalizes the names and searches the **DDInter memory store**.
   - If a match is missing, the **CatBoost model** calculates a fallback prediction.
   - The result (known or predicted) is fed into the **BioMistral LLM** to generate a plain-text clinical explanation.
   - The **Translation Service** converts the explanation into Darija.
5. **Response Cascade:** The FastAPI service returns the structured JSON to Django, which passes it back to the React frontend.
6. **UI Render:** The frontend uses Framer Motion to elegantly display the severity cards, clinical advisories, and Darija translations to the user.
