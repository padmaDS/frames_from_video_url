from flask import Flask, request, jsonify
import os
import cv2
import base64
import requests
import csv
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables
load_dotenv()

# OpenAI API Key
api_key = os.getenv('OPENAI_API_KEY')

# Constants for directories
DOWNLOAD_DIRECTORY = 'downloads/'
OUTPUT_FOLDER = 'frames_output/'

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
                        "text": """Extract the text from the image? and remove The text in the image states, 
                        Sure, here is the text from the image and the text in the image is in Telugu. 
                        Here's the extracted text: from the begining"""
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

# Function to download a video using yt_dlp
def download_video_ytdlp(youtube_url):
    import yt_dlp as youtube_dl
    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(DOWNLOAD_DIRECTORY, '%(title)s.%(ext)s')
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(youtube_url, download=True)
        return ydl.prepare_filename(info_dict)

# Function to download a video directly using requests
def download_video_blob(blob_url):
    import urllib.parse
    file_name = urllib.parse.unquote(blob_url.split('/')[-1])
    download_path = os.path.join(DOWNLOAD_DIRECTORY, file_name)
    with requests.get(blob_url, stream=True) as r:
        with open(download_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return download_path

# Function to extract frames from video and save them
def extract_frames(video_path, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error: Could not open video.")
        return

    frame_count = 0
    results = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        output_name = os.path.join(output_folder, f"frame_{frame_count}.jpg")
        cv2.imwrite(output_name, frame)

        # Extract text from the frame
        extracted_text = extract_text_from_image(output_name)
        print(f"Image: {output_name}, Extracted Text: {extracted_text}")

        results.append({
            "image_name": output_name,
            "extracted_text": extracted_text
        })

        frame_count += 1

    cap.release()
    cv2.destroyAllWindows()

    return results

# Endpoint to trigger video download, frame extraction, and text extraction
@app.route('/process_video', methods=['POST'])
def process_video():
    data = request.get_json()
    video_url = data['video_url']  # Example: 'https://quadz.blob.core.windows.net/newpoc/stitched_video_20240627130216.mp4'
    
    if video_url.startswith('https://www.youtube.com/'):
        video_path = download_video_ytdlp(video_url)
    elif video_url.startswith('https://quadz.blob.core.windows.net/'):
        video_path = download_video_blob(video_url)
    else:
        return jsonify({"error": "Unsupported URL format."}), 400

    results = extract_frames(video_path, OUTPUT_FOLDER)
    print(f"Processed video: {video_path}, Frames extracted: {len(results)}")

    # Prepare CSV file for writing results
    csv_file = "image_text_results.csv"
    csv_header = ["Image_Name", "Extracted_Text"]

    with open(csv_file, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(csv_header)

        for result in results:
            writer.writerow([result['image_name'], result['extracted_text']])

    print(f"Results saved to {csv_file}")

    return jsonify({
        "message": "Video processing completed.",
        "video_path": video_path,
        "num_frames": len(results),
        "results_file": results
    })

if __name__ == "__main__":
    app.run(debug=True)
