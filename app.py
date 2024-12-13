# main.py

from flask import Flask, request, jsonify
import os
import cv2
import numpy as np
import yt_dlp as youtube_dl
from pytube import YouTube
import base64
import requests
import csv
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Constants for directories
DOWNLOAD_DIRECTORY = 'downloads/'
OUTPUT_FOLDER = 'frames_output/'

# OpenAI API Key
api_key = os.getenv('OPENAI_API_KEY')

# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Function to extract text from image using OpenAI API
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

# Function to download a YouTube video, extract frames, and extract text from frames
def download_and_extract_frames(youtube_url, output_folder):
    # Step 1: Download the YouTube video
    def download_video_ytdlp(youtube_url):
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(DOWNLOAD_DIRECTORY, '%(title)s.%(ext)s')
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(youtube_url, download=True)
            return ydl.prepare_filename(info_dict)

    # Download the video using yt_dlp
    video_filename = download_video_ytdlp(youtube_url)

    # Step 2: Extract frames and remove duplicates
    def extract_frames_and_count_duplicates(video_path, output_folder):
        # Create output folder if it doesn't exist
        os.makedirs(output_folder, exist_ok=True)
        
        # Open the video file
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print("Error: Could not open video.")
            return
        
        # Initialize variables
        frame_count = 0
        duplicate_count = 0
        previous_frame = None
        
        while True:
            # Read a new frame
            ret, frame = cap.read()
            
            if not ret:
                break
            
            # Convert frame to grayscale
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Compute histogram of the grayscale frame
            histogram = cv2.calcHist([gray_frame], [0], None, [256], [0, 256])
            
            # Normalize histogram for comparison
            histogram /= histogram.sum()
            
            # Convert histogram to a tuple for comparison
            frame_histogram = tuple(histogram.flatten())
            
            # Compare current frame histogram with previous frame
            if previous_frame is None or frame_histogram != previous_frame:
                # Construct output file name
                output_name = os.path.join(output_folder, f"frame_{frame_count}.jpg")
                
                # Save frame as JPEG file
                cv2.imwrite(output_name, frame)
                
                # Extract text from the frame
                extracted_text = extract_text_from_image(output_name)
                
                frame_count += 1
            else:
                duplicate_count += 1
            
            # Update previous frame histogram
            previous_frame = frame_histogram
        
        # Release the video capture object and close all windows
        cap.release()
        cv2.destroyAllWindows()
        
        return frame_count

    # Extract frames from the downloaded video
    num_frames = extract_frames_and_count_duplicates(video_filename, output_folder)

    # Path to folder containing extracted frames
    frames_folder = output_folder

    # List all image files in the folder
    image_files = [file for file in os.listdir(frames_folder) if file.endswith(('jpeg', 'jpg', 'png'))]

    # Prepare CSV file for writing results
    csv_file = "image_text_results.csv"
    csv_header = ["Image_Name", "Extracted_Text"]

    with open(csv_file, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(csv_header)

        # Iterate through each image file and extract text
        for image_name in image_files:
            image_path = os.path.join(frames_folder, image_name)
            extracted_text = extract_text_from_image(image_path)
            writer.writerow([image_name, extracted_text])

    return f"Downloaded video and extracted {num_frames} frames. Results saved to image_text_results.csv."

# Flask route for processing the video
@app.route('/process_video', methods=['POST'])
def process_video():
    data = request.get_json()

    youtube_url = data.get('youtube_url')

    if youtube_url:
        try:
            result_message = download_and_extract_frames(youtube_url, OUTPUT_FOLDER)
            return jsonify({"message": result_message}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "YouTube URL not provided."}), 400


# Main method to run the Flask application
if __name__ == "__main__":
    app.run(debug=True)
