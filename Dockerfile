FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create a non-root user (security best practice)
RUN useradd -m -u 1000 botuser
USER botuser

# Use environment port
CMD python your_bot_file.py
