# Deployment Guide for Amadurs Invoices / StoreBliz Client Manager

## Render.com Deployment

### Prerequisites
1. Fork or clone this repository to your GitHub account
2. Create a Render.com account and connect it to your GitHub

### Environment Variables
Set the following environment variables in your Render.com service:

**Required:**
- `SECRET_KEY` - Generate a secure random string (Render can auto-generate this)
- `DATABASE_URL` - PostgreSQL connection string (auto-provided by Render if you add a PostgreSQL service)
- `DATA_DIR` - Set to `/opt/render/project/src/data` (matches the disk mount path)

**Optional (for enhanced features):**
- `CRON_TOKEN` - Secure token for cron job authentication
- `SMTP_HOST` - Email server hostname (if implementing email features)
- `SMTP_PORT` - Email server port (if implementing email features)  
- `SMTP_USER` - Email server username (if implementing email features)
- `SMTP_PASSWORD` - Email server password (if implementing email features)
- `STRIPE_PUBLISHABLE_KEY` - Stripe public key (if implementing payment features)
- `STRIPE_SECRET_KEY` - Stripe secret key (if implementing payment features)

### Cron Jobs Setup
For automated tasks, set up Render Cron Jobs:

1. **Recurring Tasks Cron Job:**
   - URL: `POST https://your-app.onrender.com/internal/run-recurring`
   - Headers: `X-CRON-TOKEN: your-cron-token-value`
   - Schedule: As needed (e.g., daily at midnight: `0 0 * * *`)

2. **Client Reminders Cron Job:**
   - URL: `POST https://your-app.onrender.com/internal/run-reminders`  
   - Headers: `X-CRON-TOKEN: your-cron-token-value`
   - Schedule: As needed (e.g., daily at 9 AM: `0 9 * * *`)

### Database & Storage
- **SQLite**: The app includes SQLite fallback with persistent disk storage at `/data`
- **PostgreSQL**: Recommended for production - add PostgreSQL service in Render
- **File Storage**: PDFs and other files stored in `/data/pdfs` on persistent disk (5GB allocated)

### Health Monitoring
- Health check endpoint: `GET /healthz` returns `"ok"` for service monitoring
- Logs available via Render dashboard with INFO level logging configured

### Deployment Steps
1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Use the provided `render.yaml` configuration or manually configure:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --workers=2 --threads=4 --timeout=120`
   - Add environment variables as listed above
   - Enable persistent disk with mount path `/opt/render/project/src/data`

Your StoreBliz Client Manager will be available at `https://your-service-name.onrender.com`