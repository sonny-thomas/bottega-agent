FROM --platform=linux/amd64 python:3.11

# Set the working directory in the container
WORKDIR /app

# Copy the built React app to the working directory
COPY build ./build

# Copy the Flask app and other necessary files
COPY app.py .
COPY requirements.txt .
COPY bottega_customer_chatbot.db .
COPY customer_chatbot_new_memory.db .
COPY .env .

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port on which the Flask app will run
EXPOSE 10000

# Set the entry point command to run the Flask app
CMD ["python", "app.py"]