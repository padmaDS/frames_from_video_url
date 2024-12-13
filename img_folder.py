import base64
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI API Key
api_key = os.getenv('OPENAI_API_KEY')

# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Function to send request and extract text
def extract_text_from_image(image_path):
    base64_image = encode_image(image_path)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Extract the text from the image?"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 300
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    response = response.json()

    telugu_text = response['choices'][0]['message']['content']
    return telugu_text

# Path to your folder containing images
folder_path = r"frames_output"

# List all image files in the folder
image_files = [os.path.join(folder_path, file) for file in os.listdir(folder_path) if file.endswith(('jpeg', 'jpg', 'png'))]

# Iterate through each image file and extract text
for image_path in image_files:
    extracted_text = extract_text_from_image(image_path)
    print(f"Image: {image_path}, Extracted Text: {extracted_text}")
