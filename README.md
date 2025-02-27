# Restaurant AI Assistant

Welcome to the Restaurant AI Assistant, an intelligent chatbot designed to enhance the dining experience for customers of Bottega Restaurant.

## Table of Contents

- [Features](#features)
- [Demo](#demo)
- [Installation](#installation)
- [Usage](#usage)
- [Technologies Used](#technologies-used)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Menu Information**: Fetch details about menu items, including descriptions and prices.
- **Order Management**: Place orders, modify cart contents, and check order status.
- **Personalization**: See your previous order, get recommendations from AI.

## Demo
Check out our AI Assistant in action:

[![Restaurant AI Assistant Demo](https://cdn.loom.com/sessions/thumbnails/ccc6396a13fd441db8722b1f2caaa6eb-1719947983821-with-play.gif)](https://www.loom.com/share/ccc6396a13fd441db8722b1f2caaa6eb)

[Watch Bottega-Bot Demo Video](https://www.loom.com/share/ccc6396a13fd441db8722b1f2caaa6eb)

## Demo

Check out our AI Assistant in action: [Restaurant AI Assistant Demo](https://www.loom.com/share/ccc6396a13fd441db8722b1f2caaa6eb?sid=7b4d657f-a040-4e4c-a448-f4570471157e)

## Set Up

Enter your API keys in the env file

ANTHROPIC_API_KEY (https://console.anthropic.com/)

TWILIO_ACCOUNT_SID (https://console.twilio.com/)

TWILIO_AUTH_TOKEN (https://console.twilio.com/)

twilio_phone_number 

restaurant_phone_number

(Recommended) Setup LangChain API for tracing and monitoring (https://smith.langchain.com)

LANGCHAIN_API_KEY

LANGCHAIN_TRACING_V2 = True

LANGCHAIN_PROJECT = "Project Name of Choice"

STRIPE_SECRET_KEY

## Usage

1. Start the Flask server:
   ```
   python app.py
   ```

2. Open your web browser and navigate to `http://localhost:5000`

3. Start interacting with the AI Assistant to explore menu items, place orders, or get assistance with your dining experience.

## Technologies Used

- Python
- Flask
- SQLite
- LangChain + LangGraph
- Anthropic Claude Sonnet 3.5
- React (for the frontend)
- Twilio API for text messaging feature
- Stripe API for payments

## Contributing

We welcome contributions to improve the Restaurant AI Assistant. Please follow these steps:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Commit your changes (`git commit -m 'Add some amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

---

# Deploying Aramex Chatbot to Google Cloud Platform

## Prerequisites

- Mac M1 computer
- Docker Desktop installed and running
- Google Cloud SDK installed
- A Google Cloud Platform account with a project set up
- Git repository with the Aramex chatbot code

## Step 1: Prepare the Local Environment

1. Open Terminal and navigate to your project directory.

2. Ensure you have a `.env` file in your project root with all necessary environment variables:

   ```
   ANTHROPIC_API_KEY=your_anthropic_api_key
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   LANGCHAIN_API_KEY=your_langchain_api_key
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_PROJECT=ARABOT_DEMO_1
   twilio_phone_number=your_twilio_phone_number
   restaurant_phone_number=your_restaurant_phone_number
   ```

3. Update the `app.py` to use the correct port:

   ```python
   if __name__ == '__main__':
       app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
   ```

## Step 2: Create and Configure Dockerfile

Create a `Dockerfile` in your project root with the following content:

```dockerfile
FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

COPY build ./build
COPY app.py .
COPY requirements.txt .
COPY customer_chatbot_new.db .
COPY customer_chatbot_new_memory.db .
COPY .env .

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD ["python", "app.py"]
```

## Step 3: Build and Push Docker Image

1. Enable Docker BuildKit:
   ```bash
   export DOCKER_BUILDKIT=1
   ```

2. Create a new builder instance:
   ```bash
   docker buildx create --name mybuilder --use
   ```

3. Build and push the Docker image:
   ```bash
   docker buildx build --platform linux/amd64 -t gcr.io/[PROJECT-ID]/aramex-chatbot:latest . --push
   ```
   Replace `[PROJECT-ID]` with your Google Cloud Project ID.

## Step 4: Deploy to Google Cloud Platform

1. Authenticate with Google Cloud:
   ```bash
   gcloud auth login
   gcloud config set project [PROJECT-ID]
   ```

2. Enable required GCP services:
   ```bash
   gcloud services enable run.googleapis.com containerregistry.googleapis.com
   ```

3. Deploy to Cloud Run:
   ```bash
   gcloud run deploy aramex-chatbot \
     --image gcr.io/[PROJECT-ID]/aramex-chatbot:latest \
     --platform managed \
     --region [REGION] \
     --allow-unauthenticated \
     --port 8080
   ```
   Replace `[REGION]` with your desired region (e.g., `us-central1`).

## Step 4: Verify Deployment

1. After successful deployment, Cloud Run will provide a URL where your application is hosted.
2. Open the provided URL in a web browser to verify that your Aramex chatbot is running correctly.
3. Test the chatbot functionality to ensure it's working as expected in the cloud environment.

## Troubleshooting

- If you encounter issues with the build process, try removing the existing builder and creating a new one:
  ```bash
  docker buildx rm mybuilder
  docker buildx create --name mybuilder --use
  ```

- If environment variables are not being recognized, double-check that they are correctly set in the Cloud Run console or through the `gcloud` command.

- Monitor the application logs in the Google Cloud Console for any runtime errors or issues.

## Maintenance

- To update your application, make changes to your local code, rebuild the Docker image with a new tag, and redeploy using the same `gcloud run deploy` command with the new image tag.

- Regularly update your dependencies and base Docker image to ensure you have the latest security patches.
  
For any questions or support, please contact sonnythomas0618@gmail.com

