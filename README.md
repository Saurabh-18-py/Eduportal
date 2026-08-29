# EduPortal — CBSE Class 9-12 Notes & Mock Tests

Django website: PDF notes + auto-scored MCQ mock tests, with student login (class 9-12).

## Features
- Student signup/login (choose class 9-12 at signup)
- Home → Class → Subject → Chapter → Notes (PDF download)
- Home → Class → Subject → Mock Tests → Take test (MCQ) → Auto-scored result
- "My Results" page to see past attempts
- Django admin to add Subjects, Chapters, Notes (PDF upload), Tests, Questions, Choices

## Setup in Termux

```bash
# 1. Install Python & pip if not already
pkg update && pkg upgrade
pkg install python

# 2. Go to project folder (after you copy/extract these files)
cd eduportal

# 3. Install dependencies
pip install -r requirements.txt

# If Pillow install fails in Termux, run this first:
pkg install libjpeg-turbo
pip install Pillow

# 4. Make migrations & create database
python manage.py makemigrations accounts notes mocktest
python manage.py migrate

# 5. Create an admin account (to upload notes/tests via /admin/)
python manage.py createsuperuser

# 6. Run the server
python manage.py runserver 0.0.0.0:8000
```

Then open in browser: `http://127.0.0.1:8000/`
Admin panel: `http://127.0.0.1:8000/admin/`

## How to add content (as admin)
1. Go to `/admin/`, login with superuser.
2. Add a **Subject** (name, class_level 9-12, board=CBSE).
3. Inside that Subject, add **Chapters**.
4. Inside a Chapter, add **Notes** and upload the PDF file.
5. To add a mock test: create a **Test** linked to a Subject, add **Questions** inside it, and for each Question add 4 **Choices**, marking one as `is_correct`.

## Project structure
```
eduportal/
  eduportal/        -> settings, urls, wsgi
  accounts/         -> signup/login, student profile (class level)
  notes/            -> Subject, Chapter, Note (PDF) + browsing views
  mocktest/         -> Test, Question, Choice, TestAttempt (auto-scoring)
  templates/        -> all HTML templates
  static/css/       -> styling
  media/            -> uploaded PDFs (auto-created)
  core_views.py     -> home page view
  manage.py
```

## Bulk-Generate an Entire Class's Syllabus (One Command)

Instead of running `generate_mcqs` chapter by chapter, this generates every chapter for a class in one go. Class 10 (Science, Mathematics, Social Science - 46 chapters total) is pre-loaded with the official 2026-27 CBSE syllabus.

```bash
python manage.py generate_all_mcqs --class 10 --difficulty hard
```

- Runs through all subjects and chapters, waiting a few seconds between each (`--delay`, default 8s) to respect Groq's free-tier rate limit
- Skips any chapter that already has a test, so it's safe to re-run if it stops partway
- Prints progress as it goes, and a summary of any chapters that failed (network hiccup, rate limit, etc.) so you can retry just those with `generate_mcqs`

**To do just one subject:**
```bash
python manage.py generate_all_mcqs --class 10 --subject "Mathematics" --difficulty hard
```

**Options:**
- `--num` - questions per chapter (default 10)
- `--difficulty` - easy / medium / hard (default: hard)
- `--delay` - seconds between chapters (increase if you hit rate limit errors)

This will take a while (46 chapters &times; ~8-10 seconds each ≈ 8-10 minutes for all of Class 10) - you can leave Termux running in the background.

## AI-Generated Mock Test Questions (Free — using Groq)

Fully automatic, free, no manual copy-paste needed — uses the same Groq AI setup as your TestMyIQ project.

**One-time setup:**
```bash
export GROQ_API_KEY='your-groq-key-here'
```
Add that line to your `~/.bashrc` in Termux so it's set automatically every session:
```bash
echo "export GROQ_API_KEY='your-groq-key-here'" >> ~/.bashrc
source ~/.bashrc
```

**Generate a test:**
```bash
python manage.py generate_mcqs --subject "Science" --chapter "Chemical Reactions and Equations" --class 10 --num 10 --difficulty hard
```

- `--difficulty` can be `easy`, `medium` (default), or `hard`
- This creates the Subject automatically if needed, generates the MCQs, and saves them as a ready-to-attempt Test — instantly live on the site.

Run it again with a different `--chapter`/`--subject`/`--class` for each topic you want covered.

**Note:** These are AI-generated practice questions in the style of past exam papers — not verbatim actual past-year papers.

## Alternative: Manual copy-paste import (if Groq is ever unavailable)

If you ever don't have a working AI key, you can still add questions for free by asking Claude/ChatGPT in your browser and importing the JSON manually:

```bash
python manage.py import_mcqs chapter1_science.json --subject "Science" --class 10 --test-title "Chemical Reactions - Practice Test"
```

See the prompt template and full steps in the project notes, or ask me again if you need this.

## Login System — What's New

- **Login errors**: wrong username/password now shows a clear red error banner instead of silently reloading the blank form.
- **Show/Hide password**: click "Show" next to any password field (login, signup, reset) to reveal what you typed.
- **Forgot Password** (`/accounts/password-reset/`): student enters their email → gets a reset link → sets a new password. Link expires after 1 hour and can only be used once.

### Testing "Forgot Password" locally (Termux)
By default, `EMAIL_BACKEND` is set to the **console backend** — no real email is sent. Instead, when you request a reset, the full email (including the reset link) is printed directly in your `runserver` terminal. Just copy that link into your browser to continue.

### Enabling real password-reset emails (production)
To actually email the reset link (e.g. using a Gmail account with an [App Password](https://myaccount.google.com/apppasswords)):
```bash
export EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
export EMAIL_HOST_USER='youraddress@gmail.com'
export EMAIL_HOST_PASSWORD='your-16-char-app-password'
```
Add these to `~/.bashrc` (like the `GROQ_API_KEY` step above) so they persist. Note: signup's `email` field is currently optional — for password reset to actually reach a student, make sure they enter a real email at signup.

## Permanent File Storage with Cloudinary (Notes & PYQ PDFs)

Uploaded PDFs (Notes, PYQ papers) live in Render's local storage by default, which gets wiped on every redeploy — same problem SQLite had. Cloudinary fixes this for files, the same way Supabase fixed it for the database.

**1. Create a free Cloudinary account** at cloudinary.com. Your dashboard shows three values: **Cloud Name**, **API Key**, **API Secret**.

**2. Add these to Render** (`eduportal` service → Environment tab), three separate variables:
- `CLOUDINARY_CLOUD_NAME` = your cloud name
- `CLOUDINARY_API_KEY` = your API key
- `CLOUDINARY_API_SECRET` = your API secret

**3. Redeploy.** The app automatically switches to Cloudinary for file uploads once these three variables are present (falls back to local storage in Termux, where they aren't set).

**4. Re-upload anything you added before this was set up** — PDFs uploaded while on local storage were on the old (now-wiped) storage and won't carry over automatically. New uploads from now on are permanent.

## Notes
- Currently CBSE only — board field is already there in the Subject model, so adding other boards later just means adding more choices to `BOARD_CHOICES` in `notes/models.py` and running migrations again.
- `DEBUG = True` and `SECRET_KEY` are set for local/dev use only — change both before putting this on the internet.
- This was written without a live Django environment to test against, so if you hit an error while running it in Termux, paste the error back and I'll fix it directly.
