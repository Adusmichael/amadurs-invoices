# StoreBliz Client Manager

## Project Overview
StoreBliz Client Manager is a comprehensive business management platform designed specifically for small service businesses. Built with Flask backend and modern HTML/CSS/JavaScript frontend, it combines client management, project tracking, professional invoicing, and advanced business intelligence in one streamlined solution.

### Target Market
- **Small Service Businesses**: Consultants, agencies, freelancers
- **Local Services**: Cleaning, landscaping, maintenance, repair services
- **Professional Services**: Legal, accounting, marketing, coaching
- **Creative Services**: Photographers, designers, writers, content creators
- **Technical Services**: IT support, web developers, software consultants

### Competitive Advantage
- **Simplicity over Complexity**: Clean, intuitive interface without overwhelming features
- **Affordable Alternative**: Cost-effective solution compared to enterprise tools like Xero
- **Multi-Currency Support**: International business capabilities with 9 currencies
- **WhatsApp Integration**: Direct client communication for global reach
- **Business Intelligence**: Profit tracking and analytics typically found in expensive software
- **Professional Invoicing**: Generate polished invoices and receipts without design skills

## Features
- ✅ Add/edit client project information (Name, URL, Start Date, Deadline, Cost, Invoice Status)
- ✅ Data persistence using PostgreSQL database
- ✅ REST API for CRUD operations
- ✅ Responsive table display with modern Bootstrap UI
- ✅ Project deadline highlighting (30-day warning)
- ✅ Form validation and error handling
- ✅ Edit and delete functionality
- ✅ Clean, modern design with rounded corners and professional styling
- ✅ **Multi-Currency Support** - 9 international currencies with dynamic display
- ✅ **WhatsApp Web Integration** - Instant messaging with professional templates
# Email functionality removed
# SMS functionality removed
- ✅ Professional invoice generation and sharing system
- ✅ Professional receipt generation for paid clients
- ✅ Custom notes field for additional client information
- ✅ Fully editable document headers (titles, subtitles, numbers, dates)
- ✅ Editable client information sections
- ✅ Completely customizable footer sections with company details
- ✅ Smart document generation (invoices for all, receipts for paid clients only)
- ✅ Visual editing feedback with hover effects and inline instructions
- ✅ **Smart Business Intelligence System**
  - **Profit Margin Calculator** - Track project costs vs revenue with automatic calculations
  - **Client Lifetime Value Analytics** - Comprehensive client value tracking across multiple projects
  - **Predictive Renewal Insights** - AI-powered prediction of client renewal likelihood
  - **Revenue Forecasting** - 3-month revenue projections based on client patterns
  - **Business Analytics Dashboard** - Real-time business performance metrics
  - **Color-coded Profit Display** - Visual profit margin indicators in client table

## Technical Stack
- **Backend**: Flask (Python)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **UI Framework**: Bootstrap 5.3.2
- **Icons**: Font Awesome 6.4.0
- **Server**: Gunicorn WSGI server

## Project Architecture
- `app.py` - Flask application with database models and REST API endpoints
- `main.py` - Application entry point for Gunicorn
- `index.html` - Frontend with JavaScript API client
- `replit.md` - Project documentation and user preferences
- **Database**: PostgreSQL with `client_websites` table

## Key Components
1. **ClientManager Class**: Handles all CRUD operations and API management
2. **Form Validation**: Real-time validation with visual feedback
3. **Deadline Detection**: Automatic highlighting of projects with deadlines within 30 days
4. **Invoice Generation**: Professional invoice creation and sharing system
5. **Receipt Generation**: Professional receipt system for payment confirmations
6. **Responsive Design**: Mobile-friendly layout with Bootstrap grid system

## User Preferences
- Prefers simple, clean interfaces without complex technical features
- Wants localStorage persistence without backend complexity
- Needs responsive design for various devices
- Values modern, professional styling
- Uses business template: "Adus Michael - IT Consultant" based in Liverpool, UK
- Default contact email: adusmichael@gmail.com
- Phone: +447415144247
- **Target Market**: Small service businesses (consultants, agencies, freelancers, local services)
- **Value Proposition**: Simple client management with professional invoicing and business intelligence

## Recent Changes
- **2025-09-06**: Strategic Pivot to StoreBliz Client Manager
  - **Market Expansion**: Pivoted from website-specific to general client management system
  - **Target Audience**: Small service businesses, consultants, agencies, freelancers
  - **Broader Appeal**: Rebranded UI for any service business (not just web design)
  - **Universal Terms**: Changed "Website Manager" to "Client Manager", "Date Built" to "Project Start", "Expiry" to "Deadline"
  - **Service Agnostic**: System now supports any type of client project or service

- **2025-09-06**: Smart Business Intelligence System Implemented
  - **Profit Tracking**: Added project cost tracking with automatic profit margin calculations
  - **Client Analytics**: Comprehensive client lifetime value tracking and renewal predictions
  - **Revenue Forecasting**: 3-month revenue projections based on historical client patterns
  - **Business Insights**: Real-time analytics including payment rates and business health metrics
  - **Enhanced UI**: Color-coded profit margins in client table with professional styling
  - **API Integration**: New `/api/business-analytics` endpoint for comprehensive business data
  - **Predictive Intelligence**: Smart renewal likelihood predictions based on client behavior

- **2025-09-05**: Payment System Removed
  - **Simplified System**: All Stripe payment integration removed due to configuration issues
  - **Clean Interface**: Removed payment buttons, bank details, and complex payment flows
  - **Focus on Core**: Client management, invoicing, and WhatsApp communication only
  - **Error-Free**: Eliminated payment setup errors and API key issues

- **2025-09-05**: Communication System Streamlined
  - **WhatsApp Web Only**: Simplified to WhatsApp integration (no popups!)
  - **SMS Removed**: Eliminated Twilio dependencies for configuration simplicity
  - **Email Removed**: Removed email functionality due to popup issues
  - **Professional Messaging**: Clean business communication without emojis
  - **New Tab Behavior**: All communication opens in new browser tabs

## Previous Changes
- **2025-08-01**: Enhanced documents with comprehensive editing capabilities
  - **Fully Editable Headers**: All header sections (titles, subtitles, numbers, dates) are now clickable and editable
  - **Editable Client Information**: Bill To/Payment From sections and project details can be customized inline
  - **Complete Footer Customization**: Entire footer sections including company information, payment terms, and contact details are editable
  - **Visual Editing Experience**: Hover effects, focus states, and helpful editing hints guide users
  - **Professional Layout**: Added company information and payment method sections to both invoices and receipts

- **2025-08-01**: Added professional receipt system for payment confirmations
  - **Receipt Generation**: Professional receipts for clients with "Paid" status
  - **Smart UI**: Receipt buttons appear automatically for paid clients
  - **Payment Confirmation**: Receipts show "PAID" watermark and payment confirmation
  - **Dual Document System**: Invoices for requesting payment, receipts for confirming payment
  - **Enhanced Workflow**: Seamless integration with existing invoice management
  - **Professional Styling**: Green-themed receipts vs blue-themed invoices for clear distinction

- **2025-07-31**: Enhanced with advanced invoice features and custom notes
  - **Custom Notes**: Added optional notes field for additional client information
  - **Editable Invoice Headers**: Invoice number and date are now editable inline
  - **Enhanced PDF Generation**: Improved quality with 3x scale for crisp text
  - **Database Expansion**: Added custom_notes column to client_websites table
  - **Visual Enhancements**: Added hover effects for editable fields
  - **Form Enhancement**: Extended client form with notes textarea

- **2025-07-31**: Upgraded to full-stack application with database integration
  - **Database Integration**: Added PostgreSQL database with SQLAlchemy ORM
  - **REST API**: Created complete CRUD API endpoints (/api/clients)
  - **Frontend Update**: Migrated from localStorage to API-based data management
  - **Backend Architecture**: Built Flask application with proper database models
  - **Data Persistence**: All client data now stored in PostgreSQL database
  - **Form validation and error handling**: Enhanced with server-side validation
  - **Responsive design**: Maintained Bootstrap UI with modern styling
  - **Currency**: Uses British pounds (£) for cost display
  - **Deployment**: Configured with Gunicorn WSGI server

## Setup Instructions
1. PostgreSQL database is automatically provisioned
2. Flask application starts with: `gunicorn --bind 0.0.0.0:5000 main:app`
3. Access at `http://localhost:5000`
4. API endpoints available at `/api/clients`

## API Endpoints
- `GET /api/clients` - Retrieve all client websites
- `POST /api/clients` - Create new client website
- `PUT /api/clients/{id}` - Update existing client website
- `DELETE /api/clients/{id}` - Delete client website

## Data Structure
```javascript
{
  id: number (auto-generated),
  clientName: string,
  websiteUrl: string, 
  dateBuilt: string (YYYY-MM-DD),
  expiryDate: string (YYYY-MM-DD),
  cost: number,
  invoiceStatus: "Paid" | "Unpaid",
  customNotes: string (optional)
}
```

## Database Schema
Table: `client_websites`
- `id` (Primary Key, Integer)
- `client_name` (String, 255 chars)
- `website_url` (String, 500 chars)
- `date_built` (Date)
- `expiry_date` (Date)
- `cost` (Numeric, 10,2)
- `invoice_status` (String, 20 chars)
- `custom_notes` (Text, optional)
- `created_at` (DateTime)
- `updated_at` (DateTime)