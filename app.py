import os
import logging
import shutil
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from utils import requires_cron
# Removed Twilio import - SMS functionality removed

# Configure production logging
logging.basicConfig(level=logging.INFO)

# Data directory handling
DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "pdfs"), exist_ok=True)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the Flask app
app = Flask(__name__)

# Production configuration
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-once")
app.config["PREFERRED_URL_SCHEME"] = "https"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Apply ProxyFix for production deployment
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Configure the database
database_url = os.environ.get("DATABASE_URL")
if not database_url or "sqlite" in database_url.lower():
    # Use SQLite in DATA_DIR if no DATABASE_URL or if it's a SQLite URL
    database_url = f"sqlite:///{os.path.join(DATA_DIR, 'clients.db')}"
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the database
db.init_app(app)

class ClientWebsite(db.Model):
    """Model for client website data"""
    __tablename__ = 'client_websites'
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, nullable=False, default=1)
    client_name = db.Column(db.String(255), nullable=False)
    client_email = db.Column(db.String(255))
    client_phone = db.Column(db.String(255))
    billing_address = db.Column(db.Text)
    website_url = db.Column(db.String(500))
    date_built = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    cost = db.Column(db.Numeric(10, 2), nullable=False)  # Revenue (what client pays)
    project_cost = db.Column(db.Numeric(10, 2), default=0)  # Actual project costs
    invoice_status = db.Column(db.String(20), nullable=False)
    custom_notes = db.Column(db.Text)
    custom_fields = db.Column(db.Text)
    theme = db.Column(db.String(50), nullable=False, default='default')
    public_token = db.Column(db.String(255))
    sent_at = db.Column(db.DateTime)
    paid_at = db.Column(db.DateTime)
# stripe_session_id removed
    receipt_number = db.Column(db.String(255))
    tax_percent = db.Column(db.Numeric(5, 2))
    line_items = db.Column(db.Text)
    currency_override = db.Column(db.String(10))
    theme_override = db.Column(db.String(50))
    signature_path = db.Column(db.String(500))
    signature_name = db.Column(db.String(255))
    signed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'clientName': self.client_name,
            'clientEmail': self.client_email,
            'clientPhone': self.client_phone,
            'websiteUrl': self.website_url,
            'dateBuilt': self.date_built.strftime('%Y-%m-%d') if self.date_built else None,
            'expiryDate': self.expiry_date.strftime('%Y-%m-%d') if self.expiry_date else None,
            'cost': float(self.cost),
            'projectCost': float(self.project_cost or 0),
            'profitMargin': self.calculate_profit_margin(),
            'invoiceStatus': self.invoice_status,
            'customNotes': self.custom_notes or '',
            'taxPercent': float(self.tax_percent or 0),
            'currency': self.currency_override or 'GBP'
        }
    
    def calculate_profit_margin(self):
        """Calculate profit margin percentage"""
        if not self.cost or float(self.cost) == 0:
            return 0
        
        revenue = float(self.cost)
        project_cost = float(self.project_cost or 0)
        profit = revenue - project_cost
        
        return round((profit / revenue) * 100, 2)
    
    def get_profit_amount(self):
        """Get actual profit amount"""
        revenue = float(self.cost)
        project_cost = float(self.project_cost or 0)
        return round(revenue - project_cost, 2)
    
    @classmethod
    def get_business_analytics(cls):
        """Get comprehensive business intelligence"""
        from datetime import datetime, timedelta
        clients = cls.query.all()
        now = datetime.now()
        
        total_revenue = sum(float(c.cost) for c in clients)
        total_project_costs = sum(float(c.project_cost or 0) for c in clients)
        total_profit = total_revenue - total_project_costs
        
        paid_clients = [c for c in clients if c.invoice_status == 'Paid']
        paid_revenue = sum(float(c.cost) for c in paid_clients)
        paid_project_costs = sum(float(c.project_cost or 0) for c in paid_clients)
        paid_profit = paid_revenue - paid_project_costs
        
        # Client lifetime value calculation
        client_values = {}
        for client in clients:
            name = client.client_name
            if name not in client_values:
                client_values[name] = {
                    'total_revenue': 0,
                    'total_projects': 0,
                    'avg_project_value': 0,
                    'total_profit': 0,
                    'first_project': None,
                    'last_project': None,
                    'avg_profit_margin': 0,
                    'renewal_likelihood': 'Unknown'
                }
            
            client_values[name]['total_revenue'] += float(client.cost)
            client_values[name]['total_projects'] += 1
            client_values[name]['total_profit'] += client.get_profit_amount()
            
            if not client_values[name]['first_project'] or client.created_at < client_values[name]['first_project']:
                client_values[name]['first_project'] = client.created_at
            if not client_values[name]['last_project'] or client.created_at > client_values[name]['last_project']:
                client_values[name]['last_project'] = client.created_at
        
        # Calculate average project values and renewal predictions
        for client_name in client_values:
            cv = client_values[client_name]
            cv['avg_project_value'] = round(cv['total_revenue'] / cv['total_projects'], 2)
            cv['avg_profit_margin'] = round((cv['total_profit'] / cv['total_revenue'] * 100) if cv['total_revenue'] > 0 else 0, 2)
            
            # Simple renewal prediction based on project count and recency
            if cv['total_projects'] >= 3:
                cv['renewal_likelihood'] = 'High'
            elif cv['total_projects'] == 2:
                cv['renewal_likelihood'] = 'Medium'
            else:
                cv['renewal_likelihood'] = 'Low'
        
        # Renewal and expiry predictions
        expiring_soon = []
        renewable_clients = []
        for client in clients:
            if client.expiry_date:
                days_to_expiry = (client.expiry_date - now.date()).days
                if 0 <= days_to_expiry <= 60:  # Expiring within 60 days
                    expiring_soon.append({
                        'client_name': client.client_name,
                        'days_to_expiry': days_to_expiry,
                        'revenue_at_risk': float(client.cost),
                        'profit_at_risk': client.get_profit_amount(),
                        'renewal_likelihood': client_values[client.client_name]['renewal_likelihood']
                    })
                    
                    if days_to_expiry <= 30:  # High priority renewals
                        renewable_clients.append(client.client_name)
        
        # Revenue forecasting (next 3 months)
        monthly_forecast = []
        for i in range(3):
            future_month = now + timedelta(days=30*i)
            month_name = future_month.strftime("%B %Y")
            
            # Predict renewals based on expiry dates and likelihood
            expected_renewals = 0
            expected_revenue = 0
            for client in expiring_soon:
                expiry_month = now + timedelta(days=client['days_to_expiry'])
                if expiry_month.month == future_month.month and expiry_month.year == future_month.year:
                    # Adjust by renewal likelihood
                    likelihood_multiplier = {'High': 0.8, 'Medium': 0.5, 'Low': 0.2}.get(client['renewal_likelihood'], 0.3)
                    expected_renewals += likelihood_multiplier
                    expected_revenue += client['revenue_at_risk'] * likelihood_multiplier
            
            monthly_forecast.append({
                'month': month_name,
                'expected_renewals': round(expected_renewals, 1),
                'expected_revenue': round(expected_revenue, 2),
                'confidence': 'Medium' if expected_renewals > 0 else 'Low'
            })
        
        # Business health metrics
        payment_rate = (len(paid_clients) / len(clients) * 100) if clients else 0
        avg_project_value = total_revenue / len(clients) if clients else 0
        avg_profit_per_project = total_profit / len(clients) if clients else 0
        
        return {
            'total_revenue': round(total_revenue, 2),
            'total_project_costs': round(total_project_costs, 2),
            'total_profit': round(total_profit, 2),
            'overall_profit_margin': round((total_profit / total_revenue * 100) if total_revenue > 0 else 0, 2),
            
            'paid_revenue': round(paid_revenue, 2),
            'paid_profit': round(paid_profit, 2),
            'paid_profit_margin': round((paid_profit / paid_revenue * 100) if paid_revenue > 0 else 0, 2),
            
            'total_projects': len(clients),
            'paid_projects': len(paid_clients),
            'unpaid_projects': len(clients) - len(paid_clients),
            'payment_rate': round(payment_rate, 1),
            
            'avg_project_value': round(avg_project_value, 2),
            'avg_profit_per_project': round(avg_profit_per_project, 2),
            
            # Predictive insights
            'expiring_soon': sorted(expiring_soon, key=lambda x: x['days_to_expiry'])[:10],
            'high_priority_renewals': renewable_clients,
            'revenue_forecast': monthly_forecast,
            
            'client_lifetime_values': dict(sorted(
                client_values.items(), 
                key=lambda x: x[1]['total_revenue'], 
                reverse=True
            )[:10])  # Top 10 clients by revenue
        }
    
    def __repr__(self):
        return f'<ClientWebsite {self.client_name}>'

class BusinessExpense(db.Model):
    __tablename__ = 'business_expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    expense_name = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    receipt_url = db.Column(db.String(500))  # For future receipt uploads
    is_tax_deductible = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'expenseName': self.expense_name,
            'amount': float(self.amount),
            'expenseDate': self.expense_date.strftime('%Y-%m-%d'),
            'category': self.category,
            'description': self.description or '',
            'receiptUrl': self.receipt_url or '',
            'isTaxDeductible': self.is_tax_deductible,
            'createdAt': self.created_at.strftime('%Y-%m-%d')
        }
    
    def __repr__(self):
        return f'<BusinessExpense {self.expense_name}>'

class ClientReminder(db.Model):
    """Model for tracking sent client reminders"""
    __tablename__ = 'client_reminders'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client_websites.id', ondelete='CASCADE'), nullable=False)
    reminder_type = db.Column(db.String(20), nullable=False)  # '60_day', '30_day', '7_day'
    sent_date = db.Column(db.DateTime, default=datetime.utcnow)
    message_content = db.Column(db.Text)
    status = db.Column(db.String(20), default='sent')  # 'sent', 'failed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    client = db.relationship('ClientWebsite', backref='reminders')
    
    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'client_name': self.client.client_name if self.client else '',
            'reminder_type': self.reminder_type,
            'sent_date': self.sent_date.strftime('%Y-%m-%d %H:%M:%S') if self.sent_date else '',
            'message_content': self.message_content or '',
            'status': self.status
        }
    
    def __repr__(self):
        return f'<ClientReminder {self.reminder_type} for {self.client_id}>'

# Smart Renewal Reminder Functions
def generate_reminder_message(client, reminder_type, days_remaining):
    """Generate professional WhatsApp message for different reminder types"""
    
    templates = {
        '60_day': f"""Hello {client.client_name}!

This is a friendly reminder that your project with us expires in {days_remaining} days on {client.expiry_date.strftime('%B %d, %Y')}.

To ensure uninterrupted service, we'd love to discuss renewal options with you.

Would you like to schedule a quick call to explore how we can continue supporting your business?

View your account: https://storebliz.com/client/{client.id}

Best regards,
Adus Michael - IT Consultant
Phone: +447415144247
Email: adusmichael@gmail.com

Reply here to get started!""",

        '30_day': f"""Hi {client.client_name}!

Your project expires in {days_remaining} days ({client.expiry_date.strftime('%B %d, %Y')}).

We want to ensure seamless continuity of your services. Let's discuss renewal options that work best for your business.

Our team is ready to:
- Review your current setup
- Suggest improvements  
- Provide competitive renewal pricing

View your account: https://storebliz.com/client/{client.id}

Ready to secure your renewal?

Best regards,
Adus Michael - IT Consultant
Phone: +447415144247

Let's talk!""",

        '7_day': f"""URGENT: {client.client_name}

Your project expires in just {days_remaining} days on {client.expiry_date.strftime('%B %d, %Y')}.

To avoid any service interruption, we need to finalize your renewal immediately.

Current project value: £{client.cost}

Quick action needed:
1. Confirm renewal interest
2. Review updated terms
3. Process payment

View your account: https://storebliz.com/client/{client.id}

Contact us NOW to secure your services:

Adus Michael - IT Consultant
Phone: +447415144247 (Call/WhatsApp)
Email: adusmichael@gmail.com

Don't let your project lapse!"""
    }
    
    return templates.get(reminder_type, templates['30_day'])

def check_reminder_eligibility():
    """Check which clients need reminders and haven't been contacted yet"""
    from datetime import date, timedelta
    
    now = date.today()
    eligible_clients = []
    
    # Get all clients with upcoming deadlines
    clients = ClientWebsite.query.filter(
        ClientWebsite.expiry_date >= now,
        ClientWebsite.expiry_date <= now + timedelta(days=60)
    ).all()
    
    for client in clients:
        days_to_expiry = (client.expiry_date - now).days
        
        # Determine reminder type needed
        reminder_type = None
        if days_to_expiry <= 7:
            reminder_type = '7_day'
        elif days_to_expiry <= 30:
            reminder_type = '30_day'
        elif days_to_expiry <= 60:
            reminder_type = '60_day'
        
        if reminder_type:
            # Check if reminder already sent
            existing_reminder = ClientReminder.query.filter_by(
                client_id=client.id,
                reminder_type=reminder_type
            ).first()
            
            if not existing_reminder:
                eligible_clients.append({
                    'client': client,
                    'reminder_type': reminder_type,
                    'days_remaining': days_to_expiry,
                    'message': generate_reminder_message(client, reminder_type, days_to_expiry)
                })
    
    return eligible_clients

# Twilio/SMS removed - using WhatsApp Web and Email only

# Create tables
with app.app_context():
    db.create_all()

@app.get("/healthz")
def healthz():
    """Health check endpoint for production deployment"""
    return "ok", 200

@app.route('/')
def index():
    """Serve the main index.html file"""
    with open('index.html', 'r', encoding='utf-8') as f:
        content = f.read()
    return content

@app.route('/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return send_from_directory('.', filename)

# API Routes for database operations
@app.route('/api/clients', methods=['GET'])
def get_clients():
    """Get all client websites"""
    try:
        clients = ClientWebsite.query.order_by(ClientWebsite.created_at.desc()).all()
        return jsonify([client.to_dict() for client in clients])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients', methods=['POST'])
def create_client():
    """Create a new client website"""
    try:
        data = request.get_json()
        
        client = ClientWebsite()
        client.business_id = 1
        client.client_name = data['clientName']
        client.client_email = data.get('clientEmail')
        client.client_phone = data.get('clientPhone')
        client.website_url = data['websiteUrl']
        client.date_built = datetime.strptime(data['dateBuilt'], '%Y-%m-%d').date()
        client.expiry_date = datetime.strptime(data['expiryDate'], '%Y-%m-%d').date()
        client.cost = float(data['cost'])
        client.project_cost = float(data.get('projectCost', 0))
        client.invoice_status = data['invoiceStatus']
        client.custom_notes = data.get('customNotes', '')
        client.tax_percent = float(data.get('taxPercent', 0))
        client.currency_override = data.get('currency', 'GBP')
        client.theme = 'default'
        
        db.session.add(client)
        db.session.commit()
        
        return jsonify(client.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/<int:client_id>', methods=['PUT'])
def update_client(client_id):
    """Update an existing client website"""
    try:
        client = ClientWebsite.query.get_or_404(client_id)
        data = request.get_json()
        
        client.client_name = data['clientName']
        client.client_email = data.get('clientEmail')
        client.client_phone = data.get('clientPhone')
        client.website_url = data['websiteUrl']
        client.date_built = datetime.strptime(data['dateBuilt'], '%Y-%m-%d').date()
        client.expiry_date = datetime.strptime(data['expiryDate'], '%Y-%m-%d').date()
        client.cost = float(data['cost'])
        client.project_cost = float(data.get('projectCost', 0))
        client.invoice_status = data['invoiceStatus']
        client.custom_notes = data.get('customNotes', '')
        client.tax_percent = float(data.get('taxPercent', 0))
        client.currency_override = data.get('currency', 'GBP')
        client.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify(client.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/<int:client_id>', methods=['DELETE'])
def delete_client(client_id):
    """Delete a client website"""
    try:
        client = ClientWebsite.query.get_or_404(client_id)
        db.session.delete(client)
        db.session.commit()
        
        return jsonify({'message': 'Client deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/receipt/<int:client_id>')
def generate_receipt(client_id):
    """Generate a receipt for a paid client"""
    try:
        client = ClientWebsite.query.get_or_404(client_id)
        
        # Only allow receipts for paid clients
        if client.invoice_status != 'Paid':
            return f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Receipt Not Available</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            </head>
            <body class="bg-light">
                <div class="container my-5">
                    <div class="card text-center">
                        <div class="card-body">
                            <i class="fas fa-exclamation-triangle text-warning fa-3x mb-3"></i>
                            <h3>Receipt Not Available</h3>
                            <p class="text-muted">Receipts can only be generated for clients with "Paid" status.</p>
                            <p>Current status: <span class="badge bg-warning">{client.invoice_status}</span></p>
                            <a href="/" class="btn btn-primary">Back to Dashboard</a>
                        </div>
                    </div>
                </div>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/js/all.min.js"></script>
            </body>
            </html>
            """, 200
        
        # Create HTML receipt
        receipt_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Receipt - {client.client_name}</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                .receipt-header {{ background-color: #28a745; color: white; }}
                .receipt-body {{ background-color: #f8fafc; }}
                .editable-field {{ 
                    border: 2px dashed transparent; 
                    padding: 2px 4px; 
                    border-radius: 3px; 
                    transition: all 0.2s ease;
                }}
                .editable-field:hover {{ 
                    border-color: #ffc107; 
                    background-color: rgba(255, 193, 7, 0.1); 
                }}
                .editable-field:focus {{ 
                    outline: none; 
                    border-color: #0d6efd; 
                    background-color: rgba(13, 110, 253, 0.1); 
                }}
                .edit-hint {{
                    position: fixed;
                    top: 10px;
                    right: 10px;
                    background: rgba(40, 167, 69, 0.9);
                    color: white;
                    padding: 8px 12px;
                    border-radius: 5px;
                    font-size: 12px;
                    z-index: 1000;
                    opacity: 0;
                    transition: opacity 0.3s ease;
                }}
                .edit-hint.show {{
                    opacity: 1;
                }}
                .paid-stamp {{
                    position: relative;
                    display: inline-block;
                }}
                .paid-stamp::after {{
                    content: "PAID";
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%) rotate(-15deg);
                    font-size: 3rem;
                    font-weight: bold;
                    color: #28a745;
                    opacity: 0.3;
                    pointer-events: none;
                    z-index: 1;
                }}
                @media print {{ 
                    .no-print {{ display: none; }}
                    .receipt-container {{ box-shadow: none; }}
                    .editable-field {{ border: none !important; background: transparent !important; }}
                    .edit-hint {{ display: none; }}
                }}
            </style>
        </head>
        <body class="receipt-body">
            <!-- Edit Hint -->
            <div class="edit-hint" id="editHint">
                <i class="fas fa-edit me-1"></i>Click any text to edit it
            </div>
            
            <div class="container my-5">
                <div class="receipt-container bg-white rounded shadow-lg p-4 paid-stamp">
                    <!-- Receipt Header -->
                    <div class="receipt-header p-4 rounded-top mb-4">
                        <div class="row">
                            <div class="col-md-6">
                                <h1 contenteditable="true" class="h2 mb-0 editable-field"><i class="fas fa-receipt me-2"></i>RECEIPT</h1>
                                <p contenteditable="true" class="mb-0 editable-field">Payment Confirmation</p>
                            </div>
                            <div class="col-md-6 text-md-end">
                                <h3 contenteditable="true" class="editable-field">Receipt #{client.id:04d}</h3>
                                <p class="mb-0">Date: <span contenteditable="true" class="editable-field">{datetime.now().strftime('%B %d, %Y')}</span></p>
                                <div class="mt-2">
                                    <span contenteditable="true" class="badge bg-success fs-6 editable-field">
                                        <i class="fas fa-check-circle me-1"></i>PAYMENT RECEIVED
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Client Information -->
                    <div class="row mb-4">
                        <div class="col-md-6">
                            <h5 contenteditable="true" class="editable-field"><i class="fas fa-user me-2"></i>Payment From:</h5>
                            <strong contenteditable="true" class="editable-field">{client.client_name}</strong><br>
                            <span contenteditable="true" class="editable-field">Website: <a href="{client.website_url}" target="_blank">{client.website_url}</a></span>
                        </div>
                        <div class="col-md-6 text-md-end">
                            <h5 contenteditable="true" class="editable-field"><i class="fas fa-info-circle me-2"></i>Service Details:</h5>
                            <span contenteditable="true" class="editable-field"><strong>Service Completed:</strong> {client.date_built.strftime('%B %d, %Y')}</span><br>
                            <span contenteditable="true" class="editable-field"><strong>Service Expires:</strong> {client.expiry_date.strftime('%B %d, %Y')}</span><br>
                            <span contenteditable="true" class="editable-field"><strong>Payment Status:</strong> <span class="badge bg-success">Paid in Full</span></span>
                        </div>
                    </div>
                    
                    <!-- Receipt Table -->
                    <div class="table-responsive mb-4">
                        <table class="table table-striped">
                            <thead class="table-success">
                                <tr>
                                    <th>Service Description</th>
                                    <th>Quantity</th>
                                    <th>Rate</th>
                                    <th>Amount Paid</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td><span contenteditable="true" class="editable-field">Professional Services</span><br>
                                        <small class="text-muted"><span contenteditable="true" class="editable-field">Project services for {client.client_name}</span></small>
                                    </td>
                                    <td>1</td>
                                    <td>£{client.cost:.2f}</td>
                                    <td><strong>£{client.cost:.2f}</strong></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    
                    <!-- Total -->
                    <div class="row">
                        <div class="col-md-8"></div>
                        <div class="col-md-4">
                            <table class="table table-sm">
                                <tr>
                                    <td><strong>Subtotal:</strong></td>
                                    <td class="text-end"><strong>£{client.cost:.2f}</strong></td>
                                </tr>
                                {f'''
                                <tr>
                                    <td><strong>VAT ({client.tax_percent:.1f}%):</strong></td>
                                    <td class="text-end"><strong>£{float(client.cost) * float(client.tax_percent or 0) / 100:.2f}</strong></td>
                                </tr>
                                ''' if client.tax_percent and float(client.tax_percent) > 0 else ''}
                                <tr class="table-success">
                                    <td><strong>Total Paid:</strong></td>
                                    <td class="text-end"><strong>£{float(client.cost) + (float(client.cost) * float(client.tax_percent or 0) / 100):.2f}</strong></td>
                                </tr>
                                <tr class="table-success">
                                    <td><strong>Balance Due:</strong></td>
                                    <td class="text-end"><strong>£0.00</strong></td>
                                </tr>
                            </table>
                        </div>
                    </div>
                    
                    {f'''
                    <!-- Custom Notes -->
                    <div class="mt-4 p-3 bg-success bg-opacity-10 rounded">
                        <h6><i class="fas fa-sticky-note me-2"></i>Service Notes:</h6>
                        <p class="mb-0">{client.custom_notes if client.custom_notes else "No additional notes provided."}</p>
                    </div>
                    ''' if client.custom_notes else ''}
                    
                    <!-- Thank You Message - Fully Editable Footer -->
                    <div class="mt-4 p-3 bg-light rounded text-center">
                        <h5 contenteditable="true" class="text-success editable-field"><i class="fas fa-heart me-2"></i>Thank You for Your Payment!</h5>
                        <p contenteditable="true" class="mb-1 editable-field">This receipt confirms that payment has been received in full.</p>
                        <p contenteditable="true" class="mb-1 editable-field">We appreciate your business and look forward to serving you again.</p>
                        <p contenteditable="true" class="mb-0 editable-field"><strong>Payment received on:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
                        
                        <!-- Additional Footer Content - All Editable -->
                        <hr>
                        <div class="row mt-3">
                            <div class="col-md-6 text-start">
                                <h6 contenteditable="true" class="editable-field">Business Information:</h6>
                                <p contenteditable="true" class="mb-1 editable-field">Adus Michael - IT Consultant</p>
                                <p contenteditable="true" class="mb-1 editable-field">Princess Drive, United Kingdom</p>
                                <p contenteditable="true" class="mb-1 editable-field">Liverpool, L12 6QQ</p>
                                <p contenteditable="true" class="mb-0 editable-field">Phone: +447415144247</p>
                            </div>
                            <div class="col-md-6 text-end">
                                <h6 contenteditable="true" class="editable-field">Receipt Information:</h6>
                                <p contenteditable="true" class="mb-1 editable-field">This receipt serves as proof of payment</p>
                                <p contenteditable="true" class="mb-1 editable-field">Keep this for your records</p>
                                <p contenteditable="true" class="mb-1 editable-field">Support: adusmichael@gmail.com</p>
                                <p contenteditable="true" class="mb-0 editable-field">Thank you for choosing our services!</p>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Editing Instructions -->
                    <div class="mt-4 p-2 bg-success bg-opacity-10 rounded no-print">
                        <small class="text-muted">
                            <i class="fas fa-info-circle me-1"></i>
                            <strong>Editing:</strong> Click any text to customize your receipt. Header sections, client information, and footer details are all editable.
                        </small>
                    </div>
                    
                    <!-- Action Buttons -->
                    <div class="mt-4 text-center no-print">
                        <button onclick="window.print()" class="btn btn-success me-2">
                            <i class="fas fa-print"></i> Print Receipt
                        </button>
                        <button onclick="downloadPDF()" class="btn btn-primary me-2">
                            <i class="fas fa-download"></i> Download PDF
                        </button>
                        <a href="mailto:?subject=Receipt%20#{client.id:04d}%20-%20{client.client_name.replace(' ', '%20')}&body=Thank%20you%20for%20your%20payment!%0A%0AYour%20receipt%20is%20available%20at:%20https://storebliz.com/receipt/{client.id}" 
                           class="btn btn-info me-2">
                            <i class="fas fa-envelope"></i> Email Receipt
                        </a>
                        <a href="/" class="btn btn-secondary">
                            <i class="fas fa-arrow-left"></i> Back to Dashboard
                        </a>
                    </div>
                </div>
            </div>
            
            <script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/js/all.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
            <script>
                async function downloadPDF() {{
                    try {{
                        // Hide the action buttons before capturing
                        const actionButtons = document.querySelector('.no-print');
                        actionButtons.style.display = 'none';
                        
                        // Temporarily modify styles for better PDF rendering
                        const originalBodyStyle = document.body.style.cssText;
                        const originalContainerStyle = document.querySelector('.receipt-container').style.cssText;
                        
                        // Apply PDF-optimized styles
                        document.body.style.backgroundColor = '#ffffff';
                        document.body.style.margin = '0';
                        document.body.style.padding = '15px';
                        
                        const receiptContainer = document.querySelector('.receipt-container');
                        receiptContainer.style.maxWidth = '750px';
                        receiptContainer.style.margin = '0 auto';
                        receiptContainer.style.fontSize = '14px';
                        receiptContainer.style.lineHeight = '1.4';
                        
                        // Add bold styling via CSS
                        const style = document.createElement('style');
                        style.textContent = `
                            .receipt-container * {{
                                font-weight: bold !important;
                                -webkit-print-color-adjust: exact !important;
                                print-color-adjust: exact !important;
                            }}
                            .receipt-container h1, .receipt-container h2, .receipt-container h3,
                            .receipt-container h4, .receipt-container h5, .receipt-container h6 {{
                                font-weight: 900 !important;
                            }}
                        `;
                        document.head.appendChild(style);
                        
                        // Wait for style changes to apply
                        await new Promise(resolve => setTimeout(resolve, 200));
                        
                        // Capture with optimized settings
                        const canvas = await html2canvas(receiptContainer, {{
                            scale: 2,
                            useCORS: true,
                            allowTaint: false,
                            backgroundColor: '#ffffff',
                            width: receiptContainer.scrollWidth,
                            height: receiptContainer.scrollHeight,
                            scrollX: 0,
                            scrollY: 0,
                            windowWidth: 1200,
                            windowHeight: 800,
                            logging: false,
                            ignoreElements: function(element) {{
                                return element.classList && element.classList.contains('no-print');
                            }}
                        }});
                        
                        // Restore original styles and remove added style
                        document.body.style.cssText = originalBodyStyle;
                        receiptContainer.style.cssText = originalContainerStyle;
                        if (style && style.parentNode) {{
                            style.parentNode.removeChild(style);
                        }}
                        actionButtons.style.display = 'block';
                        
                        // Create PDF with better sizing
                        const {{ jsPDF }} = window.jspdf;
                        const pdf = new jsPDF({{
                            orientation: 'portrait',
                            unit: 'mm',
                            format: 'a4',
                            putOnlyUsedFonts: true,
                            compress: false
                        }});
                        
                        const imgData = canvas.toDataURL('image/png', 1.0);
                        
                        // Calculate dimensions to maintain aspect ratio and quality
                        const pdfWidth = 210; // A4 width in mm
                        const pdfHeight = 297; // A4 height in mm
                        const canvasAspectRatio = canvas.height / canvas.width;
                        
                        const margin = 15; // Smaller margin for better fit
                        const maxWidth = pdfWidth - (margin * 2);
                        const maxHeight = pdfHeight - (margin * 2);
                        
                        let imgWidth = maxWidth;
                        let imgHeight = imgWidth * canvasAspectRatio;
                        
                        // If content is too tall, scale to fit height
                        if (imgHeight > maxHeight) {{
                            imgHeight = maxHeight;
                            imgWidth = imgHeight / canvasAspectRatio;
                        }}
                        
                        const xOffset = (pdfWidth - imgWidth) / 2;
                        const yOffset = margin;
                        
                        pdf.addImage(imgData, 'PNG', xOffset, yOffset, imgWidth, imgHeight, undefined, 'FAST');
                        
                        // Download the PDF
                        pdf.save('Receipt-{client.id:04d}-{client.client_name.replace(" ", "-")}.pdf');
                        
                    }} catch (error) {{
                        console.error('Error generating PDF:', error);
                        alert('Error generating PDF. Please try using the Print option instead.');
                        
                        // Ensure styles are restored even on error
                        const actionButtons = document.querySelector('.no-print');
                        if (actionButtons) actionButtons.style.display = 'block';
                    }}
                }}
                
                function copyReceiptLink() {{
                    const url = window.location.href;
                    navigator.clipboard.writeText(url).then(() => {{
                        alert('Receipt link copied to clipboard!');
                    }});
                }}
            </script>
        </body>
        </html>
        """
        
        return receipt_html
    except Exception as e:
        return f"Error generating receipt: {str(e)}", 500

@app.route('/invoice/<int:client_id>')
def generate_invoice(client_id):
    """Generate an invoice for a client"""
    try:
        client = ClientWebsite.query.get_or_404(client_id)
        
        # Create HTML invoice
        invoice_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Invoice - {client.client_name}</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                .invoice-header {{ background-color: #2563eb; color: white; }}
                .invoice-body {{ background-color: #f8fafc; }}
                .editable-field {{ 
                    border: 2px dashed transparent; 
                    padding: 2px 4px; 
                    border-radius: 3px; 
                    transition: all 0.2s ease;
                }}
                .editable-field:hover {{ 
                    border-color: #ffc107; 
                    background-color: rgba(255, 193, 7, 0.1); 
                }}
                .editable-field:focus {{ 
                    outline: none; 
                    border-color: #0d6efd; 
                    background-color: rgba(13, 110, 253, 0.1); 
                }}
                .edit-hint {{
                    position: fixed;
                    top: 10px;
                    right: 10px;
                    background: rgba(0, 123, 255, 0.9);
                    color: white;
                    padding: 8px 12px;
                    border-radius: 5px;
                    font-size: 12px;
                    z-index: 1000;
                    opacity: 0;
                    transition: opacity 0.3s ease;
                }}
                .edit-hint.show {{
                    opacity: 1;
                }}
                @media print {{ 
                    .no-print {{ display: none; }}
                    .invoice-container {{ box-shadow: none; }}
                    .editable-field {{ border: none !important; background: transparent !important; }}
                    .edit-hint {{ display: none; }}
                }}
            </style>
        </head>
        <body class="invoice-body">
            <!-- Edit Hint -->
            <div class="edit-hint" id="editHint">
                <i class="fas fa-edit me-1"></i>Click any text to edit it
            </div>
            
            <div class="container my-5">
                <div class="invoice-container bg-white rounded shadow-lg p-4">
                    <!-- Invoice Header -->
                    <div class="invoice-header p-4 rounded-top mb-4">
                        <div class="row">
                            <div class="col-md-6">
                                <h1 contenteditable="true" class="h2 mb-0 editable-field">INVOICE</h1>
                                <p contenteditable="true" class="mb-0 editable-field">Website Development Services</p>
                            </div>
                            <div class="col-md-6 text-md-end">
                                <h3 contenteditable="true" class="editable-field">Invoice #{client.id:04d}</h3>
                                <p class="mb-0">Date: <span contenteditable="true" class="editable-field">{datetime.now().strftime('%B %d, %Y')}</span></p>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Client Information -->
                    <div class="row mb-4">
                        <div class="col-md-6">
                            <h5 contenteditable="true" class="editable-field">Bill To:</h5>
                            <strong contenteditable="true" class="editable-field">{client.client_name}</strong><br>
                            <span contenteditable="true" class="editable-field">Website: <a href="{client.website_url}" target="_blank">{client.website_url}</a></span>
                        </div>
                        <div class="col-md-6 text-md-end">
                            <h5 contenteditable="true" class="editable-field">Project Details:</h5>
                            <span contenteditable="true" class="editable-field"><strong>Built:</strong> {client.date_built.strftime('%B %d, %Y')}</span><br>
                            <span contenteditable="true" class="editable-field"><strong>Expires:</strong> {client.expiry_date.strftime('%B %d, %Y')}</span><br>
                            <span contenteditable="true" class="editable-field"><strong>Status:</strong> <span class="badge bg-{'success' if client.invoice_status == 'Paid' else 'warning'}">{client.invoice_status}</span></span>
                        </div>
                    </div>
                    
                    <!-- Invoice Table -->
                    <div class="table-responsive mb-4">
                        <table class="table table-striped">
                            <thead class="table-dark">
                                <tr>
                                    <th>Description</th>
                                    <th>Quantity</th>
                                    <th>Rate</th>
                                    <th>Amount</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td><span contenteditable="true" class="editable-field">Professional Services</span><br>
                                        <small class="text-muted"><span contenteditable="true" class="editable-field">Project services for {client.client_name}</span></small>
                                    </td>
                                    <td>1</td>
                                    <td>£{client.cost:.2f}</td>
                                    <td>£{client.cost:.2f}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    
                    <!-- Total -->
                    <div class="row">
                        <div class="col-md-8"></div>
                        <div class="col-md-4">
                            <table class="table table-sm">
                                <tr>
                                    <td><strong>Subtotal:</strong></td>
                                    <td class="text-end"><strong>£{client.cost:.2f}</strong></td>
                                </tr>
                                {f'''
                                <tr>
                                    <td><strong>VAT ({client.tax_percent:.1f}%):</strong></td>
                                    <td class="text-end"><strong>£{float(client.cost) * float(client.tax_percent or 0) / 100:.2f}</strong></td>
                                </tr>
                                ''' if client.tax_percent and float(client.tax_percent) > 0 else ''}
                                <tr class="table-primary">
                                    <td><strong>Total Due:</strong></td>
                                    <td class="text-end"><strong>£{float(client.cost) + (float(client.cost) * float(client.tax_percent or 0) / 100):.2f}</strong></td>
                                </tr>
                            </table>
                        </div>
                    </div>
                    
                    {f'''
                    <!-- Custom Notes -->
                    <div class="mt-4 p-3 bg-info bg-opacity-10 rounded">
                        <h6><i class="fas fa-sticky-note me-2"></i>Additional Notes:</h6>
                        <p class="mb-0">{client.custom_notes if client.custom_notes else "No additional notes provided."}</p>
                    </div>
                    ''' if client.custom_notes else ''}
                    
                    <!-- Payment Terms - Fully Editable Footer -->
                    <div class="mt-4 p-3 bg-light rounded">
                        <h6 contenteditable="true" class="editable-field">Payment Terms:</h6>
                        <p contenteditable="true" class="mb-1 editable-field">Payment is due within 30 days of invoice date.</p>
                        <p contenteditable="true" class="mb-1 editable-field">Late payments may be subject to a 1.5% monthly service charge.</p>
                        <p contenteditable="true" class="mb-0 editable-field">Thank you for your business!</p>
                        
                        <!-- Additional Footer Content - All Editable -->
                        <hr>
                        <div class="row mt-3">
                            <div class="col-md-6">
                                <h6 contenteditable="true" class="editable-field">Business Information:</h6>
                                <p contenteditable="true" class="mb-1 editable-field">Adus Michael - IT Consultant</p>
                                <p contenteditable="true" class="mb-1 editable-field">Princess Drive, United Kingdom</p>
                                <p contenteditable="true" class="mb-1 editable-field">Liverpool, L12 6QQ</p>
                                <p contenteditable="true" class="mb-0 editable-field">Phone: +447415144247</p>
                            </div>
                            <div class="col-md-6 text-md-end">
                                <h6 contenteditable="true" class="editable-field">Payment Methods:</h6>
                                <p contenteditable="true" class="mb-1 editable-field"><strong>Bank Transfer:</strong></p>
                                <p contenteditable="true" class="mb-1 editable-field">Account: Adus Michael</p>
                                <p contenteditable="true" class="mb-1 editable-field">Sort Code: 12-34-56</p>
                                <p contenteditable="true" class="mb-1 editable-field">Account No: 12345678</p>
                                <p contenteditable="true" class="mb-1 editable-field">Ref: INV-{client.id:04d}</p>
                                <p contenteditable="true" class="mb-0 editable-field">Support: adusmichael@gmail.com</p>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Editing Instructions -->
                    <div class="mt-4 p-2 bg-warning bg-opacity-10 rounded no-print">
                        <small class="text-muted">
                            <i class="fas fa-info-circle me-1"></i>
                            <strong>Editing:</strong> Click any text to customize your invoice. Header sections, client information, and footer details are all editable.
                        </small>
                    </div>
                    
                    <!-- Payment section removed -->

                    <!-- Action Buttons -->
                    <div class="mt-4 text-center no-print">
                        <button onclick="window.print()" class="btn btn-primary me-2">
                            <i class="fas fa-print"></i> Print Invoice
                        </button>
                        <button onclick="downloadPDF()" class="btn btn-success me-2">
                            <i class="fas fa-download"></i> Download PDF
                        </button>
                        <a href="mailto:?subject=Invoice%20#{client.id:04d}%20-%20{client.client_name.replace(' ', '%20')}&body=Please%20find%20your%20invoice%20attached.%0A%0AInvoice%20Link:%20https://storebliz.com/invoice/{client.id}" 
                           class="btn btn-info me-2">
                            <i class="fas fa-envelope"></i> Email Invoice
                        </a>
                        <a href="/" class="btn btn-secondary">
                            <i class="fas fa-arrow-left"></i> Back to Dashboard
                        </a>
                    </div>
                </div>
            </div>
            
            <script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/js/all.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
            <script>
                async function downloadPDF() {{
                    try {{
                        // Hide the action buttons before capturing
                        const actionButtons = document.querySelector('.no-print');
                        actionButtons.style.display = 'none';
                        
                        // Temporarily modify styles for better PDF rendering
                        const originalBodyStyle = document.body.style.cssText;
                        const originalContainerStyle = document.querySelector('.invoice-container').style.cssText;
                        
                        // Apply PDF-optimized styles
                        document.body.style.backgroundColor = '#ffffff';
                        document.body.style.margin = '0';
                        document.body.style.padding = '15px';
                        
                        const invoiceContainer = document.querySelector('.invoice-container');
                        invoiceContainer.style.maxWidth = '750px';
                        invoiceContainer.style.margin = '0 auto';
                        invoiceContainer.style.fontSize = '14px';
                        invoiceContainer.style.lineHeight = '1.4';
                        
                        // Add bold styling via CSS
                        const style = document.createElement('style');
                        style.textContent = `
                            .invoice-container * {{
                                font-weight: bold !important;
                                -webkit-print-color-adjust: exact !important;
                                print-color-adjust: exact !important;
                            }}
                            .invoice-container h1, .invoice-container h2, .invoice-container h3,
                            .invoice-container h4, .invoice-container h5, .invoice-container h6 {{
                                font-weight: 900 !important;
                            }}
                        `;
                        document.head.appendChild(style);
                        
                        // Wait for style changes to apply
                        await new Promise(resolve => setTimeout(resolve, 200));
                        
                        // Capture with optimized settings
                        const canvas = await html2canvas(invoiceContainer, {{
                            scale: 2,
                            useCORS: true,
                            allowTaint: false,
                            backgroundColor: '#ffffff',
                            width: invoiceContainer.scrollWidth,
                            height: invoiceContainer.scrollHeight,
                            scrollX: 0,
                            scrollY: 0,
                            windowWidth: 1200,
                            windowHeight: 800,
                            logging: false,
                            ignoreElements: function(element) {{
                                return element.classList && element.classList.contains('no-print');
                            }}
                        }});
                        
                        // Restore original styles and remove added style
                        document.body.style.cssText = originalBodyStyle;
                        invoiceContainer.style.cssText = originalContainerStyle;
                        if (style && style.parentNode) {{
                            style.parentNode.removeChild(style);
                        }}
                        actionButtons.style.display = 'block';
                        
                        // Create PDF with better sizing
                        const {{ jsPDF }} = window.jspdf;
                        const pdf = new jsPDF({{
                            orientation: 'portrait',
                            unit: 'mm',
                            format: 'a4',
                            putOnlyUsedFonts: true,
                            compress: false
                        }});
                        
                        const imgData = canvas.toDataURL('image/png', 1.0);
                        
                        // Calculate dimensions to maintain aspect ratio and quality
                        const pdfWidth = 210; // A4 width in mm
                        const pdfHeight = 297; // A4 height in mm
                        const canvasAspectRatio = canvas.height / canvas.width;
                        
                        const margin = 15; // Smaller margin for better fit
                        const maxWidth = pdfWidth - (margin * 2);
                        const maxHeight = pdfHeight - (margin * 2);
                        
                        let imgWidth = maxWidth;
                        let imgHeight = imgWidth * canvasAspectRatio;
                        
                        // If content is too tall, scale to fit height
                        if (imgHeight > maxHeight) {{
                            imgHeight = maxHeight;
                            imgWidth = imgHeight / canvasAspectRatio;
                        }}
                        
                        const xOffset = (pdfWidth - imgWidth) / 2;
                        const yOffset = margin;
                        
                        pdf.addImage(imgData, 'PNG', xOffset, yOffset, imgWidth, imgHeight, undefined, 'FAST');
                        
                        // Download the PDF
                        pdf.save('Invoice-{client.id:04d}-{client.client_name.replace(" ", "-")}.pdf');
                        
                    }} catch (error) {{
                        console.error('Error generating PDF:', error);
                        alert('Error generating PDF. Please try using the Print option instead.');
                        
                        // Ensure styles are restored even on error
                        const actionButtons = document.querySelector('.no-print');
                        if (actionButtons) actionButtons.style.display = 'block';
                    }}
                }}
                
                function copyInvoiceLink() {{
                    const url = window.location.href;
                    navigator.clipboard.writeText(url).then(() => {{
                        alert('Invoice link copied to clipboard!');
                    }});
                }}
                
                // Payment functionality removed
            </script>
        </body>
        </html>
        """
        
        return invoice_html
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Payment functionality removed for simplicity

# All payment routes and functionality removed for simplicity

# Business Intelligence API
@app.route('/api/business-analytics')
def get_business_analytics():
    """Get comprehensive business intelligence data"""
    try:
        analytics = ClientWebsite.get_business_analytics()
        return jsonify(analytics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Smart Renewal Reminder API Endpoints
@app.route('/api/reminders/check', methods=['GET'])
def check_reminders():
    """Check which clients need renewal reminders"""
    try:
        eligible_clients = check_reminder_eligibility()
        
        result = []
        for item in eligible_clients:
            client = item['client']
            result.append({
                'client_id': client.id,
                'client_name': client.client_name,
                'client_phone': client.client_phone,
                'expiry_date': client.expiry_date.strftime('%Y-%m-%d'),
                'days_remaining': item['days_remaining'],
                'reminder_type': item['reminder_type'],
                'message_preview': item['message'][:100] + '...' if len(item['message']) > 100 else item['message'],
                'project_value': float(client.cost)
            })
        
        return jsonify({
            'eligible_clients': result,
            'total_count': len(result)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reminders/send', methods=['POST'])
def send_reminders():
    """Send renewal reminders to eligible clients"""
    try:
        data = request.get_json()
        client_ids = data.get('client_ids', [])
        
        if not client_ids:
            # Send to all eligible clients
            eligible_clients = check_reminder_eligibility()
        else:
            # Send to specific clients
            eligible_clients = [item for item in check_reminder_eligibility() 
                             if item['client'].id in client_ids]
        
        sent_reminders = []
        
        for item in eligible_clients:
            client = item['client']
            
            # Create reminder record
            reminder = ClientReminder()
            reminder.client_id = client.id
            reminder.reminder_type = item['reminder_type']
            reminder.message_content = item['message']
            reminder.status = 'sent'
            
            db.session.add(reminder)
            
            # Generate WhatsApp link
            phone = client.client_phone or '+447415144247'  # Fallback to business phone
            if phone and not phone.startswith('+'):
                phone = '+44' + phone.lstrip('0')  # Convert UK format
            
            # Format phone and message for WhatsApp URL
            clean_phone = phone.replace('+', '').replace(' ', '')
            encoded_message = item['message'].replace(' ', '%20').replace('\n', '%0A')
            whatsapp_url = f"https://wa.me/{clean_phone}?text={encoded_message}"
            
            sent_reminders.append({
                'client_id': client.id,
                'client_name': client.client_name,
                'reminder_type': item['reminder_type'],
                'days_remaining': item['days_remaining'],
                'whatsapp_url': whatsapp_url,
                'status': 'ready_to_send'
            })
        
        # Commit all reminders
        db.session.commit()
        
        return jsonify({
            'sent_reminders': sent_reminders,
            'total_sent': len(sent_reminders),
            'message': f'Generated {len(sent_reminders)} reminder(s) ready to send via WhatsApp'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reminders/history', methods=['GET'])
def get_reminder_history():
    """Get history of sent reminders"""
    try:
        reminders = ClientReminder.query.order_by(ClientReminder.sent_date.desc()).limit(50).all()
        return jsonify([reminder.to_dict() for reminder in reminders])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reminders/stats', methods=['GET'])
def get_reminder_stats():
    """Get reminder statistics"""
    try:
        from sqlalchemy import func
        
        total_reminders = ClientReminder.query.count()
        
        # Reminders by type
        reminder_counts = db.session.query(
            ClientReminder.reminder_type,
            func.count(ClientReminder.id).label('count')
        ).group_by(ClientReminder.reminder_type).all()
        
        # Recent reminders (last 30 days)
        from datetime import timedelta, datetime
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_reminders = ClientReminder.query.filter(
            ClientReminder.sent_date >= thirty_days_ago
        ).count()
        
        # Clients with upcoming deadlines
        eligible_clients = check_reminder_eligibility()
        
        return jsonify({
            'total_reminders_sent': total_reminders,
            'recent_reminders_30_days': recent_reminders,
            'pending_reminders': len(eligible_clients),
            'reminder_breakdown': [
                {'type': item[0], 'count': item[1]} 
                for item in reminder_counts
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analytics')
def analytics_dashboard():
    """Analytics dashboard with business insights"""
    try:
        # Get current month/year
        from datetime import datetime, timedelta
        now = datetime.now()
        current_month = now.month
        current_year = now.year
        
        # Basic stats
        total_clients = ClientWebsite.query.count()
        total_revenue = db.session.query(db.func.sum(ClientWebsite.cost)).scalar() or 0
        paid_clients = ClientWebsite.query.filter_by(invoice_status='Paid').count()
        unpaid_clients = ClientWebsite.query.filter_by(invoice_status='Unpaid').count()
        
        # Outstanding payments
        outstanding_amount = db.session.query(db.func.sum(ClientWebsite.cost)).filter_by(invoice_status='Unpaid').scalar() or 0
        
        # Expiring soon (next 30 days)
        thirty_days_from_now = now + timedelta(days=30)
        expiring_soon = ClientWebsite.query.filter(
            ClientWebsite.expiry_date <= thirty_days_from_now.date(),
            ClientWebsite.expiry_date >= now.date()
        ).count()
        
        # Top clients by value
        top_clients = db.session.query(
            ClientWebsite.client_name,
            ClientWebsite.cost,
            ClientWebsite.invoice_status
        ).order_by(ClientWebsite.cost.desc()).limit(5).all()
        
        # Revenue breakdown
        paid_revenue = db.session.query(db.func.sum(ClientWebsite.cost)).filter_by(invoice_status='Paid').scalar() or 0
        unpaid_revenue = outstanding_amount
        
        # Recent clients (last 30 days)
        thirty_days_ago = now - timedelta(days=30)
        recent_clients = ClientWebsite.query.filter(
            ClientWebsite.created_at >= thirty_days_ago
        ).count()
        
        analytics_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Analytics Dashboard</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                .stat-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
                .revenue-card {{ background: linear-gradient(135deg, #56ab2f 0%, #a8e6cf 100%); }}
                .warning-card {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
                .info-card {{ background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }}
                .stat-number {{ font-size: 2.5rem; font-weight: bold; }}
                .chart-container {{ position: relative; height: 300px; }}
            </style>
        </head>
        <body class="bg-light">
            <div class="container-fluid py-4">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h1><i class="fas fa-chart-bar me-2"></i>Analytics Dashboard</h1>
                    <a href="/" class="btn btn-primary">
                        <i class="fas fa-arrow-left me-2"></i>Back to Clients
                    </a>
                </div>
                
                <!-- Summary Cards -->
                <div class="row mb-4">
                    <div class="col-md-3">
                        <div class="card stat-card text-white h-100">
                            <div class="card-body text-center">
                                <i class="fas fa-users fa-2x mb-2"></i>
                                <div class="stat-number">{total_clients}</div>
                                <p class="mb-0">Total Clients</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card revenue-card text-white h-100">
                            <div class="card-body text-center">
                                <i class="fas fa-pound-sign fa-2x mb-2"></i>
                                <div class="stat-number">£{total_revenue:.0f}</div>
                                <p class="mb-0">Total Revenue</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card warning-card text-white h-100">
                            <div class="card-body text-center">
                                <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                                <div class="stat-number">£{outstanding_amount:.0f}</div>
                                <p class="mb-0">Outstanding</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card info-card text-white h-100">
                            <div class="card-body text-center">
                                <i class="fas fa-calendar-alt fa-2x mb-2"></i>
                                <div class="stat-number">{expiring_soon}</div>
                                <p class="mb-0">Expiring Soon</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <!-- Payment Status Chart -->
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5><i class="fas fa-chart-pie me-2"></i>Payment Status</h5>
                            </div>
                            <div class="card-body">
                                <div class="chart-container">
                                    <canvas id="paymentChart"></canvas>
                                </div>
                                <div class="row text-center mt-3">
                                    <div class="col-6">
                                        <div class="text-success">
                                            <strong>{paid_clients} Paid</strong><br>
                                            <small>£{paid_revenue:.2f}</small>
                                        </div>
                                    </div>
                                    <div class="col-6">
                                        <div class="text-warning">
                                            <strong>{unpaid_clients} Unpaid</strong><br>
                                            <small>£{unpaid_revenue:.2f}</small>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Top Clients -->
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5><i class="fas fa-crown me-2"></i>Top Clients by Value</h5>
                            </div>
                            <div class="card-body">
                                <div class="list-group list-group-flush">
                                    {"".join([f'''
                                    <div class="list-group-item d-flex justify-content-between align-items-center">
                                        <div>
                                            <strong>{client.client_name}</strong>
                                            <br><small class="text-muted">£{client.cost:.2f}</small>
                                        </div>
                                        <span class="badge bg-{"success" if client.invoice_status == "Paid" else "warning"} rounded-pill">
                                            {client.invoice_status}
                                        </span>
                                    </div>
                                    ''' for client in top_clients])}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Quick Stats Row -->
                <div class="row mt-4">
                    <div class="col-md-12">
                        <div class="card">
                            <div class="card-header">
                                <h5><i class="fas fa-info-circle me-2"></i>Quick Business Insights</h5>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-3 text-center">
                                        <h4 class="text-success">{(paid_clients/total_clients*100 if total_clients > 0 else 0):.1f}%</h4>
                                        <p class="text-muted">Collection Rate</p>
                                    </div>
                                    <div class="col-md-3 text-center">
                                        <h4 class="text-info">{recent_clients}</h4>
                                        <p class="text-muted">New Clients (30d)</p>
                                    </div>
                                    <div class="col-md-3 text-center">
                                        <h4 class="text-primary">£{(total_revenue/total_clients if total_clients > 0 else 0):.0f}</h4>
                                        <p class="text-muted">Avg Project Value</p>
                                    </div>
                                    <div class="col-md-3 text-center">
                                        <h4 class="text-warning">{expiring_soon}</h4>
                                        <p class="text-muted">Renewals Due</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/js/all.min.js"></script>
            <script>
                // Payment Status Pie Chart
                const ctx = document.getElementById('paymentChart').getContext('2d');
                new Chart(ctx, {{
                    type: 'doughnut',
                    data: {{
                        labels: ['Paid', 'Unpaid'],
                        datasets: [{{
                            data: [{paid_clients}, {unpaid_clients}],
                            backgroundColor: ['#28a745', '#ffc107'],
                            borderWidth: 2,
                            borderColor: '#fff'
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                position: 'bottom',
                                labels: {{
                                    padding: 20,
                                    usePointStyle: true
                                }}
                            }}
                        }}
                    }}
                }});
            </script>
        </body>
        </html>
        """
        
        return analytics_html
    except Exception as e:
        return f"Error loading analytics: {str(e)}", 500

# Expense Management Routes
@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    """Get all business expenses"""
    try:
        expenses = BusinessExpense.query.order_by(BusinessExpense.expense_date.desc()).all()
        return jsonify([expense.to_dict() for expense in expenses])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/expenses', methods=['POST'])
def add_expense():
    """Add a new business expense"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        expense = BusinessExpense()
        expense.expense_name = data['expenseName']
        expense.amount = data['amount']
        expense.expense_date = datetime.strptime(data['expenseDate'], '%Y-%m-%d').date()
        expense.category = data['category']
        expense.description = data.get('description', '')
        expense.is_tax_deductible = data.get('isTaxDeductible', True)
        
        db.session.add(expense)
        db.session.commit()
        
        return jsonify(expense.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/expenses/<int:expense_id>', methods=['PUT'])
def update_expense(expense_id):
    """Update a business expense"""
    try:
        expense = BusinessExpense.query.get_or_404(expense_id)
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        expense.expense_name = data['expenseName']
        expense.amount = data['amount']
        expense.expense_date = datetime.strptime(data['expenseDate'], '%Y-%m-%d').date()
        expense.category = data['category']
        expense.description = data.get('description', '')
        expense.is_tax_deductible = data.get('isTaxDeductible', True)
        
        db.session.commit()
        
        return jsonify(expense.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    """Delete a business expense"""
    try:
        expense = BusinessExpense.query.get_or_404(expense_id)
        db.session.delete(expense)
        db.session.commit()
        
        return jsonify({'message': 'Expense deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/expenses')
def expenses_page():
    """Expense tracking page"""
    try:
        # Categories for dropdown
        categories = [
            'Office Supplies', 'Software & Tools', 'Marketing', 'Travel',
            'Equipment', 'Professional Services', 'Training', 'Utilities',
            'Internet & Phone', 'Insurance', 'Other'
        ]
        
        expenses_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Expense Tracking</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                .expense-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
                .summary-card {{ background: linear-gradient(135deg, #56ab2f 0%, #a8e6cf 100%); }}
                .deductible-badge {{ background-color: #d1ecf1; color: #0c5460; }}
                .non-deductible-badge {{ background-color: #f8d7da; color: #721c24; }}
                .expense-form {{ background: #f8f9fa; border-radius: 15px; }}
            </style>
        </head>
        <body class="bg-light">
            <div class="container-fluid py-4">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h1><i class="fas fa-receipt me-2"></i>Business Expenses</h1>
                    <div>
                        <a href="/analytics" class="btn btn-info me-2">
                            <i class="fas fa-chart-bar me-2"></i>Analytics
                        </a>
                        <a href="/" class="btn btn-primary">
                            <i class="fas fa-arrow-left me-2"></i>Back to Clients
                        </a>
                    </div>
                </div>
                
                <!-- Add Expense Form -->
                <div class="card mb-4">
                    <div class="expense-card text-white">
                        <div class="card-header">
                            <h4><i class="fas fa-plus-circle me-2"></i>Add New Expense</h4>
                        </div>
                    </div>
                    <div class="card-body expense-form">
                        <form id="expenseForm">
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label class="form-label">Expense Name *</label>
                                        <input type="text" class="form-control" id="expenseName" required>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="mb-3">
                                        <label class="form-label">Amount (£) *</label>
                                        <input type="number" class="form-control" id="amount" step="0.01" required>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="mb-3">
                                        <label class="form-label">Date *</label>
                                        <input type="date" class="form-control" id="expenseDate" required>
                                    </div>
                                </div>
                            </div>
                            <div class="row">
                                <div class="col-md-4">
                                    <div class="mb-3">
                                        <label class="form-label">Category *</label>
                                        <select class="form-select" id="category" required>
                                            <option value="">Select Category</option>
                                            {"".join([f'<option value="{cat}">{cat}</option>' for cat in categories])}
                                        </select>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label class="form-label">Description</label>
                                        <input type="text" class="form-control" id="description" placeholder="Optional details">
                                    </div>
                                </div>
                                <div class="col-md-2">
                                    <div class="mb-3">
                                        <div class="form-check mt-4">
                                            <input class="form-check-input" type="checkbox" id="isTaxDeductible" checked>
                                            <label class="form-check-label" for="isTaxDeductible">
                                                Tax Deductible
                                            </label>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="d-flex gap-2">
                                <button type="submit" class="btn btn-success">
                                    <i class="fas fa-save me-2"></i>Add Expense
                                </button>
                                <button type="button" class="btn btn-secondary" id="cancelBtn" style="display: none;" onclick="cancelEdit()">
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
                
                <!-- Expense Summary -->
                <div class="row mb-4">
                    <div class="col-md-4">
                        <div class="card summary-card text-white">
                            <div class="card-body text-center">
                                <h3 id="totalExpenses">£0.00</h3>
                                <p class="mb-0">Total Expenses</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card bg-success text-white">
                            <div class="card-body text-center">
                                <h3 id="taxDeductible">£0.00</h3>
                                <p class="mb-0">Tax Deductible</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card bg-info text-white">
                            <div class="card-body text-center">
                                <h3 id="monthlyExpenses">£0.00</h3>
                                <p class="mb-0">This Month</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Expenses Table -->
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-list me-2"></i>Expense History</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead>
                                    <tr>
                                        <th>Date</th>
                                        <th>Expense</th>
                                        <th>Category</th>
                                        <th>Amount</th>
                                        <th>Tax Status</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="expensesTableBody">
                                    <!-- Dynamically populated -->
                                </tbody>
                            </table>
                        </div>
                        <div id="emptyState" class="text-center py-5" style="display: none;">
                            <i class="fas fa-receipt fa-3x text-muted mb-3"></i>
                            <h5 class="text-muted">No expenses recorded yet</h5>
                            <p class="text-muted">Add your first business expense above</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/js/all.min.js"></script>
            <script>
                class ExpenseManager {{
                    constructor() {{
                        this.expenses = [];
                        this.editingExpense = null;
                        this.loadExpenses();
                        this.setupForm();
                        document.getElementById('expenseDate').value = new Date().toISOString().split('T')[0];
                    }}
                    
                    setupForm() {{
                        document.getElementById('expenseForm').addEventListener('submit', (e) => {{
                            e.preventDefault();
                            if (this.editingExpense) {{
                                this.updateExpense();
                            }} else {{
                                this.addExpense();
                            }}
                        }});
                    }}
                    
                    async loadExpenses() {{
                        try {{
                            const response = await fetch('/api/expenses');
                            this.expenses = await response.json();
                            this.renderExpenses();
                            this.updateSummary();
                        }} catch (error) {{
                            console.error('Error loading expenses:', error);
                        }}
                    }}
                    
                    async addExpense() {{
                        const formData = this.getFormData();
                        try {{
                            const response = await fetch('/api/expenses', {{
                                method: 'POST',
                                headers: {{'Content-Type': 'application/json'}},
                                body: JSON.stringify(formData)
                            }});
                            
                            if (response.ok) {{
                                this.loadExpenses();
                                this.resetForm();
                                this.showAlert('Expense added successfully!', 'success');
                            }} else {{
                                throw new Error('Failed to add expense');
                            }}
                        }} catch (error) {{
                            this.showAlert('Error adding expense: ' + error.message, 'danger');
                        }}
                    }}
                    
                    async updateExpense() {{
                        const formData = this.getFormData();
                        try {{
                            const response = await fetch(`/api/expenses/${{this.editingExpense.id}}`, {{
                                method: 'PUT',
                                headers: {{'Content-Type': 'application/json'}},
                                body: JSON.stringify(formData)
                            }});
                            
                            if (response.ok) {{
                                this.loadExpenses();
                                this.cancelEdit();
                                this.showAlert('Expense updated successfully!', 'success');
                            }} else {{
                                throw new Error('Failed to update expense');
                            }}
                        }} catch (error) {{
                            this.showAlert('Error updating expense: ' + error.message, 'danger');
                        }}
                    }}
                    
                    async deleteExpense(id) {{
                        if (confirm('Are you sure you want to delete this expense?')) {{
                            try {{
                                const response = await fetch(`/api/expenses/${{id}}`, {{
                                    method: 'DELETE'
                                }});
                                
                                if (response.ok) {{
                                    this.loadExpenses();
                                    this.showAlert('Expense deleted successfully!', 'success');
                                }} else {{
                                    throw new Error('Failed to delete expense');
                                }}
                            }} catch (error) {{
                                this.showAlert('Error deleting expense: ' + error.message, 'danger');
                            }}
                        }}
                    }}
                    
                    editExpense(index) {{
                        const expense = this.expenses[index];
                        this.editingExpense = expense;
                        
                        document.getElementById('expenseName').value = expense.expenseName;
                        document.getElementById('amount').value = expense.amount;
                        document.getElementById('expenseDate').value = expense.expenseDate;
                        document.getElementById('category').value = expense.category;
                        document.getElementById('description').value = expense.description;
                        document.getElementById('isTaxDeductible').checked = expense.isTaxDeductible;
                        
                        document.querySelector('#expenseForm button[type="submit"]').innerHTML = '<i class="fas fa-save me-2"></i>Update Expense';
                        document.getElementById('cancelBtn').style.display = 'inline-block';
                    }}
                    
                    cancelEdit() {{
                        this.editingExpense = null;
                        this.resetForm();
                        document.querySelector('#expenseForm button[type="submit"]').innerHTML = '<i class="fas fa-save me-2"></i>Add Expense';
                        document.getElementById('cancelBtn').style.display = 'none';
                    }}
                    
                    getFormData() {{
                        return {{
                            expenseName: document.getElementById('expenseName').value,
                            amount: parseFloat(document.getElementById('amount').value),
                            expenseDate: document.getElementById('expenseDate').value,
                            category: document.getElementById('category').value,
                            description: document.getElementById('description').value,
                            isTaxDeductible: document.getElementById('isTaxDeductible').checked
                        }};
                    }}
                    
                    resetForm() {{
                        document.getElementById('expenseForm').reset();
                        document.getElementById('expenseDate').value = new Date().toISOString().split('T')[0];
                    }}
                    
                    renderExpenses() {{
                        const tbody = document.getElementById('expensesTableBody');
                        const emptyState = document.getElementById('emptyState');
                        
                        if (this.expenses.length === 0) {{
                            tbody.innerHTML = '';
                            emptyState.style.display = 'block';
                            return;
                        }}
                        
                        emptyState.style.display = 'none';
                        tbody.innerHTML = this.expenses.map((expense, index) => `
                            <tr>
                                <td>${{new Date(expense.expenseDate).toLocaleDateString()}}</td>
                                <td>
                                    <strong>${{expense.expenseName}}</strong>
                                    ${{expense.description ? `<br><small class="text-muted">${{expense.description}}</small>` : ''}}
                                </td>
                                <td><span class="badge bg-secondary">${{expense.category}}</span></td>
                                <td><strong>£${{expense.amount.toFixed(2)}}</strong></td>
                                <td>
                                    <span class="badge ${{expense.isTaxDeductible ? 'deductible-badge' : 'non-deductible-badge'}}">
                                        ${{expense.isTaxDeductible ? 'Tax Deductible' : 'Non-Deductible'}}
                                    </span>
                                </td>
                                <td>
                                    <button class="btn btn-warning btn-sm me-1" onclick="expenseManager.editExpense(${{index}})" title="Edit">
                                        <i class="fas fa-edit"></i>
                                    </button>
                                    <button class="btn btn-danger btn-sm" onclick="expenseManager.deleteExpense(${{expense.id}})" title="Delete">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </td>
                            </tr>
                        `).join('');
                    }}
                    
                    updateSummary() {{
                        const total = this.expenses.reduce((sum, exp) => sum + exp.amount, 0);
                        const taxDeductible = this.expenses.filter(exp => exp.isTaxDeductible).reduce((sum, exp) => sum + exp.amount, 0);
                        
                        const currentMonth = new Date().getMonth();
                        const currentYear = new Date().getFullYear();
                        const monthlyTotal = this.expenses.filter(exp => {{
                            const expDate = new Date(exp.expenseDate);
                            return expDate.getMonth() === currentMonth && expDate.getFullYear() === currentYear;
                        }}).reduce((sum, exp) => sum + exp.amount, 0);
                        
                        document.getElementById('totalExpenses').textContent = `£${{total.toFixed(2)}}`;
                        document.getElementById('taxDeductible').textContent = `£${{taxDeductible.toFixed(2)}}`;
                        document.getElementById('monthlyExpenses').textContent = `£${{monthlyTotal.toFixed(2)}}`;
                    }}
                    
                    showAlert(message, type) {{
                        const alertDiv = document.createElement('div');
                        alertDiv.className = `alert alert-${{type}} alert-dismissible fade show`;
                        alertDiv.innerHTML = `
                            ${{message}}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        `;
                        
                        document.body.insertBefore(alertDiv, document.body.firstChild);
                        setTimeout(() => alertDiv.remove(), 5000);
                    }}
                }}
                
                const expenseManager = new ExpenseManager();
                
                function cancelEdit() {{
                    expenseManager.cancelEdit();
                }}
            </script>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
        </body>
        </html>
        """
        
        return expenses_html
    except Exception as e:
        return f"Error loading expenses page: {str(e)}", 500

# Internal Cron Endpoints
@app.route('/internal/run-recurring', methods=['POST'])
@requires_cron
def run_recurring():
    """Run recurring business tasks - protected endpoint for cron jobs"""
    try:
        # Call existing business analytics functions or any recurring tasks
        # This could include data cleanup, analytics updates, etc.
        
        # For now, this safely returns success
        # In the future, you can add recurring tasks here
        
        return jsonify({"ok": True, "message": "Recurring tasks completed successfully"})
    except Exception as e:
        logging.error(f"Error in run_recurring: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/internal/run-reminders', methods=['POST'])
@requires_cron
def run_reminders():
    """Run reminder checks and send notifications - protected endpoint for cron jobs"""
    try:
        # Get eligible clients for reminders
        eligible_clients = check_reminder_eligibility()
        
        if not eligible_clients:
            return jsonify({
                "ok": True,
                "message": "No reminders needed at this time",
                "reminders_sent": 0
            })
        
        sent_count = 0
        processed_clients = []
        
        # Process each eligible client
        for item in eligible_clients:
            try:
                client = item['client']
                
                # Create reminder record
                reminder = ClientReminder()
                reminder.client_id = client.id
                reminder.reminder_type = item['reminder_type']
                reminder.message_content = item['message']
                reminder.status = 'sent'
                
                db.session.add(reminder)
                
                # Generate WhatsApp link for manual sending
                phone = client.client_phone or '+447415144247'
                if phone and not phone.startswith('+'):
                    phone = '+44' + phone.lstrip('0')
                
                clean_phone = phone.replace('+', '').replace(' ', '')
                encoded_message = item['message'].replace(' ', '%20').replace('\n', '%0A')
                whatsapp_url = f"https://wa.me/{clean_phone}?text={encoded_message}"
                
                processed_clients.append({
                    'client_id': client.id,
                    'client_name': client.client_name,
                    'reminder_type': item['reminder_type'],
                    'days_remaining': item['days_remaining'],
                    'whatsapp_url': whatsapp_url
                })
                
                sent_count += 1
                
            except Exception as client_error:
                logging.error(f"Error processing client {item['client'].id}: {str(client_error)}")
                continue
        
        # Commit all reminder records
        db.session.commit()
        
        return jsonify({
            "ok": True,
            "message": f"Processed {sent_count} reminder(s) successfully",
            "reminders_sent": sent_count,
            "processed_clients": processed_clients
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in run_reminders: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

# Messaging Routes

# Email functionality removed

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)