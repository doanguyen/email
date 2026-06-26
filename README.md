# Email Marketing

A Django web app for sending email marketing campaigns via the Gmail API. Supports multiple Google accounts, Jinja2-templated emails, CSV contact lists, and background sending via Celery.

## Prerequisites

- Python 3.12
- PostgreSQL
- Redis
- A Google Cloud project with the Gmail API enabled and OAuth 2.0 credentials

## Setup

### 1. Clone and install dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### 2. Configure environment

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | A long random string for Django |
| `DJANGO_DEBUG` | `True` for local dev, `False` in production |
| `DATABASE_URL` | PostgreSQL connection string, e.g. `postgresql://user:pass@localhost/emailmarketing` |
| `CELERY_BROKER_URL` | Redis URL, e.g. `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Redis URL (same as broker is fine) |
| `GOOGLE_OAUTH_REDIRECT_URI` | Must match the redirect URI in your Google Cloud Console, e.g. `http://localhost:8000/accounts/oauth/callback/` |

### 3. Add Google OAuth credentials

Download your OAuth 2.0 client credentials from [Google Cloud Console](https://console.cloud.google.com/) and save the file as `credentials.json` in the project root.

The app requests these Gmail scopes:
- `gmail.send`
- `gmail.labels`
- `gmail.modify`
- `gmail.readonly`

### 4. Run database migrations

```bash
python manage.py migrate
```

### 5. (Optional) Create a superuser for the admin panel

```bash
python manage.py createsuperuser
```

## Running the app

You need three processes running simultaneously.

**Django dev server:**
```bash
python manage.py runserver
```

**Celery worker** (handles background email sending):
```bash
celery -A emailmarketing worker -l info
```

**Redis** (broker — must be running before Celery):
```bash
redis-server
```

The app is now available at [http://localhost:8000](http://localhost:8000).

## Usage

### 1. Add a Google account

From the homepage, click **Add Account**. You will be redirected to Google's OAuth consent screen. After granting permission, the account is saved and listed on the homepage.

If an account's token expires and cannot be refreshed, it is marked as **broken** — simply re-add it to get a fresh token.

### 2. Create a campaign

Click **New Campaign** from the homepage (or select an account first). Fill in the form:

| Field | Description |
|---|---|
| **Campaign name** | A label for your own reference |
| **Subject** | Email subject line. Supports Jinja2 variables (see below) |
| **Label** | Gmail label name applied to all sent emails for this campaign |
| **Body template** | Email body. Supports Jinja2 variables (see below) |
| **Account** | The Google account to send from |
| **Contacts CSV** | Upload a CSV file in the format described below |

Submit the form. The campaign is created immediately and sending starts in the background via Celery.

### 3. Monitor progress

After submitting, you are redirected to the campaign detail page which shows:
- Status: `pending` → `running` → `completed` (or `failed`)
- Progress counters: total contacts, sent, failed
- Per-contact status: `pending`, `sent`, `failed`, or `bounced`

The page polls the status API automatically.

## Templates (Jinja2)

Both the **subject** and **body** fields support Jinja2 syntax. The only supported variable is:

```
{{ first_name }}
```

Example subject:
```
Hi {{ first_name }}, we have an update for you
```

Example body:
```
Hello {{ first_name }},

Thank you for being a valued customer...
```

The app validates that any variables used in the template exist before creating the campaign.

## Contacts CSV format

The CSV must follow the `RRContacts.csv` template. Required columns:

| Column | Description |
|---|---|
| `email` | Recipient email address |
| `first_name` | Used in template rendering |

Additional columns are stored in the `attributes` JSON field and available for future use.

## Project structure

```
emailmarketing/
  accounts/       # Google OAuth account management
  campaigns/      # Campaign and contact models, views, Celery tasks
  common/         # Shared base model (created_at, updated_at)
config/
  django/         # Django settings (base + local)
  settings/       # Celery settings
  urls.py         # Root URL conf
templates/        # Django HTML templates
credentials.json  # Google OAuth client secrets (not committed)
```

## Admin panel

The Django admin is available at `/admin/`. Log in with the superuser you created to manage accounts and campaigns directly.
