from flask import Flask, render_template, request, jsonify, url_for
from pytube import YouTube
import cv2
import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from datetime import datetime
import math
from moviepy.editor import VideoFileClip

load_dotenv()

connect_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')

app = Flask(__name__, static_folder='static')

# Define the directory where downloads will be saved
DOWNLOAD_DIRECTORY = './static/downloads/'
FRAMES_DIRECTORY = './static/frames/'
# Define the directory where the videos are stored
OUTPUT_VIDEO_DIRECTORY = './static/output_videos/'

# Function to create a directory if it doesn't exist
def create_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def upload_video(video_path, video_name, connect_str):
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"The file {video_path} does not exist.")

    file_extension = os.path.splitext(video_path)[1]
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_video_name = f"{video_name}_{timestamp}{file_extension}".replace(" ", "_").replace(":", "_").replace("/", "_")

    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    container_name = 'newpoc'
    container_client = blob_service_client.get_container_client(container_name)
    if not container_client.exists():
        container_client.create_container()

    blob_client = container_client.get_blob_client(safe_video_name)
    with open(video_path, "rb") as video_file:
        blob_client.upload_blob(video_file, blob_type="BlockBlob")

    blob_url = blob_client.url
    return blob_url

def convert_mp4_to_webm(input_path, output_path, bitrate='5000k'):
    video = VideoFileClip(input_path)
    video.write_videofile(output_path, codec='libvpx-vp9', bitrate=bitrate)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    youtube_url = request.form['url']
    try:
        yt = YouTube(youtube_url)
        video = yt.streams.filter(progressive=True, file_extension='mp4').first()
        video.download(DOWNLOAD_DIRECTORY)
        video_filename = video.default_filename
        download_path = os.path.join(DOWNLOAD_DIRECTORY, video_filename)
        message = f'{video_filename} downloaded successfully! <br> Download path: {download_path}'
    except Exception as e:
        message = f'Error downloading video: {str(e)}'
   
    return render_template('download.html', message=message, video_filename=video_filename, last_step='')

@app.route('/convert', methods=['POST'])
def convert():
    video_filename = request.form['video_filename']
    video_path = os.path.join(DOWNLOAD_DIRECTORY, video_filename)
   
    try:
        if not os.path.exists(video_path):
            return render_template('download.html', message=f"Error: Video file not found at {video_path}", last_step='download')

        create_directory(FRAMES_DIRECTORY)
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            return render_template('download.html', message="Error: Could not open video file.", last_step='download')
       
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = math.ceil(fps / 5)  # Extract 5 frames per second

        frame_count = 0
        frame_number = 0
        frame_files = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break
           
            if frame_count % frame_interval == 0:
                frame_filename = f'frame_{frame_number:04d}.jpg'
                frame_filepath = os.path.join(FRAMES_DIRECTORY, frame_filename)
                cv2.imwrite(frame_filepath, frame)
                frame_files.append(f'frames/{frame_filename}')
                frame_number += 1
           
            frame_count += 1
       
        cap.release()
        message = f"Frames extracted successfully. Total frames: {frame_number}"

        os.remove(video_path)
    except Exception as e:
        message = f"Error: {str(e)}"
   
    return render_template('download.html', message=message, video_filename=video_filename, frames_extracted=True, frames=frame_files, last_step='download')

@app.route('/remove_duplicates', methods=['POST'])
def remove_duplicates():
    try:
        frames = sorted([f for f in os.listdir(FRAMES_DIRECTORY) if f.endswith('.jpg')])
       
        if not frames:
            return render_template('download.html', message="No frames found to process.", last_step='convert')

        duplicates_removed = 0
        last_frame = None

        for frame in frames:
            frame_path = os.path.join(FRAMES_DIRECTORY, frame)
            current_frame = cv2.imread(frame_path)
           
            if last_frame is not None:
                current_frame_resized = cv2.resize(current_frame, (last_frame.shape[1], last_frame.shape[0]))
               
                if cv2.norm(current_frame_resized, last_frame, cv2.NORM_L2) < 1.0:
                    os.remove(frame_path)
                    duplicates_removed += 1
                else:
                    last_frame = current_frame_resized
            else:
                last_frame = current_frame
       
        message = f"Duplicates removed successfully. Total duplicates removed: {duplicates_removed}"
        remaining_frames = sorted([f'frames/{f}' for f in os.listdir(FRAMES_DIRECTORY) if f.endswith('.jpg')])
    except Exception as e:
        message = f"Error: {str(e)}"
        remaining_frames = []
   
    return render_template('download.html', message=message, duplicates_removed=True, frames=remaining_frames, last_step='convert')

@app.route('/stitch', methods=['POST'])
def stitch():
    try:
        frames = sorted([f for f in os.listdir(FRAMES_DIRECTORY) if f.endswith('.jpg')])
       
        if not frames:
            return render_template('download.html', message="No frames found to process.", last_step='remove_duplicates')

        create_directory(OUTPUT_VIDEO_DIRECTORY)
       
        frame_path = os.path.join(FRAMES_DIRECTORY, frames[0])
        frame = cv2.imread(frame_path)
        height, width, layers = frame.shape
        size = (width, height)
       
        output_video_path = os.path.join(OUTPUT_VIDEO_DIRECTORY, 'stitched_video.mp4')
        out = cv2.VideoWriter(output_video_path, cv2.VideoWriter_fourcc(*'mp4v'), 30, size)
       
        for frame_file in frames:
            frame_path = os.path.join(FRAMES_DIRECTORY, frame_file)
            frame = cv2.imread(frame_path)
            out.write(frame)
       
        out.release()

        # Convert the stitched video to WebM format
        webm_output_path = os.path.join(OUTPUT_VIDEO_DIRECTORY, 'stitched_video.webm')
        convert_mp4_to_webm(output_video_path, webm_output_path)

        message = f"Video created and converted successfully! <br> Output video path: {output_video_path} <br> WebM video path: {webm_output_path}"
    except Exception as e:
        message = f"Error: {str(e)}"
   
    return render_template('download.html', message=message, stitched=True, output_video_path=f'output_videos/{os.path.basename(output_video_path)}', webm_video_path=f'output_videos/{os.path.basename(webm_output_path)}', last_step='remove_duplicates')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        output_video_path = request.form['output_video_path']
        video_name = 'stitched_video'
       
        if not connect_str:
            raise ValueError("Azure Storage connection string is not provided.")
       
        try:
            blob_url = upload_video(output_video_path, video_name, connect_str)
            message = f"Video uploaded to: <a href='{blob_url}' target='_blank'>{blob_url}</a>"
        except Exception as e:
            message = f"Error uploading video: {str(e)}"
            blob_url = None
       
    except Exception as e:
        message = f"Error: {str(e)}"
        blob_url = None
   
    return render_template('download.html', message=message, blob_url=blob_url, stitched=True, last_step='stitch')

@app.route('/frames')
def view_frames():
    frames = sorted([f for f in os.listdir(FRAMES_DIRECTORY) if f.endswith('.jpg')])
    return render_template('frames.html', frames=frames)

@app.route('/images')
def images():
    frames = sorted([f for f in os.listdir(FRAMES_DIRECTORY) if f.endswith('.jpg')])
    return jsonify(frames)

@app.route('/play_video', methods=['GET'])
def play_video():
    webm_video_path = url_for('static', filename='output_videos/stitched_video.webm')
    print(f"WebM video path: {webm_video_path}")  # Debugging line
    return render_template('video_play.html', video_path=webm_video_path)

if __name__ == '__main__':
    create_directory(DOWNLOAD_DIRECTORY)
    create_directory(FRAMES_DIRECTORY)
    create_directory(OUTPUT_VIDEO_DIRECTORY)
    app.run(debug=True)
