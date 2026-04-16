# PLO Equity Engine - Dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY engine/ ./engine/
COPY static/ ./static/

# Set working directory to engine
WORKDIR /app/engine

# Environment variables
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV N4P_SEAT_SECRET=your_secret_change_in_production
ENV TRACKER_API_KEY=trk_default

# Expose port 3000
EXPOSE 3000

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "--workers", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
