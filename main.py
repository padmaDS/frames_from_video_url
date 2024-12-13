import os
import cv2
import numpy as np
import yt_dlp as youtube_dl
from pytube import YouTube

DOWNLOAD_DIRECTORY = 'downloads/'
OUTPUT_FOLDER = 'frames_output/'

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
    print(f"Downloaded video file: {video_filename}")

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
                
                frame_count += 1
            else:
                duplicate_count += 1
            
            # Update previous frame histogram
            previous_frame = frame_histogram
        
        # Release the video capture object and close all windows
        cap.release()
        cv2.destroyAllWindows()
        
        print(f"Unique frames extracted: {frame_count}")
        print(f"Number of Duplicate frames: {duplicate_count}")

    # Extract frames from the downloaded video
    extract_frames_and_count_duplicates(video_filename, output_folder)

# Example usage
if __name__ == "__main__":
    youtube_url = 'https://www.youtube.com/shorts/7wwUNqHVS-U'  # Replace with your YouTube URL
    download_and_extract_frames(youtube_url, OUTPUT_FOLDER)
